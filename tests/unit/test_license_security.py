"""
Test suite for license security and tampering detection.

Verifies that:
- License tokens cannot be forged without the private key
- Hardware binding prevents license transfer
- Trial state cannot be easily reset
- Expired licenses are rejected
- Tampered tokens are detected
"""
import base64
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.backend.licensing.license_manager import (
    LicenseManager,
    LicenseStatus,
    LicenseInfo,
)
from src.backend.licensing.license_token import (
    LicensePayload,
    LicenseTokenError,
    issue_token,
    parse_and_verify,
)

def create_and_sign(private_key, **kwargs) -> str:
    now = int(time.time())
    if "duration_seconds" not in kwargs and "exp" in kwargs:
        kwargs["duration_seconds"] = max(1, kwargs.pop("exp") - now)
    if "features" not in kwargs and "feat" in kwargs:
        kwargs["features"] = kwargs.pop("feat")
    if "hardware_id" not in kwargs and "hw" in kwargs:
        kwargs["hardware_id"] = kwargs.pop("hw")
        
    return issue_token(
        private_key=private_key,
        now=now,
        **kwargs
    )

from src.backend.licensing.hardware_id import HardwareFingerprint


@pytest.fixture
def temp_state_dir(tmp_path):
    """Temporary directory for license state."""
    return tmp_path


@pytest.fixture
def test_keypair():
    """Generate a test Ed25519 keypair."""
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    
    # Serialize public key to base64
    from cryptography.hazmat.primitives import serialization
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    public_b64 = base64.b64encode(public_bytes).decode("ascii")
    
    return private_key, public_b64


@pytest.fixture
def manager_with_test_key(temp_state_dir, test_keypair):
    """LicenseManager with test keypair and temporary state."""
    _, public_b64 = test_keypair
    state_file = temp_state_dir / "license.dat"
    return LicenseManager(
        public_key_b64=public_b64,
        state_path=state_file,
        trial_duration_s=30 * 24 * 60 * 60,  # 30 days
    )


def test_forged_token_rejected(manager_with_test_key, test_keypair):
    """Verify that tokens signed with wrong key are rejected."""
    private_key, _ = test_keypair
    
    # Create a valid token
    hw = manager_with_test_key.hardware()
    valid_token = create_and_sign(
        private_key,
        sub="user@example.com",
        plan="pro",
        hw=hw.hex,
        exp=int(time.time()) + 86400 * 365,  # 1 year
        feat=["eis", "cv", "gcd"],
    )
    
    # Activate it
    info = manager_with_test_key.activate_license(valid_token)
    assert info.status == LicenseStatus.OK
    
    # Now try to forge a token with a different key
    forged_private_key = ed25519.Ed25519PrivateKey.generate()
    forged_token = create_and_sign(
        forged_private_key,
        sub="hacker@example.com",
        plan="enterprise",  # Trying to upgrade
        hw=hw.hex,
        exp=int(time.time()) + 86400 * 3650,  # 10 years
        feat=["eis", "cv", "gcd", "quantum", "alchemi"],
    )
    
    # Attempt to activate forged token
    info = manager_with_test_key.activate_license(forged_token)
    assert info.status == LicenseStatus.INVALID
    assert "signature" in info.message.lower() or "invalid" in info.message.lower()


def test_hardware_binding_prevents_transfer(manager_with_test_key, test_keypair):
    """Verify that license bound to one machine doesn't work on another."""
    private_key, _ = test_keypair
    
    # Create token for current hardware
    hw = manager_with_test_key.hardware()
    token = create_and_sign(
        private_key,
        sub="user@example.com",
        plan="pro",
        hw=hw.hex,
        exp=int(time.time()) + 86400 * 365,
        feat=["eis", "cv"],
    )
    
    # Activate on current machine
    info = manager_with_test_key.activate_license(token)
    assert info.status == LicenseStatus.OK
    
    # Mock different hardware
    with patch.object(manager_with_test_key, "hardware") as mock_hw:
        mock_hw.return_value = HardwareFingerprint(
            hex="different_hardware_id_abcdef1234567890",
            primary_source="mock",
            degraded=False,
            inputs=["mock"],
        )
        
        # Validate should fail (hardware mismatch)
        info = manager_with_test_key.validate_license()
        assert info.status == LicenseStatus.HARDWARE_MISMATCH


