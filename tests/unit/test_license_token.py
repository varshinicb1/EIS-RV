"""
Ed25519 license-token round trip + tamper detection.

These tests do NOT touch disk; they generate a fresh keypair per test and
exercise ``issue_token`` / ``parse_and_verify`` directly. The on-disk
license manager is covered separately in tests of LicenseManager.
"""
import time

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.backend.licensing.license_token import (
    LicensePayload,
    LicenseTokenError,
    TOKEN_MAGIC,
    issue_token,
    parse_and_verify,
)


def _kp():
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    return priv, pub


def test_round_trip_valid_token():
    priv, pub = _kp()
    tok = issue_token(
        private_key=priv,
        sub="user@vidyuthlabs.co.in",
        plan="pro",
        hardware_id="abc123",
        duration_seconds=86_400,
        features=["alchemi", "lab_data"],
    )
    parts = tok.split(".")
    assert len(parts) == 3
    assert parts[0] == TOKEN_MAGIC

    payload = parse_and_verify(tok, public_key=pub, expected_hw="abc123")
    assert isinstance(payload, LicensePayload)
    assert payload.sub == "user@vidyuthlabs.co.in"
    assert payload.plan == "pro"
    assert payload.hw == "abc123"
    assert "alchemi" in payload.feat
    assert payload.exp > payload.iat


def test_signature_tampered_token_rejected():
    priv, pub = _kp()
    tok = issue_token(
        private_key=priv, sub="x", plan="pro", hardware_id="hw1",
        duration_seconds=3600, features=[],
    )
    magic, body, sig = tok.split(".")
    # Flip a single base64 character in the signature
    new_sig = ("A" if sig[0] != "A" else "B") + sig[1:]
    bad = f"{magic}.{body}.{new_sig}"
    with pytest.raises(LicenseTokenError):
        parse_and_verify(bad, public_key=pub, expected_hw="hw1")


def test_payload_tampered_token_rejected():
    """If anyone re-encodes the payload (e.g. to extend exp), signature breaks."""
    priv, pub = _kp()
    tok = issue_token(
        private_key=priv, sub="x", plan="trial", hardware_id="hw1",
        duration_seconds=3600, features=[],
    )
    magic, body, sig = tok.split(".")
    # Replace a byte in the body
    new_body = body[:-1] + ("A" if body[-1] != "A" else "B")
    bad = f"{magic}.{new_body}.{sig}"
    with pytest.raises(LicenseTokenError):
        parse_and_verify(bad, public_key=pub, expected_hw="hw1")


def test_wrong_public_key_rejected():
    priv, _ = _kp()
    _, pub2 = _kp()
    tok = issue_token(
        private_key=priv, sub="x", plan="pro", hardware_id="hw1",
        duration_seconds=3600, features=[],
    )
    with pytest.raises(LicenseTokenError):
        parse_and_verify(tok, public_key=pub2, expected_hw="hw1")


def test_hardware_mismatch_rejected():
    priv, pub = _kp()
    tok = issue_token(
        private_key=priv, sub="x", plan="pro", hardware_id="machineA",
        duration_seconds=3600, features=[],
    )
    with pytest.raises(LicenseTokenError):
        parse_and_verify(tok, public_key=pub, expected_hw="machineB")


def test_expired_token_rejected():
    priv, pub = _kp()
    # Token that expired 1 hour ago
    now = int(time.time())
    tok = issue_token(
        private_key=priv, sub="x", plan="pro", hardware_id="hw1",
        duration_seconds=3600, features=[],
        now=now - 7200,  # issued 2h ago, expires 1h ago
    )
    with pytest.raises(LicenseTokenError):
        parse_and_verify(tok, public_key=pub, expected_hw="hw1")


def test_clock_skew_tolerance():
    """Within allow_clock_skew_s, almost-expired tokens are still accepted."""
    priv, pub = _kp()
    now = int(time.time())
    # Expires 30s in the past — within default 60s skew
    tok = issue_token(
        private_key=priv, sub="x", plan="pro", hardware_id="hw1",
        duration_seconds=60, features=[],
        now=now - 90,  # iat=now-90, exp=now-30
    )
    payload = parse_and_verify(
        tok, public_key=pub, expected_hw="hw1", allow_clock_skew_s=60,
    )
    assert payload.sub == "x"


def test_wrong_magic_rejected():
    priv, pub = _kp()
    tok = issue_token(
        private_key=priv, sub="x", plan="pro", hardware_id="hw1",
        duration_seconds=3600, features=[],
    )
    bogus = "RMNS9." + tok.split(".", 1)[1]
    with pytest.raises(LicenseTokenError):
        parse_and_verify(bogus, public_key=pub, expected_hw="hw1")


def test_malformed_token_rejected():
    _, pub = _kp()
    for bad in ["", "abc", "RMNS1.x", "...", "RMNS1.x.y.z"]:
        with pytest.raises(LicenseTokenError):
            parse_and_verify(bad, public_key=pub, expected_hw="hw1")
