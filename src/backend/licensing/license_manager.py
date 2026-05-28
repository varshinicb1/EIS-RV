"""
License manager — honest replacement.

Compared to the previous version
--------------------------------
The previous license_manager (628 LOC) had a hardcoded HMAC secret
shipped to every client and used Fernet (AES-128-CBC + HMAC-SHA256) to
"encrypt" the license file with a key derived from a publicly-known
constant. Any user who unzipped the binary could forge license tokens.
The README marketed this as "AES-256, hardware-bound, military-grade".

This rewrite:

* Verifies tokens with **Ed25519 + an embedded public key**. The
  matching private key never reaches the client; it lives on the
  license server. Forging a valid token requires breaking Ed25519.
* Binds tokens to a **stable hardware id** computed from the platform's
  permanent identifier (``/etc/machine-id`` on Linux, ``IOPlatformUUID``
  on macOS, ``MachineGuid`` on Windows), with explicit ``degraded``
  flag if we had to fall back.
* Stores trial state in a small encrypted-at-rest file under the user's
  application data directory. The encryption is meaningful here only as
  tamper-evidence — a determined attacker can rewrite the trial state
  file, but doing so does not extend the license: the server-issued
  token's expiry is still enforced cryptographically.
* Offers a FastAPI-friendly ``Depends(verify_license)`` so simulation
  routes can require a valid license. Trials are accepted.

What is in scope today
----------------------
* Token verification (offline).
* Trial bootstrap / countdown.
* ``activate_license`` from a server-issued token.
* ``deactivate_license``.
* ``Depends(verify_license)`` for FastAPI.

What is out of scope today (on purpose)
---------------------------------------
* Stripe + the actual license server endpoint. The server stub lives at
  ``src/backend/licensing/license_server_stub.py`` and is not deployed.
* Online revocation lookups. Once we run a license server we can add a
  CRL endpoint and check periodically; for v1 we rely on short-ish
  ``exp`` values (e.g. 30 days for paid plans, refreshed by the client
  in the background).
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from src.backend.licensing.hardware_id import (
    HardwareFingerprint,
    compute_fingerprint,
)
from src.backend.licensing.license_token import (
    LicensePayload,
    LicenseTokenError,
    load_public_key_b64,
    parse_and_verify,
)

logger = logging.getLogger(__name__)


# ---- Embedded public key ---------------------------------------------------
#
# Generated 2026-05-03. The matching private key lives on the license server
# at ~/.raman-studio-license-server/ed25519-priv.pem (chmod 600) and MUST
# NEVER be committed.
#
# To rotate: generate a new keypair, update both the value below and the
# deployed private key, and bump TOKEN_MAGIC in license_token.py so existing
# v1 tokens stop validating.
LICENSE_PUBLIC_KEY_B64 = (
    "rRymHTtXA/S8RCLuAqp9GV6V92rYLwGeHBiMltDcnxk="
)

# Built-in features when no token exists. Trials get the full set; explicit
# license tokens carry their own ``feat`` array.
TRIAL_FEATURES: list[str] = [
    "eis", "cv", "gcd", "drt", "circuit_fit",
    "battery", "supercap", "biosensor",
    "alchemi", "agent", "literature", "reports",
]

TRIAL_DURATION_S = 30 * 24 * 60 * 60   # 30 days
PBKDF2_ITERS = 600_000


# ---- Status + payload types ---------------------------------------------


class LicenseStatus:
    OK = "ok"
    TRIAL = "trial"
    TRIAL_EXPIRED = "trial_expired"
    INVALID = "invalid"
    EXPIRED = "expired"
    HARDWARE_MISMATCH = "hardware_mismatch"
    NOT_ACTIVATED = "not_activated"


@dataclass
class LicenseInfo:
    status: str
    plan: str
    sub: Optional[str] = None
    expires_at: Optional[int] = None
    days_remaining: Optional[int] = None
    features: list[str] = field(default_factory=list)
    hardware: Optional[str] = None
    degraded_hardware: bool = False
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "plan": self.plan,
            "sub": self.sub,
            "expires_at": self.expires_at,
            "days_remaining": self.days_remaining,
            "features": list(self.features),
            "hardware": self.hardware,
            "degraded_hardware": self.degraded_hardware,
            "message": self.message,
        }


# ---- Storage paths --------------------------------------------------------


def _user_data_dir() -> Path:
    """
    Return the platform-appropriate user data directory.

    Linux:   ~/.local/share/raman-studio/
    macOS:   ~/Library/Application Support/raman-studio/
    Windows: %APPDATA%\\raman-studio\\
    """
    home = Path.home()
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = home / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))
    out = base / "raman-studio"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _state_file() -> Path:
    return _user_data_dir() / "license.dat"


# ---- The manager ----------------------------------------------------------


class LicenseManager:
    """
    Single-instance license state.

    Construction is cheap; nothing reads from disk or computes a
    hardware id until the first method is called.
    """

    def __init__(
        self,
        *,
        public_key_b64: str = LICENSE_PUBLIC_KEY_B64,
        state_path: Optional[Path] = None,
        trial_duration_s: int = TRIAL_DURATION_S,
    ) -> None:
        self._public_key = load_public_key_b64(public_key_b64)
        self._state_path = state_path or _state_file()
        self._trial_duration_s = trial_duration_s
        self._fingerprint: Optional[HardwareFingerprint] = None
        self._cached_state: Optional[dict[str, Any]] = None
        self._cached_token_payload: Optional[LicensePayload] = None

    # ---- Hardware ----------------------------------------------------

    def hardware(self) -> HardwareFingerprint:
        if self._fingerprint is None:
            self._fingerprint = compute_fingerprint()
        return self._fingerprint

    # ---- Encrypted-at-rest state file --------------------------------
    #
    # The key is derived from the hardware id with PBKDF2. This is
    # tamper-evidence, not confidentiality: a sufficiently motivated
    # attacker can run PBKDF2 themselves. What it prevents is:
    #
    # * Casual editing of the JSON-encoded trial-start timestamp.
    # * Accidental commit of the file revealing the structure.
    #
    # The actual security comes from the Ed25519 token signature, which
    # the attacker cannot forge.

    def _file_key(self) -> bytes:
        hw = self.hardware().hex.encode("ascii")
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"raman-studio-state-v1",
            iterations=PBKDF2_ITERS,
        )
        derived = kdf.derive(hw)
        # Fernet wants url-safe base64 of a 32-byte key.
        import base64
        return base64.urlsafe_b64encode(derived)

    def _read_state(self) -> dict[str, Any]:
        if self._cached_state is not None:
            return self._cached_state
        path = self._state_path
        if not path.exists():
            return {}
        try:
            blob = path.read_bytes()
            data = Fernet(self._file_key()).decrypt(blob)
            self._cached_state = json.loads(data.decode("utf-8"))
            return self._cached_state
        except (InvalidToken, ValueError, json.JSONDecodeError) as e:
            logger.warning(
                "License state file is corrupted or from another machine "
                "(%s); resetting.",
                e,
            )
            return {}

    def _write_state(self, state: dict[str, Any]) -> None:
        blob = Fernet(self._file_key()).encrypt(
            json.dumps(state, separators=(",", ":")).encode("utf-8")
        )
        # Atomic write: write to .tmp then rename.
        tmp = self._state_path.with_suffix(".tmp")
        tmp.write_bytes(blob)
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, self._state_path)
        self._cached_state = state

    # ---- Trial -------------------------------------------------------

    def _trial_start(self) -> int:
        state = self._read_state()
        ts = state.get("trial_start")
        if isinstance(ts, int) and ts > 0:
            return ts

        now = int(time.time())
        new_state = dict(state)
        new_state["trial_start"] = now
        self._write_state(new_state)
        return now

    def _trial_seconds_remaining(self) -> int:
        elapsed = int(time.time()) - self._trial_start()
        return max(0, self._trial_duration_s - elapsed)

    # ---- Activate / deactivate --------------------------------------

    def activate_license(self, token: str) -> LicenseInfo:
        """
        Verify ``token`` and store it. Replaces any previous activation.
        """
        token = (token or "").strip()
        if not token:
            return self._info(LicenseStatus.INVALID, plan="none",
                              message="empty token")
        try:
            payload = parse_and_verify(
                token,
                public_key=self._public_key,
                expected_hw=self.hardware().hex,
            )
        except LicenseTokenError as e:
            return self._info(LicenseStatus.INVALID, plan="none",
                              message=str(e))

        state = self._read_state()
        state["token"] = token
        # Clear any cached trial timestamp — once activated, trial is moot.
        state.pop("trial_start", None)
        self._write_state(state)
        self._cached_token_payload = payload

        return self._info(
            LicenseStatus.OK,
            plan=payload.plan,
            sub=payload.sub,
            expires_at=payload.exp,
            features=payload.feat,
            message="license activated",
        )

    def deactivate_license(self) -> None:
        state = self._read_state()
        state.pop("token", None)
        self._write_state(state)
        self._cached_token_payload = None

    # ---- Validate ----------------------------------------------------

    def validate_license(self) -> LicenseInfo:
        """Single source of truth for "what state is the app in?"."""
        state = self._read_state()
        token = state.get("token")

        if isinstance(token, str) and token:
            try:
                payload = parse_and_verify(
                    token,
                    public_key=self._public_key,
                    expected_hw=self.hardware().hex,
                )
                self._cached_token_payload = payload
                return self._info(
                    LicenseStatus.OK,
                    plan=payload.plan,
                    sub=payload.sub,
                    expires_at=payload.exp,
                    features=payload.feat,
                )
            except LicenseTokenError as e:
                msg = str(e).lower()
                if "expired" in msg:
                    status = LicenseStatus.EXPIRED
                elif "different machine" in msg:
                    status = LicenseStatus.HARDWARE_MISMATCH
                else:
                    status = LicenseStatus.INVALID
                return self._info(status, plan="none", message=str(e))

        # No token → trial. Initialise on first call.
        remaining = self._trial_seconds_remaining()
        if remaining <= 0:
            return self._info(
                LicenseStatus.TRIAL_EXPIRED,
                plan="trial",
                message="Trial expired. Activate a license to continue.",
                expires_at=self._trial_start() + self._trial_duration_s,
                features=[],
            )
        return self._info(
            LicenseStatus.TRIAL,
            plan="trial",
            expires_at=self._trial_start() + self._trial_duration_s,
            features=TRIAL_FEATURES,
        )

    def is_feature_enabled(self, feature: str) -> bool:
        info = self.validate_license()
        if info.status not in (LicenseStatus.OK, LicenseStatus.TRIAL):
            return False
        return feature in info.features

    # ---- Helpers ----------------------------------------------------

    def get_license_info(self) -> dict[str, Any]:
        return self.validate_license().to_dict()

    def get_hardware_id(self) -> str:
        return self.hardware().hex

    def _info(
        self,
        status: str,
        *,
        plan: str,
        sub: Optional[str] = None,
        expires_at: Optional[int] = None,
        features: Optional[list[str]] = None,
        message: str = "",
    ) -> LicenseInfo:
        days_remaining: Optional[int] = None
        if expires_at is not None:
            days_remaining = max(0, (expires_at - int(time.time())) // 86400)
        hw = self.hardware()
        return LicenseInfo(
            status=status,
            plan=plan,
            sub=sub,
            expires_at=expires_at,
            days_remaining=days_remaining,
            features=list(features or []),
            hardware=hw.short,
            degraded_hardware=hw.degraded,
            message=message,
        )


# ---- Module-level singleton -------------------------------------------

_singleton: Optional[LicenseManager] = None


def get_license_manager() -> LicenseManager:
    global _singleton
    if _singleton is None:
        _singleton = LicenseManager()
    return _singleton


def reset_license_manager() -> None:
    """For tests."""
    global _singleton
    _singleton = None


# ---- FastAPI dependency ----------------------------------------------


def verify_license(*, required_feature: Optional[str] = None) -> Any:
    """
    Build a FastAPI dependency that 403s if no valid license / trial.

    Usage::

        from src.backend.licensing.license_manager import verify_license
        @app.post("/api/v2/eis/simulate",
                  dependencies=[Depends(verify_license())])
        async def simulate_eis(...): ...

        # Or to require a specific feature:
        @app.post("/api/v2/agent/chat",
                  dependencies=[Depends(verify_license(required_feature="agent"))])

    The dependency does NOT touch the request body; it only checks that
    the install has a valid trial / license. Network is not required.
    """
    from fastapi import HTTPException

    def _dep() -> LicenseInfo:
        mgr = get_license_manager()
        info = mgr.validate_license()
        if info.status not in (LicenseStatus.OK, LicenseStatus.TRIAL):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": info.status,
                    "message": info.message
                    or "License is not valid; activate one to continue.",
                },
            )
        if required_feature and required_feature not in info.features:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "feature_disabled",
                    "message": (
                        f"This plan ({info.plan}) does not include the "
                        f"{required_feature!r} feature."
                    ),
                },
            )
        return info

    return _dep
