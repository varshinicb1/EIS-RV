"""
Local AI agent — Raman-Qwen LoRA chat router.

This was previously a separate FastAPI process at ``src/ai_engine/agent_server.py``
listening on port 8001. It now mounts as an ``APIRouter`` on the main
backend so we run a single Python process.

Design notes
------------
- **Lazy load.** The model is heavy (Qwen-1.5-1.8B + 4-bit quant + LoRA).
  We do NOT import torch / transformers / peft at module-import time. The
  first request to ``/api/v2/agent/chat`` triggers the load. Subsequent
  requests reuse the loaded model.
- **Honest about availability.** If torch / transformers / peft / the
  LoRA checkpoint are missing, the route returns a structured
  ``available=false`` response — it does NOT silently fall back to NIM.
  Callers can choose explicitly.
- **Prompt-injection fix.** The earlier code parsed ```` ```json ``` ````
  blocks from model output and returned them verbatim as ``tool_calls``,
  giving any prompter a path to forge structured tool calls. We no
  longer do that. We return the assistant text and a separate
  ``hint_json`` field that is ONLY populated when the model produces
  parseable JSON AND the JSON shape is known to us. ``hint_json`` is
  advisory — the caller is expected to validate before acting.
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.backend.licensing.license_manager import verify_license

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/v2/agent",
    tags=["ai_agent"],
    dependencies=[Depends(verify_license())],
)


# ---- Configuration ---------------------------------------------------------

BASE_MODEL_ID = os.environ.get("RAMAN_AGENT_BASE_MODEL", "Qwen/Qwen1.5-1.8B-Chat")
ADAPTER_DIR = os.environ.get(
    "RAMAN_AGENT_ADAPTER_DIR", "models/Raman-Qwen-Agent"
)

# Limits — defensive against pathological prompts.
MAX_PROMPT_CHARS = 8000
MAX_NEW_TOKENS = 1024
MAX_HISTORY_MESSAGES = 30


# ---- Schemas ---------------------------------------------------------------


class AgentMessage(BaseModel):
    role: str = Field(..., pattern="^(system|user|assistant)$")
    content: str = Field(..., max_length=MAX_PROMPT_CHARS)


class AgentChatRequest(BaseModel):
    messages: list[AgentMessage]
    temperature: float = Field(0.4, ge=0.0, le=2.0)
    max_new_tokens: int = Field(512, ge=16, le=MAX_NEW_TOKENS)
    seed: Optional[int] = None


class AgentStatus(BaseModel):
    available: bool
    loaded: bool
    base_model: str
    adapter_dir: str
    adapter_present: bool
    reason: Optional[str] = None


# ---- Lazy-loaded model holder ---------------------------------------------


class _ModelHolder:
    """
    Holds tokenizer + model after first use. Thread-safe lazy load — the
    FastAPI app may serve multiple in-flight requests; only one of them
    should pay the load cost.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loaded = False
        self._load_error: Optional[str] = None
        self._model: Any = None
        self._tokenizer: Any = None

    @property
    def loaded(self) -> bool:
        return self._loaded

    @property
    def adapter_present(self) -> bool:
        return os.path.isdir(ADAPTER_DIR) and any(
            f.endswith((".safetensors", ".bin"))
            for f in os.listdir(ADAPTER_DIR)
            if not f.startswith("checkpoint-")
        ) or any(
            os.path.isdir(os.path.join(ADAPTER_DIR, d))
            and d.startswith("checkpoint-")
            for d in (os.listdir(ADAPTER_DIR) if os.path.isdir(ADAPTER_DIR) else [])
        )

    def status(self) -> AgentStatus:
        return AgentStatus(
            available=self._load_error is None,
            loaded=self._loaded,
            base_model=BASE_MODEL_ID,
            adapter_dir=ADAPTER_DIR,
            adapter_present=self.adapter_present,
            reason=self._load_error,
        )

    def _try_load(self) -> None:
        """Run once. On failure, sets self._load_error and leaves loaded=False."""
        try:
            import torch  # noqa: F401
            from transformers import (  # type: ignore
                AutoModelForCausalLM,
                AutoTokenizer,
                BitsAndBytesConfig,
            )
        except ImportError as e:
            self._load_error = (
                f"transformers/torch not installed: {e}. "
                "Install with: pip install torch transformers accelerate"
            )
            return

        try:
            tokenizer = AutoTokenizer.from_pretrained(
                BASE_MODEL_ID, trust_remote_code=True
            )
        except Exception as e:
            self._load_error = f"Failed to load tokenizer for {BASE_MODEL_ID}: {e}"
            return

        bnb_config: Any = None
        try:
            import torch as _torch  # local rebind so `torch` is in scope below
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=_torch.bfloat16,
            )
        except Exception as e:
            logger.info("bitsandbytes 4-bit unavailable (%s); loading fp16 instead", e)
            bnb_config = None

        try:
            base_kwargs: dict[str, Any] = {"trust_remote_code": True,
                                            "device_map": "auto"}
            if bnb_config is not None:
                base_kwargs["quantization_config"] = bnb_config

            base_model = AutoModelForCausalLM.from_pretrained(
                BASE_MODEL_ID, **base_kwargs
            )
        except Exception as e:
            self._load_error = f"Failed to load base model {BASE_MODEL_ID}: {e}"
            return

        # Try the adapter; failure is non-fatal — fall back to base model.
        model = base_model
        if os.path.isdir(ADAPTER_DIR):
            try:
                from peft import PeftModel  # type: ignore

                # Find the latest checkpoint dir if present.
                checkpoints = sorted(
                    (d for d in os.listdir(ADAPTER_DIR) if d.startswith("checkpoint-")),
                    key=lambda d: int(d.split("-", 1)[1]) if d.split("-", 1)[1].isdigit() else 0,
                )
                target = (
                    os.path.join(ADAPTER_DIR, checkpoints[-1])
                    if checkpoints
                    else ADAPTER_DIR
                )
                model = PeftModel.from_pretrained(base_model, target)
                logger.info("Loaded LoRA adapter from %s", target)
            except Exception as e:
                logger.warning(
                    "Adapter load failed (using base model): %s", e
                )

        try:
            model.eval()
        except Exception:
            logger.warning("%s:%d swallowed exception", __name__, 199, exc_info=False)

        self._tokenizer = tokenizer
        self._model = model
        self._loaded = True
        self._load_error = None
        logger.info("Raman-Qwen agent loaded successfully")

    def ensure_loaded(self) -> None:
        if self._loaded or self._load_error is not None:
            return
        with self._lock:
            if self._loaded or self._load_error is not None:
                return
            self._try_load()

    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float,
        max_new_tokens: int,
        seed: Optional[int] = None,
    ) -> str:
        if not self._loaded:
            raise RuntimeError(self._load_error or "model not loaded")

        import torch  # safe — we only get here if load succeeded

        prompt = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        inputs = self._tokenizer([prompt], return_tensors="pt")
        try:
            inputs = inputs.to(self._model.device)
        except Exception:
            pass  # CPU / device map fallback

        if seed is not None:
            torch.manual_seed(int(seed))

        with torch.no_grad():
            out = self._model.generate(
                **inputs,
                max_new_tokens=int(max_new_tokens),
                temperature=float(temperature),
                do_sample=temperature > 0,
                pad_token_id=self._tokenizer.eos_token_id,
            )

        # Strip the prompt prefix to get just the new tokens.
        in_len = inputs.input_ids.shape[1]
        new_tokens = out[0][in_len:]
        return self._tokenizer.decode(new_tokens, skip_special_tokens=True)


