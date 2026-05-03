"""
Ed25519-signed license tokens.

Token format
------------
::

    RMNS1.<payload-b64url>.<sig-b64url>

* ``RMNS1`` is a constant magic+version. Easy to grep for.
* ``payload-b64url`` is the URL-safe base64 (no padding) of a JSON object:

      {
        "iss": "vidyuthlabs",
        "sub": "<user_email>",
        "plan": "trial" | "individual" | "lab" | "institution",
        "hw":  "<hardware_id>",        # 64 hex chars (sha256 hex)
        "iat": 1730000000,             # issued-at, unix seconds
        "nbf": 1730000000,             # not-before, unix seconds
        "exp": 1732592000,             # expires-at, unix seconds
        "feat": ["eis", "cv", ...],   # enabled feature ids
        "id":  "<uuid4>",              # token id, for revocation lists
        "v":   1                       # payload schema version
      }

* ``sig-b64url`` is the URL-safe base64 (no padding) of the Ed25519
  signature over the bytes ``magic + b"." + payload-b64url``.

We use raw Ed25519, not JWT, deliberately:

* No alg-confusion attacks (RFC 8725).
* No HS256 footgun.
* Tiny libraries / tiny keys (32-byte public key embedded in client).

Verification policy
-------------------
* Signature checks against the embedded public key.
* ``nbf <= now <= exp``.
* ``hw`` matches the local hardware id, OR the token has plan="trial"
  (trials are anchored locally, not by the license server).
* ``v == 1``.

If any check fails the token is rejected. We do not fall back to "valid
anyway".
"""
from __future__ import annotations

import base64
import json
import time
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


# Magic+version. Bump when we make backwards-incompatible changes.
TOKEN_MAGIC = "RMNS1"
PAYLOAD_VERSION = 1


# ---- Errors ---------------------------------------------------------------


class LicenseTokenError(ValueError):
    """Token failed to parse, signature, or claim validation."""


# ---- b64url helpers (no padding) ------------------------------------------


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


# ---- Payload --------------------------------------------------------------


@dataclass
class LicensePayload:
    sub: str                      # subscriber email
    plan: str                     # trial | individual | lab | institution
    hw: str                       # hardware id (64 hex)
    iat: int                      # issued at
    nbf: int                      # not before
    exp: int                      # expires at
    feat: list[str]              # feature flags
    id: str                       # token id
    iss: str = "vidyuthlabs"
    v: int = PAYLOAD_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "iss": self.iss,
            "sub": self.sub,
            "plan": self.plan,
            "hw": self.hw,
            "iat": self.iat,
            "nbf": self.nbf,
            "exp": self.exp,
            "feat": list(self.feat),
            "id": self.id,
            "v": self.v,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LicensePayload":
        try:
            return cls(
                iss=data.get("iss", "vidyuthlabs"),
                sub=str(data["sub"]),
                plan=str(data["plan"]),
                hw=str(data["hw"]),
                iat=int(data["iat"]),
                nbf=int(data["nbf"]),
                exp=int(data["exp"]),
                feat=list(data.get("feat") or []),
                id=str(data["id"]),
                v=int(data.get("v", 1)),
            )
        except (KeyError, TypeError, ValueError) as e:
            raise LicenseTokenError(f"malformed payload: {e}") from e


# ---- Sign (server side) ---------------------------------------------------


def issue_token(
    *,
    private_key: Ed25519PrivateKey,
    sub: str,
    plan: str,
    hardware_id: str,
    duration_seconds: int,
    features: list[str],
    now: Optional[int] = None,
) -> str:
    """
    Build and sign a license token. Server-side only — the private key
    must never reach the client.
    """
    if now is None:
        now = int(time.time())

    payload = LicensePayload(
        sub=sub,
        plan=plan,
        hw=hardware_id,
        iat=now,
        nbf=now,
        exp=now + int(duration_seconds),
        feat=list(features),
        id=str(uuid.uuid4()),
    )

    payload_json = json.dumps(payload.to_dict(), separators=(",", ":"),
                              sort_keys=True).encode("utf-8")
    payload_b64 = _b64url_encode(payload_json)

    signing_input = f"{TOKEN_MAGIC}.{payload_b64}".encode("ascii")
    signature = private_key.sign(signing_input)
    sig_b64 = _b64url_encode(signature)

    return f"{TOKEN_MAGIC}.{payload_b64}.{sig_b64}"


# ---- Verify (client side) -------------------------------------------------


def parse_and_verify(
    token: str,
    *,
    public_key: Ed25519PublicKey,
    expected_hw: str,
    now: Optional[int] = None,
    allow_clock_skew_s: int = 60,
) -> LicensePayload:
    """
    Parse, signature-check, and claim-check a license token.

    Raises ``LicenseTokenError`` on any failure.

    ``expected_hw`` is the local machine's hardware id. If the token's
    plan is ``"trial"`` we still verify ``hw`` matches — trials are
    anchored locally so the same trial can't be replayed on another
    machine.
    """
    if not token or "." not in token:
        raise LicenseTokenError("empty or malformed token")

    parts = token.split(".")
    if len(parts) != 3:
        raise LicenseTokenError("token must have 3 segments")

    magic, payload_b64, sig_b64 = parts
    if magic != TOKEN_MAGIC:
        raise LicenseTokenError(
            f"unknown token version {magic!r} (expected {TOKEN_MAGIC!r})"
        )

    try:
        signature = _b64url_decode(sig_b64)
    except Exception as e:
        raise LicenseTokenError(f"signature is not valid base64: {e}") from e

    signing_input = f"{magic}.{payload_b64}".encode("ascii")
    try:
        public_key.verify(signature, signing_input)
    except InvalidSignature as e:
        raise LicenseTokenError("signature does not verify") from e

    try:
        payload_bytes = _b64url_decode(payload_b64)
        data = json.loads(payload_bytes.decode("utf-8"))
    except Exception as e:
        raise LicenseTokenError(f"payload is not valid JSON: {e}") from e

    payload = LicensePayload.from_dict(data)

    if payload.v != PAYLOAD_VERSION:
        raise LicenseTokenError(
            f"unsupported payload version {payload.v} (this client speaks v{PAYLOAD_VERSION})"
        )

    if now is None:
        now = int(time.time())

    if now + allow_clock_skew_s < payload.nbf:
        raise LicenseTokenError(
            f"token not valid until {payload.nbf} (now={now})"
        )

    if now > payload.exp + allow_clock_skew_s:
        raise LicenseTokenError(
            f"token expired at {payload.exp} (now={now})"
        )

    if payload.hw != expected_hw:
        raise LicenseTokenError(
            "token is bound to a different machine"
        )

    return payload


# ---- Public-key helper ----------------------------------------------------


def load_public_key_b64(b64_text: str) -> Ed25519PublicKey:
    """Load a 32-byte raw Ed25519 public key from base64."""
    raw = base64.b64decode(b64_text)
    if len(raw) != 32:
        raise ValueError(f"expected 32 raw bytes, got {len(raw)}")
    return Ed25519PublicKey.from_public_bytes(raw)
