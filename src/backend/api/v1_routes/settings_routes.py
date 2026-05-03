"""
/api/v2/settings/* — user-facing settings endpoints.

Currently exposes the NVIDIA NIM API-key flow:

  POST /api/v2/settings/validate-nvidia-key
       {api_key} → {valid, model?, latency_s?, error?}
       Tests the candidate key against integrate.api.nvidia.com WITHOUT
       persisting it.

  POST /api/v2/settings/nvidia-key
       {api_key}                 → persist + reload
       {api_key: ""} or {clear: true} → wipe

Persistence writes to the local .env file (atomic temp+rename) and
updates ``os.environ['NVIDIA_API_KEY']`` immediately so subsequent
NIM calls pick the new value up without restart. The default NIM
client singleton is reset so its cached api_key is dropped.

License-gated — anonymous callers shouldn't poke the cloud key.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.backend.licensing.license_manager import verify_license

router = APIRouter(
    prefix="/api/v2/settings",
    tags=["settings"],
    dependencies=[Depends(verify_license())],
)


class _ValidateKeyRequest(BaseModel):
    api_key: str = Field(..., min_length=8, max_length=200)


class _SaveKeyRequest(BaseModel):
    api_key: Optional[str] = Field(None, max_length=200)
    clear: bool = False


# ---- helpers ----------------------------------------------------------------

def _env_path() -> Path:
    """Repo .env, anchored to the source tree (not CWD)."""
    return Path(__file__).resolve().parents[3] / ".env"


def _read_env() -> str:
    p = _env_path()
    return p.read_text(encoding="utf-8") if p.exists() else (
        "# RĀMAN Studio — local environment (gitignored).\n"
    )


def _write_env_atomic(text: str) -> None:
    p = _env_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    # Atomic write: temp file in the same directory, then rename.
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".env.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, p)
        os.chmod(p, 0o600)   # readable only by the user
    except Exception:
        try: os.unlink(tmp)
        except OSError: pass
        raise


def _set_env_var(text: str, key: str, value: str) -> str:
    """Replace or append a KEY=VALUE line. Comments and other vars preserved."""
    out = []
    found = False
    for line in text.splitlines(keepends=False):
        if line.startswith(f"{key}=") and not line.lstrip().startswith("#"):
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"{key}={value}")
    if text.endswith("\n") and out and not out[-1].endswith("\n"):
        return "\n".join(out) + "\n"
    return "\n".join(out)


# ---- routes -----------------------------------------------------------------

@router.post("/validate-nvidia-key")
async def validate_nvidia_key(req: _ValidateKeyRequest) -> dict:
    """
    Test the candidate key by hitting NIM's health endpoint with a
    minimal chat call. Returns {valid: bool, model?, latency_s?, error?}.

    Does NOT persist anything; safe to call on every keystroke at the
    client (debounced) for live validation.
    """
    from src.ai_engine.nim_client import NIMClient
    client = NIMClient(api_key=req.api_key)
    h = client.health()
    if h.get("ok"):
        return {
            "valid": True,
            "model": h.get("model"),
            "latency_s": h.get("latency_s"),
        }
    return {
        "valid": False,
        "error": h.get("reason") or "Key check failed",
        "status": h.get("status"),
    }


@router.post("/nvidia-key")
async def save_nvidia_key(req: _SaveKeyRequest) -> dict:
    """
    Persist the NVIDIA API key to the local .env, update the live
    process env, and reset the NIM client singleton so the next call
    picks the new key up.
    """
    new_key = "" if req.clear else (req.api_key or "")
    if new_key and not new_key.startswith("nvapi-"):
        raise HTTPException(400, "NVIDIA API keys start with 'nvapi-'.")

    # Write .env atomically.
    try:
        text = _read_env()
        text = _set_env_var(text, "NVIDIA_API_KEY", new_key)
        _write_env_atomic(text)
    except Exception as e:
        raise HTTPException(500, f"Could not update .env: {type(e).__name__}")

    # Update live env + reset singleton.
    os.environ["NVIDIA_API_KEY"] = new_key
    try:
        from src.ai_engine.nim_client import reset_default_client
        reset_default_client()
    except Exception:
        pass
    # Also reset the local _get_alchemi cache the server.py routes use.
    try:
        import src.backend.api.server as _server
        if hasattr(_server, "_alchemi"):
            _server._alchemi = None
    except Exception:
        pass

    return {
        "ok": True,
        "stored": bool(new_key),
        "message": "AI features active." if new_key else "AI features disabled.",
    }


@router.get("/nvidia-key/status")
async def nvidia_key_status() -> dict:
    """Return whether a key is configured (without exposing it)."""
    key = os.environ.get("NVIDIA_API_KEY", "")
    return {
        "configured": bool(key),
        "tail": ("…" + key[-4:]) if key else None,
    }
