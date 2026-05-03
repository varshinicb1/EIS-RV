"""
License server — stub.

This is the *issuer* side of the licensing system. It runs separately
from the desktop app, with the **private** Ed25519 key on disk. It is
NOT part of the desktop app and is NOT loaded by the desktop FastAPI
server.

What it does today
------------------
* ``POST /v1/license/issue``: takes ``{sub, plan, hardware_id, days,
  features}`` and returns a signed token.

What it does NOT do today (deliberate; ship later)
--------------------------------------------------
* No payment integration. Hand off to Stripe and validate the webhook
  before calling ``issue_token``.
* No revocation list. We rely on short ``exp`` for v1.
* No quota / per-plan defaults. The caller is responsible for choosing
  the duration and feature set.
* No auth on this endpoint. **Do not deploy as-is** — put it behind a
  reverse proxy that terminates auth (mTLS, OAuth, an admin-only API
  key, your call). Treat the private key as a master secret.

Run locally for testing
-----------------------
    PRIV=~/.raman-studio-license-server/ed25519-priv.pem \\
    uvicorn src.backend.licensing.license_server_stub:app --port 8765

Generate a token from a Python REPL
-----------------------------------
    from src.backend.licensing.license_server_stub import _issue_via_cli
    print(_issue_via_cli(
        sub="alice@example.com",
        plan="individual",
        hardware_id="<hex from desktop client>",
        days=365,
        features=["eis","cv","gcd","agent","alchemi"],
    ))
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.backend.licensing.license_token import issue_token


# ---- Private key loader ---------------------------------------------------


def _default_private_key_path() -> Path:
    """The location the keypair-generation script writes to."""
    return Path.home() / ".raman-studio-license-server" / "ed25519-priv.pem"


def _load_private_key() -> Ed25519PrivateKey:
    path = Path(os.environ.get("RAMAN_LICENSE_PRIVATE_KEY",
                                _default_private_key_path()))
    if not path.exists():
        raise FileNotFoundError(
            f"License server private key not found at {path}. "
            "Generate one with the keygen step (see SECURITY.md)."
        )
    pem = path.read_bytes()
    key = serialization.load_pem_private_key(pem, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError(f"Expected Ed25519, got {type(key).__name__}")
    return key


_private_key: Optional[Ed25519PrivateKey] = None


def _get_private_key() -> Ed25519PrivateKey:
    global _private_key
    if _private_key is None:
        _private_key = _load_private_key()
    return _private_key


# ---- API -----------------------------------------------------------------


class IssueRequest(BaseModel):
    sub: str = Field(..., description="Subscriber email")
    plan: str = Field(..., description="trial | individual | lab | institution")
    hardware_id: str = Field(..., min_length=16, max_length=128,
                              description="Client hardware fingerprint")
    days: int = Field(..., gt=0, le=3650,
                       description="Token lifetime in days")
    features: list[str] = Field(default_factory=list)


class IssueResponse(BaseModel):
    token: str
    payload_summary: dict[str, Any]


app = FastAPI(
    title="RĀMAN License Server (stub)",
    description=(
        "Internal-only token issuer. Do NOT expose to the public internet "
        "without an auth layer in front."
    ),
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, Any]:
    try:
        _get_private_key()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/v1/license/issue", response_model=IssueResponse)
def issue(req: IssueRequest) -> IssueResponse:
    try:
        priv = _get_private_key()
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))

    if req.plan not in {"trial", "individual", "lab", "institution"}:
        raise HTTPException(status_code=400,
                            detail=f"unknown plan {req.plan!r}")

    token = issue_token(
        private_key=priv,
        sub=req.sub,
        plan=req.plan,
        hardware_id=req.hardware_id,
        duration_seconds=int(req.days) * 86400,
        features=list(req.features),
    )

    return IssueResponse(
        token=token,
        payload_summary={
            "sub": req.sub,
            "plan": req.plan,
            "hardware_id_short": req.hardware_id[:12],
            "days": req.days,
            "features": req.features,
        },
    )


# ---- CLI helper for manual testing ----------------------------------------


def _issue_via_cli(
    *,
    sub: str,
    plan: str,
    hardware_id: str,
    days: int,
    features: list[str],
) -> str:
    return issue_token(
        private_key=_load_private_key(),
        sub=sub,
        plan=plan,
        hardware_id=hardware_id,
        duration_seconds=days * 86400,
        features=features,
    )