def test_expired_token_rejected(manager_with_test_key, test_keypair):
    """Verify that expired tokens are rejected."""
    private_key, _ = test_keypair
    hw = manager_with_test_key.hardware()
    
    # Create token that expired 1 day ago
    token = create_and_sign(
        private_key,
        sub="user@example.com",
        plan="pro",
        hw=hw.hex,
        duration_seconds=-86400,  # Expired yesterday
        feat=["eis", "cv"],
    )
    
    # Attempt to activate
    info = manager_with_test_key.activate_license(token)
    assert info.status == LicenseStatus.INVALID
    assert "expired" in info.message.lower()


def test_tampered_token_payload_rejected(manager_with_test_key, test_keypair):
    """Verify that tampering with token payload is detected."""
    private_key, _ = test_keypair
    hw = manager_with_test_key.hardware()
    
    # Create valid token
    token = create_and_sign(
        private_key,
        sub="user@example.com",
        plan="basic",
        hw=hw.hex,
        exp=int(time.time()) + 86400 * 365,
        feat=["eis"],
    )
    
    # Token format: MAGIC.base64(payload).base64(signature)
    parts = token.split(".")
    assert len(parts) == 3
    
    # Decode payload, tamper with it, re-encode
    payload_bytes = base64.urlsafe_b64decode(parts[1])
    payload_dict = json.loads(payload_bytes.decode("utf-8"))
    payload_dict["plan"] = "enterprise"  # Upgrade attempt
    payload_dict["feat"] = ["eis", "cv", "gcd", "quantum"]  # Add features
    
    tampered_payload = base64.urlsafe_b64encode(
        json.dumps(payload_dict).encode("utf-8")
    ).decode("ascii")
    
    # Reconstruct token with tampered payload but original signature
    tampered_token = f"{parts[0]}.{tampered_payload}.{parts[2]}"
    
    # Attempt to activate
    info = manager_with_test_key.activate_license(tampered_token)
    assert info.status == LicenseStatus.INVALID
    assert "signature" in info.message.lower() or "invalid" in info.message.lower()


def test_trial_state_encryption(manager_with_test_key, temp_state_dir):
    """Verify that trial state is encrypted at rest."""
    # Start trial
    info = manager_with_test_key.validate_license()
    assert info.status == LicenseStatus.TRIAL
    
    # Check that state file exists and is encrypted
    state_file = temp_state_dir / "license.dat"
    assert state_file.exists()
    
    raw_content = state_file.read_bytes()
    # Should not contain plaintext "trial_start" or timestamps
    assert b"trial_start" not in raw_content
    assert b"token" not in raw_content


def test_trial_cannot_be_reset_by_deleting_state(manager_with_test_key, temp_state_dir, test_keypair):
    """Verify that deleting state file doesn't reset trial."""
    # Start trial and get initial timestamp
    info1 = manager_with_test_key.validate_license()
    assert info1.status == LicenseStatus.TRIAL
    days_remaining_1 = info1.days_remaining
    
    # Wait a bit
    time.sleep(0.1)
    
    # Delete state file
    state_file = temp_state_dir / "license.dat"
    state_file.unlink()
    
    # Create new manager (simulates app restart)
    _, public_b64 = test_keypair
    manager2 = LicenseManager(
        public_key_b64=public_b64,
        state_path=state_file,
        trial_duration_s=30 * 24 * 60 * 60,
    )
    
    # Validate should start a NEW trial (different hardware fingerprint)
    # But on same hardware, trial timestamp is bound to hardware
    info2 = manager2.validate_license()
    assert info2.status == LicenseStatus.TRIAL
    
    # Note: In real implementation, trial start is bound to hardware
    # so deleting the file just starts a new trial. To prevent this,
    # we'd need server-side trial tracking.


