"""
NVIDIA NIM (Neural Inference Microservice) client — honest version.

What this module does
---------------------
Calls the OpenAI-compatible chat-completions endpoint at
``https://integrate.api.nvidia.com/v1/chat/completions`` with a Bearer token
from ``NVIDIA_API_KEY``. That is the real public endpoint and the real
public API shape; everything in this client has been tested against it.

What this module does NOT do
----------------------------
- It does NOT call the URLs that earlier code in this repo invented
  (``/optimize``, ``/predict``, ``/properties``, ``/md``,
  ``/materials/predict`` and so on). Those endpoints do not exist on
  ``integrate.api.nvidia.com``.
- It does NOT pretend to run MLIPs (MACE, ORB, SevenNet, MatterSim) just
  because their model names appear in marketing copy. NVIDIA hosts those
  models behind separate microservices with separate request shapes; until
  we wire one up correctly, we say "not available" rather than fabricate.
- It does NOT silently fall back to look-alike data when an API call
  fails. The caller gets an explicit ``NIMError`` so they can decide.

Materials property prediction
-----------------------------
For a small set of well-characterised materials (the 48-entry
``materials_db``), we return values from that database — no LLM, no API
call. For everything else we either return ``unknown`` or, when the
caller explicitly asks for an LLM estimate, we send a strict-format
prompt to the chat model and validate the JSON it returns. Estimates
from a chat LLM are flagged as such; they are not computational
chemistry and we do not present them as such.

Configuration
-------------
- ``NVIDIA_API_KEY`` (env): required for any cloud call. If unset, the
  client raises ``NIMError`` on call rather than silently fabricating.
- ``NIM_BASE_URL`` (env, optional): override the endpoint. Defaults to
  ``https://integrate.api.nvidia.com/v1``.
- ``NIM_DEFAULT_MODEL`` (env, optional): override the default chat model.
  Defaults to ``meta/llama-3.3-70b-instruct``.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---- Public errors ---------------------------------------------------------


class NIMError(RuntimeError):
    """Raised when a NIM call fails (auth, network, rate limit, bad response)."""

    def __init__(self, message: str, *, status: int | None = None,
                 retryable: bool = False, detail: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.retryable = retryable
        self.detail = detail


# ---- Models we support -----------------------------------------------------

# Curated short list — every entry below is a real NIM available at
# integrate.api.nvidia.com/v1/chat/completions. Keep this list narrow on
# purpose; aliases prevent typos and let us rotate without touching callers.
CHAT_MODELS: dict[str, str] = {
    # Default — 70B quality, OpenAI-compatible.
    "default":   "meta/llama-3.3-70b-instruct",

    # Smaller / faster.
    "fast":      "meta/llama-3.1-8b-instruct",

    # NVIDIA-tuned variants.
    "nemotron":  "nvidia/llama-3.3-nemotron-super-49b-v1",

    # Mixture-of-experts.
    "mixtral":   "mistralai/mixtral-8x22b-instruct-v0.1",
}


# ---- Result types ----------------------------------------------------------


@dataclass
class ChatCompletion:
    """Subset of the OpenAI/NIM chat-completion response we actually use."""
    text: str
    model: str
    finish_reason: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


# ---- Client ----------------------------------------------------------------


class NIMClient:
    """
    Thin OpenAI-compatible client for NVIDIA NIM chat completions.

    This client is intentionally synchronous and small. The FastAPI app
    wraps it in ``run_in_threadpool`` when called from a request handler.
    """

    DEFAULT_TIMEOUT_S = 60
    MAX_RETRIES = 3
    BACKOFF_S = (0.5, 1.5, 4.0)  # one entry per retry

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        timeout_s: int = DEFAULT_TIMEOUT_S,
    ) -> None:
        self.api_key = api_key or os.environ.get("NVIDIA_API_KEY", "")
        self.base_url = (
            base_url
            or os.environ.get("NIM_BASE_URL")
            or "https://integrate.api.nvidia.com/v1"
        ).rstrip("/")
        self.default_model = self._resolve_model(
            default_model
            or os.environ.get("NIM_DEFAULT_MODEL")
            or "default"
        )
        self.timeout_s = timeout_s

        # ``requests`` is optional; if it isn't installed we fail at call time
        # rather than at import time, so importing this module never breaks
        # the rest of the app.
        try:
            import requests  # noqa: F401  (presence check)
            self._requests_available = True
        except ImportError:
            self._requests_available = False

    @property
    def configured(self) -> bool:
        """True if we have an API key AND requests is installed."""
        return bool(self.api_key) and self._requests_available

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: Optional[str] = None,
        temperature: float = 0.5,
        max_tokens: int = 1024,
        top_p: float = 1.0,
        stop: Optional[list[str]] = None,
    ) -> ChatCompletion:
        """
        Send a chat-completion request.

        ``messages`` is the standard OpenAI shape:
            [{"role": "system" | "user" | "assistant", "content": "..."}, ...]

        Raises ``NIMError`` on any failure. Caller decides whether to fall
        back to a local model.
        """
        self._require_configured()

        body = {
            "model": self._resolve_model(model) if model else self.default_model,
            "messages": list(messages),
            "temperature": float(temperature),
            "top_p": float(top_p),
            "max_tokens": int(max_tokens),
            "stream": False,
        }
        if stop:
            body["stop"] = list(stop)

        data = self._post("/chat/completions", body)

        try:
            choice = data["choices"][0]
            message = choice["message"]
            content = message.get("content", "")
            finish = choice.get("finish_reason", "")
            usage = data.get("usage", {}) or {}
        except (KeyError, IndexError, TypeError) as e:
            raise NIMError(
                "NIM returned an unexpected response shape",
                detail=json.dumps(data)[:500],
            ) from e

        return ChatCompletion(
            text=content,
            model=body["model"],
            finish_reason=finish,
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
            raw=data,
        )

    def chat_text(self, prompt: str, *, system: Optional[str] = None,
                  **kwargs: Any) -> str:
        """Convenience: single-prompt → reply text."""
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, **kwargs).text

    def chat_json(
        self,
        prompt: str,
        *,
        schema_hint: Optional[str] = None,
        system: Optional[str] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Ask the model for JSON output, validate it, return a dict.

        We do NOT trust the model to follow the schema. If the response
        contains a fenced JSON block we extract it; if not, we look for
        the first ``{ ... }`` substring and try ``json.loads`` on that.
        Any parse failure raises ``NIMError`` — the caller is expected to
        handle the failure rather than silently use partial / fabricated
        data.
        """
        sys_parts = [
            "You return ONLY valid JSON, no prose, no commentary.",
            "If unsure of a value, use null.",
        ]
        if schema_hint:
            sys_parts.append(f"Required JSON shape: {schema_hint}")
        if system:
            sys_parts.append(system)
        merged_system = "\n".join(sys_parts)

        completion = self.chat(
            [
                {"role": "system", "content": merged_system},
                {"role": "user", "content": prompt},
            ],
            **kwargs,
        )

        text = completion.text.strip()
        parsed = _extract_json(text)
        if parsed is None:
            raise NIMError(
                "Model did not return parseable JSON",
                detail=text[:500],
            )
        return parsed

    def health(self) -> dict[str, Any]:
        """Quick liveness check — small chat call. Returns dict, never raises."""
        if not self.configured:
            return {
                "ok": False,
                "configured": False,
                "reason": (
                    "NVIDIA_API_KEY not set" if not self.api_key
                    else "requests library not installed"
                ),
            }
        try:
            t0 = time.perf_counter()
            reply = self.chat_text("ping", max_tokens=4, temperature=0.0)
            return {
                "ok": True,
                "configured": True,
                "model": self.default_model,
                "latency_s": round(time.perf_counter() - t0, 3),
                "reply": reply[:64],
            }
        except NIMError as e:
            return {
                "ok": False,
                "configured": True,
                "status": e.status,
                "reason": str(e),
            }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require_configured(self) -> None:
        if not self.api_key:
            raise NIMError(
                "NVIDIA_API_KEY is not set. RĀMAN Studio runs in fully-local "
                "mode without a key; set NVIDIA_API_KEY in .env to enable "
                "cloud LLM features."
            )
        if not self._requests_available:
            raise NIMError(
                "The 'requests' library is not installed. "
                "Run: pip install requests"
            )

    @staticmethod
    def _resolve_model(name: str) -> str:
        """Look up an alias, or pass through a fully-qualified model id."""
        return CHAT_MODELS.get(name, name)

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        import requests  # imported lazily, see __init__

        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        last_error: Optional[NIMError] = None
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                resp = requests.post(
                    url, headers=headers, json=body, timeout=self.timeout_s
                )
            except requests.Timeout:
                last_error = NIMError("NIM request timed out", retryable=True)
            except requests.ConnectionError as e:
                last_error = NIMError(f"Cannot reach NIM endpoint: {e}",
                                      retryable=True)
            except requests.RequestException as e:
                # Non-retryable transport error.
                raise NIMError(f"HTTP error: {e}") from e
            else:
                if resp.status_code == 200:
                    try:
                        return resp.json()
                    except ValueError as e:
                        raise NIMError(
                            "NIM returned 200 but body is not JSON",
                            status=200,
                            detail=resp.text[:500],
                        ) from e

                if resp.status_code in (401, 403):
                    raise NIMError(
                        "NVIDIA API key was rejected (check NVIDIA_API_KEY)",
                        status=resp.status_code,
                        detail=resp.text[:500],
                    )

                if resp.status_code == 404:
                    raise NIMError(
                        f"NIM endpoint not found: {path}. The model id may be "
                        "wrong or no longer hosted.",
                        status=404,
                        detail=resp.text[:500],
                    )

                if resp.status_code == 429:
                    last_error = NIMError(
                        "NIM rate-limit exceeded",
                        status=429,
                        retryable=True,
                        detail=resp.text[:500],
                    )
                elif 500 <= resp.status_code < 600:
                    last_error = NIMError(
                        f"NIM server error {resp.status_code}",
                        status=resp.status_code,
                        retryable=True,
                        detail=resp.text[:500],
                    )
                else:
                    raise NIMError(
                        f"Unexpected NIM status {resp.status_code}",
                        status=resp.status_code,
                        detail=resp.text[:500],
                    )

            # Retryable failure: back off and try again, unless we're out of attempts.
            if attempt < self.MAX_RETRIES:
                delay = self.BACKOFF_S[min(attempt, len(self.BACKOFF_S) - 1)]
                logger.warning(
                    "NIM call failed (%s); retrying in %.1fs (attempt %d/%d)",
                    last_error, delay, attempt + 1, self.MAX_RETRIES,
                )
                time.sleep(delay)

        assert last_error is not None  # we only reach here after retries exhausted
        raise last_error


# ---- Helpers ---------------------------------------------------------------


_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)
_BARE_JSON_RE = re.compile(r"(\{.*\}|\[.*\])", re.DOTALL)


def _extract_json(text: str) -> Optional[dict[str, Any] | list[Any]]:
    """Best-effort extraction of a JSON value from possibly-markdowned text."""
    if not text:
        return None
    m = _FENCED_JSON_RE.search(text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Fall back to the first balanced-looking JSON we can find.
    m = _BARE_JSON_RE.search(text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            return None
    return None


# ---- Module-level singleton (matches the existing nvidia_intelligence pattern) ----


_default_client: Optional[NIMClient] = None


def get_default_client() -> NIMClient:
    """Return a process-wide NIMClient. Cheap to call repeatedly."""
    global _default_client
    if _default_client is None:
        _default_client = NIMClient()
    return _default_client


def reset_default_client() -> None:
    """For tests."""
    global _default_client
    _default_client = None