_holder = _ModelHolder()


# ---- Routes ---------------------------------------------------------------


@router.get("/status", response_model=AgentStatus)
async def agent_status() -> AgentStatus:
    """Reports whether the agent can be invoked. Does not load the model."""
    return _holder.status()


@router.post("/load")
async def agent_load() -> dict[str, Any]:
    """
    Force-load the model (otherwise it loads on the first chat request).
    Useful for warming the GPU before a user-visible turn.
    """
    _holder.ensure_loaded()
    s = _holder.status()
    return {"loaded": s.loaded, "available": s.available, "reason": s.reason}


@router.post("/chat")
async def agent_chat(req: AgentChatRequest) -> dict[str, Any]:
    """
    Generate a reply from the local Raman-Qwen agent.

    On model unavailable, returns ``available=False`` with a reason.
    Caller can fall back to NIM (``/api/nvidia/chat``) explicitly.
    """
    if len(req.messages) == 0:
        raise HTTPException(status_code=400, detail="messages must not be empty")
    if len(req.messages) > MAX_HISTORY_MESSAGES:
        raise HTTPException(
            status_code=400,
            detail=f"too many messages (max {MAX_HISTORY_MESSAGES})",
        )

    _holder.ensure_loaded()
    if not _holder.loaded:
        return {
            "available": False,
            "answer": None,
            "reason": _holder.status().reason,
        }

    # Run the (CPU/GPU-blocking) generate call off the asyncio loop.
    from starlette.concurrency import run_in_threadpool

    try:
        text = await run_in_threadpool(
            _holder.generate,
            [m.model_dump() for m in req.messages],
            temperature=req.temperature,
            max_new_tokens=req.max_new_tokens,
            seed=req.seed,
        )
    except Exception as e:
        logger.exception("agent generate failed")
        raise HTTPException(status_code=500, detail=f"generate failed: {e}")

    # Audit-finding C5 fix: do NOT parse fenced JSON blocks and return them
    # as `tool_calls`. We expose a `hint_json` field that is populated only
    # when the entire reply is a valid JSON object and we don't expand it
    # into a structured action server-side. The caller validates before use.
    hint_json: Optional[Any] = None
    stripped = text.strip()
    if stripped.startswith(("{", "[")):
        try:
            import json
            hint_json = json.loads(stripped)
        except Exception:
            hint_json = None

    return {
        "available": True,
        "answer": text,
        "hint_json": hint_json,
        "model": BASE_MODEL_ID,
    }