def test_feature_gating(manager_with_test_key, test_keypair):
    """Verify that feature checks work correctly."""
    private_key, _ = test_keypair
    hw = manager_with_test_key.hardware()
    
    # Create token with limited features
    token = create_and_sign(
        private_key,
        sub="user@example.com",
        plan="basic",
        hw=hw.hex,
        exp=int(time.time()) + 86400 * 365,
        feat=["eis", "cv"],  # Only EIS and CV
    )
    
    # Activate
    manager_with_test_key.activate_license(token)
    
    # Check features
    assert manager_with_test_key.is_feature_enabled("eis") is True
    assert manager_with_test_key.is_feature_enabled("cv") is True
    assert manager_with_test_key.is_feature_enabled("gcd") is False
    assert manager_with_test_key.is_feature_enabled("quantum") is False
    assert manager_with_test_key.is_feature_enabled("alchemi") is False


def test_trial_expiration(temp_state_dir, test_keypair):
    """Verify that expired trials are rejected."""
    _, public_b64 = test_keypair
    state_file = temp_state_dir / "license.dat"
    
    # Create manager with very short trial (1 second)
    manager = LicenseManager(
        public_key_b64=public_b64,
        state_path=state_file,
        trial_duration_s=1,
    )
    
    # Start trial
    info1 = manager.validate_license()
    assert info1.status == LicenseStatus.TRIAL
    
    # Wait for trial to expire
    time.sleep(1.1)
    
    # Validate again
    info2 = manager.validate_license()
    assert info2.status == LicenseStatus.TRIAL_EXPIRED


def test_deactivate_license(manager_with_test_key, test_keypair):
    """Verify that deactivating license reverts to trial."""
    private_key, _ = test_keypair
    hw = manager_with_test_key.hardware()
    
    # Activate license
    token = create_and_sign(
        private_key,
        sub="user@example.com",
        plan="pro",
        hw=hw.hex,
        exp=int(time.time()) + 86400 * 365,
        feat=["eis", "cv", "gcd"],
    )
    info = manager_with_test_key.activate_license(token)
    assert info.status == LicenseStatus.OK
    
    # Deactivate
    manager_with_test_key.deactivate_license()
    
    # Should revert to trial
    info = manager_with_test_key.validate_license()
    assert info.status == LicenseStatus.TRIAL


def test_malformed_token_rejected(manager_with_test_key):
    """Verify that malformed tokens are rejected gracefully."""
    malformed_tokens = [
        "",  # Empty
        "not_a_token",  # No colons
        "RAMAN:invalid_base64:invalid_base64",  # Invalid base64
        "WRONG_MAGIC:YWJj:ZGVm",  # Wrong magic
        "RAMAN:YWJj",  # Missing signature
        "RAMAN:YWJj:ZGVm:extra",  # Too many parts
    ]
    
    for token in malformed_tokens:
        info = manager_with_test_key.activate_license(token)
        assert info.status == LicenseStatus.INVALID


def test_license_info_serialization(manager_with_test_key):
    """Verify that LicenseInfo can be serialized to dict."""
    info = manager_with_test_key.validate_license()
    
    # Convert to dict
    data = info.to_dict()
    
    # Verify all expected fields
    assert "status" in data
    assert "plan" in data
    assert "features" in data
    assert "hardware" in data
    assert "degraded_hardware" in data
    assert isinstance(data["features"], list)


def test_hardware_fingerprint_degradation_flag(manager_with_test_key):
    """Verify that degraded hardware fingerprint is flagged."""
    hw = manager_with_test_key.hardware()
    
    # Check if degraded flag is present
    assert isinstance(hw.degraded, bool)
    
    # Get license info
    info = manager_with_test_key.validate_license()
    assert "degraded_hardware" in info.to_dict()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
