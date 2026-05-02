"""
Secure License Manager for RĀMAN Studio
========================================
Hardware-based licensing with online validation and enhanced security
Company: VidyuthLabs
Pricing: $5/month with 30-day free trial

Honoring Professor CNR Rao's legacy in materials science
"""

import hashlib
import uuid
import platform
import json
import os
import hmac
import subprocess
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import logging
from functools import wraps
from time import time
from collections import defaultdict
import base64

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter to prevent abuse"""
    def __init__(self):
        self.calls = defaultdict(list)
    
    def limit(self, max_calls: int, period: int):
        """Decorator for rate limiting"""
        def decorator(func):
            @wraps(func)
            def wrapper(instance, *args, **kwargs):
                now = time()
                key = f"{func.__name__}"
                
                # Clean old calls
                instance.calls[key] = [t for t in instance.calls[key] if now - t < period]
                
                # Check limit
                if len(instance.calls[key]) >= max_calls:
                    raise Exception(f"Rate limit exceeded: {max_calls} calls per {period}s")
                
                # Record call
                instance.calls[key].append(now)
                
                return func(instance, *args, **kwargs)
            return wrapper
        return decorator


rate_limiter = RateLimiter()


class LicenseStatus:
    """License status constants"""
    VALID = "valid"
    TRIAL = "trial"
    EXPIRED = "expired"
    INVALID = "invalid"
    NO_LICENSE = "no_license"
    OFFLINE_GRACE = "offline_grace"
    REVOKED = "revoked"


class LicenseManager:
    """Secure license manager with enhanced protection"""
    
    # License server URL (VidyuthLabs backend)
    LICENSE_SERVER = "https://license.vidyuthlabs.com/api/v1"
    
    # Local license file
    LICENSE_FILE = Path.home() / ".raman-studio" / "license.enc"
    
    # Offline grace period (7 days)
    OFFLINE_GRACE_DAYS = 7
    
    # Trial period (30 days)
    TRIAL_DAYS = 30
    
    # HMAC secret (in production: load from secure storage)
    HMAC_SECRET = b'vidyuthlabs_raman_studio_hmac_secret_v1'
    
    def __init__(self):
        self.hardware_id = self._generate_hardware_id()
        self.license_data = None
        self.calls = defaultdict(list)  # Rate limiting tracker
        self._ensure_license_dir()
        self._load_license()
        self._check_integrity()
    
    def _ensure_license_dir(self):
        """Ensure license directory exists with proper permissions"""
        self.LICENSE_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # Set restrictive permissions (owner only)
        if platform.system() != "Windows":
            os.chmod(self.LICENSE_FILE.parent, 0o700)
    
    def _generate_hardware_id(self) -> str:
        """Generate unique hardware ID with multiple entropy sources"""
        components = []
        
        # CPU ID
        components.append(platform.processor())
        
        # MAC Address
        mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff)
                       for elements in range(0, 2*6, 2)][::-1])
        components.append(mac)
        
        # System info
        components.append(f"{platform.system()}-{platform.machine()}")
        
        # Platform-specific unique identifiers
        if platform.system() == "Windows":
            # Motherboard UUID
            try:
                result = subprocess.run(
                    ["wmic", "csproduct", "get", "UUID"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    components.append(lines[1].strip())
            except:
                pass
            
            # Disk serial
            try:
                result = subprocess.run(
                    ["wmic", "diskdrive", "get", "SerialNumber"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    components.append(lines[1].strip())
            except:
                pass
        
        elif platform.system() == "Linux":
            # DMI UUID
            try:
                with open('/sys/class/dmi/id/product_uuid', 'r') as f:
                    components.append(f.read().strip())
            except:
                pass
            
            # Machine ID
            try:
                with open('/etc/machine-id', 'r') as f:
                    components.append(f.read().strip())
            except:
                pass
        
        # Combine and hash
        combined = '-'.join(filter(None, components))
        hardware_hash = hashlib.sha256(combined.encode()).hexdigest()
        
        return hardware_hash[:32]
    
    def _get_encryption_key(self) -> bytes:
        """Generate encryption key from hardware ID with high iteration count"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'vidyuthlabs_raman_studio_2026_v2',
            iterations=500000,  # Increased from 100k
        )
        key = kdf.derive(self.hardware_id.encode())
        return base64.urlsafe_b64encode(key)
    
    def _encrypt_data(self, data: Dict) -> bytes:
        """Encrypt license data with HMAC for integrity"""
        key = self._get_encryption_key()
        f = Fernet(key)
        json_data = json.dumps(data).encode()
        encrypted = f.encrypt(json_data)
        
        # Add HMAC for integrity
        mac = hmac.new(self.HMAC_SECRET, encrypted, hashlib.sha256).digest()
        
        return mac + b'::' + encrypted
    
    def _decrypt_data(self, encrypted_with_mac: bytes) -> Optional[Dict]:
        """Decrypt license data and verify integrity"""
        try:
            # Split MAC and encrypted data
            mac, encrypted = encrypted_with_mac.split(b'::', 1)
            
            # Verify HMAC
            expected_mac = hmac.new(self.HMAC_SECRET, encrypted, hashlib.sha256).digest()
            if not hmac.compare_digest(mac, expected_mac):
                logger.error("License file integrity check failed")
                return None
            
            # Decrypt
            key = self._get_encryption_key()
            f = Fernet(key)
            decrypted = f.decrypt(encrypted)
            return json.loads(decrypted.decode())
        except Exception as e:
            logger.error(f"Failed to decrypt license: {e}")
            return None
    
    def _load_license(self):
        """Load license from disk"""
        if not self.LICENSE_FILE.exists():
            logger.info("No license file found")
            return
        
        try:
            with open(self.LICENSE_FILE, 'rb') as f:
                encrypted = f.read()
            
            self.license_data = self._decrypt_data(encrypted)
            
            if self.license_data:
                logger.info("✅ License loaded successfully")
            else:
                logger.warning("⚠️  Failed to decrypt license or integrity check failed")
        except Exception as e:
            logger.error(f"Failed to load license: {e}")
    
    def _save_license(self):
        """Save license to disk with proper permissions"""
        if not self.license_data:
            return
        
        try:
            encrypted = self._encrypt_data(self.license_data)
            
            # Write atomically
            temp_file = self.LICENSE_FILE.with_suffix('.tmp')
            with open(temp_file, 'wb') as f:
                f.write(encrypted)
            
            # Set restrictive permissions before moving
            if platform.system() != "Windows":
                os.chmod(temp_file, 0o600)
            
            # Atomic rename
            temp_file.replace(self.LICENSE_FILE)
            
            logger.info("💾 License saved securely")
        except Exception as e:
            logger.error(f"Failed to save license: {e}")
    
    def _check_integrity(self):
        """Check for tampering"""
        # Check if running in debugger
        if self._is_debugger_present():
            logger.warning("⚠️  Debugger detected")
            # In production: exit or disable features
    
    def _is_debugger_present(self) -> bool:
        """Detect if debugger is attached"""
        try:
            if platform.system() == 'Windows':
                import ctypes
                return ctypes.windll.kernel32.IsDebuggerPresent() != 0
        except:
            pass
        return False
    
    def _constant_time_compare(self, a: str, b: str) -> bool:
        """Constant-time string comparison to prevent timing attacks"""
        return hmac.compare_digest(a.encode(), b.encode())
    
    @rate_limiter.limit(max_calls=3, period=3600)  # 3 trials per hour
    def start_trial(self) -> bool:
        """Start 30-day free trial with rate limiting"""
        if self.license_data and self.license_data.get('type') != 'trial':
            logger.warning("Cannot start trial - license already exists")
            return False
        
        now = datetime.now()
        trial_end = now + timedelta(days=self.TRIAL_DAYS)
        
        self.license_data = {
            'type': 'trial',
            'hardware_id': self.hardware_id,
            'start_date': now.isoformat(),
            'end_date': trial_end.isoformat(),
            'features': ['all'],
            'company': 'VidyuthLabs',
            'product': 'RĀMAN Studio',
            'version': '1.0.0',
            'integrity_hash': self._compute_integrity_hash()
        }
        
        self._save_license()
        logger.info(f"🎉 Trial started - expires {trial_end.strftime('%Y-%m-%d')}")
        return True
    
    def _compute_integrity_hash(self) -> str:
        """Compute integrity hash of license data"""
        if not self.license_data:
            return ""
        
        # Create deterministic string from license data
        data_str = json.dumps(self.license_data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()
    
    def _validate_online(self, license_key: str) -> Tuple[Optional[bool], Dict]:
        """Validate license with VidyuthLabs server"""
        try:
            import requests
            
            # Create signature
            timestamp = str(int(datetime.now().timestamp()))
            message = f"{license_key}-{self.hardware_id}-{timestamp}"
            signature = hmac.new(
                self.HMAC_SECRET,
                message.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Send validation request
            response = requests.post(
                f"{self.LICENSE_SERVER}/validate",
                json={
                    'license_key': license_key,
                    'hardware_id': self.hardware_id,
                    'timestamp': timestamp,
                    'signature': signature,
                    'product': 'raman-studio',
                    'version': '1.0.0'
                },
                timeout=10,
                headers={'User-Agent': 'RAMAN-Studio/1.0.0'}
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Verify response signature
                response_sig = data.get('signature')
                license_data = data.get('license_data', {})
                expected_sig = hmac.new(
                    self.HMAC_SECRET,
                    json.dumps(license_data, sort_keys=True).encode(),
                    hashlib.sha256
                ).hexdigest()
                
                if not hmac.compare_digest(response_sig, expected_sig):
                    return False, {'error': 'Invalid signature'}
                
                return True, license_data
            elif response.status_code == 403:
                return False, {'error': 'revoked', 'message': 'License has been revoked'}
            else:
                return False, {'error': 'validation_failed'}
                
        except requests.exceptions.Timeout:
            # Allow offline grace period
            return None, {'error': 'timeout'}
        except requests.exceptions.RequestException as e:
            logger.error(f"Online validation error: {e}")
            return None, {'error': 'network_error'}
        except Exception as e:
            logger.error(f"Unexpected validation error: {e}")
            return False, {'error': str(e)}
    
    @rate_limiter.limit(max_calls=5, period=60)  # 5 activations per minute
    def activate_license(self, license_key: str) -> Tuple[bool, str]:
        """Activate license with key from VidyuthLabs"""
        try:
            # Validate format
            parts = license_key.strip().upper().split('-')
            if len(parts) != 5 or parts[0] != 'VIDYUTH':
                return False, "Invalid license key format"
            
            # Validate online
            success, data = self._validate_online(license_key)
            
            if success is False:
                if data.get('error') == 'revoked':
                    return False, "License has been revoked"
                return False, "License validation failed"
            
            if success is None:
                # Offline - cannot activate
                return False, "Cannot activate license offline. Please connect to internet."
            
            # Create license data
            now = datetime.now()
            subscription_end = now + timedelta(days=30)  # Monthly subscription
            
            self.license_data = {
                'type': 'subscription',
                'license_key': license_key,
                'hardware_id': self.hardware_id,
                'activation_date': now.isoformat(),
                'subscription_end': subscription_end.isoformat(),
                'features': data.get('features', ['all', 'gpu', 'projects', 'export']),
                'company': 'VidyuthLabs',
                'product': 'RĀMAN Studio',
                'version': '1.0.0',
                'price': '$5/month',
                'last_validation': now.isoformat(),
                'integrity_hash': ''
            }
            
            self.license_data['integrity_hash'] = self._compute_integrity_hash()
            
            self._save_license()
            logger.info("✅ License activated successfully")
            return True, "License activated successfully"
            
        except Exception as e:
            logger.error(f"License activation failed: {e}")
            return False, f"Activation failed: {str(e)}"
    
    @rate_limiter.limit(max_calls=10, period=60)  # 10 validations per minute
    def validate_license(self, online: bool = True) -> Tuple[str, Dict]:
        """
        Validate current license with enhanced security
        Returns: (status, details)
        """
        if not self.license_data:
            return LicenseStatus.NO_LICENSE, {
                'message': 'No license found. Start free trial or activate license.',
                'trial_available': True
            }
        
        # Check integrity
        expected_hash = self.license_data.pop('integrity_hash', '')
        current_hash = self._compute_integrity_hash()
        self.license_data['integrity_hash'] = expected_hash
        
        if expected_hash and not hmac.compare_digest(expected_hash, current_hash):
            logger.error("License integrity check failed - possible tampering")
            return LicenseStatus.INVALID, {
                'message': 'License file has been tampered with',
                'error': 'integrity_failed'
            }
        
        now = datetime.now()
        license_type = self.license_data.get('type')
        
        # Check hardware ID with constant-time comparison
        if not self._constant_time_compare(
            self.license_data.get('hardware_id', ''),
            self.hardware_id
        ):
            return LicenseStatus.INVALID, {
                'message': 'License is bound to different hardware',
                'error': 'hardware_mismatch'
            }
        
        # Check trial license
        if license_type == 'trial':
            end_date = datetime.fromisoformat(self.license_data['end_date'])
            days_remaining = (end_date - now).days
            
            if now > end_date:
                return LicenseStatus.EXPIRED, {
                    'message': 'Trial period expired',
                    'expired_date': end_date.isoformat(),
                    'upgrade_url': 'https://vidyuthlabs.co.in/raman-studio/subscribe'
                }
            
            return LicenseStatus.TRIAL, {
                'message': f'Trial active - {days_remaining} days remaining',
                'days_remaining': days_remaining,
                'end_date': end_date.isoformat(),
                'features': self.license_data.get('features', [])
            }
        
        # Check subscription license
        if license_type == 'subscription':
            subscription_end = datetime.fromisoformat(self.license_data['subscription_end'])
            days_remaining = (subscription_end - now).days
            
            # Check if online validation is needed
            last_validation = datetime.fromisoformat(
                self.license_data.get('last_validation', now.isoformat())
            )
            days_since_validation = (now - last_validation).days
            
            # Perform online validation if needed
            if online and days_since_validation > 1:  # Validate daily
                license_key = self.license_data.get('license_key')
                success, data = self._validate_online(license_key)
                
                if success is False:
                    if data.get('error') == 'revoked':
                        return LicenseStatus.REVOKED, {
                            'message': 'License has been revoked',
                            'error': 'revoked'
                        }
                    return LicenseStatus.INVALID, {
                        'message': 'License validation failed',
                        'error': data.get('error')
                    }
                
                if success is True:
                    # Update last validation
                    self.license_data['last_validation'] = now.isoformat()
                    self._save_license()
            
            # Offline grace period
            if days_since_validation > self.OFFLINE_GRACE_DAYS:
                return LicenseStatus.OFFLINE_GRACE, {
                    'message': 'Offline grace period expired - please connect to internet',
                    'days_since_validation': days_since_validation,
                    'grace_days_remaining': 0
                }
            
            # Check subscription status
            if now > subscription_end:
                return LicenseStatus.EXPIRED, {
                    'message': 'Subscription expired',
                    'expired_date': subscription_end.isoformat(),
                    'renew_url': 'https://vidyuthlabs.co.in/raman-studio/renew'
                }
            
            return LicenseStatus.VALID, {
                'message': 'License valid',
                'license_key': self.license_data.get('license_key', 'N/A')[:20] + '...',  # Partial key only
                'subscription_end': subscription_end.isoformat(),
                'days_remaining': days_remaining,
                'features': self.license_data.get('features', []),
                'price': self.license_data.get('price', '$5/month')
            }
        
        return LicenseStatus.INVALID, {
            'message': 'Unknown license type',
            'error': 'invalid_type'
        }
    
    def get_hardware_id(self) -> str:
        """Get hardware ID for license activation"""
        return self.hardware_id
    
    def get_license_info(self) -> Dict:
        """Get comprehensive license information"""
        status, details = self.validate_license(online=False)
        
        return {
            'status': status,
            'hardware_id': self.hardware_id[:16] + '...',  # Partial ID only
            'details': details,
            'company': 'VidyuthLabs',
            'product': 'RĀMAN Studio',
            'version': '1.0.0',
            'support_email': 'support@vidyuthlabs.co.in',
            'website': 'https://vidyuthlabs.co.in'
        }
    
    def is_feature_enabled(self, feature: str) -> bool:
        """Check if a feature is enabled in current license"""
        status, details = self.validate_license(online=False)
        
        if status in [LicenseStatus.VALID, LicenseStatus.TRIAL]:
            features = details.get('features', [])
            return 'all' in features or feature in features
        
        return False
    
    def deactivate_license(self):
        """Deactivate and securely remove license"""
        if self.LICENSE_FILE.exists():
            # Overwrite with random data before deleting
            with open(self.LICENSE_FILE, 'wb') as f:
                f.write(os.urandom(self.LICENSE_FILE.stat().st_size))
            self.LICENSE_FILE.unlink()
        
        self.license_data = None
        logger.info("🔓 License deactivated securely")


# Global license manager instance
_license_manager = None


def get_license_manager() -> LicenseManager:
    """Get global license manager instance"""
    global _license_manager
    if _license_manager is None:
        _license_manager = LicenseManager()
    return _license_manager


if __name__ == "__main__":
    # Test license manager
    logging.basicConfig(level=logging.INFO)
    
    manager = get_license_manager()
    print("\n" + "=" * 60)
    print("SECURE LICENSE MANAGER TEST")
    print("=" * 60)
    
    print(f"\n🔑 Hardware ID: {manager.get_hardware_id()}")
    
    info = manager.get_license_info()
    print(f"\n📊 License Info:")
    print(f"   Status: {info['status']}")
    print(f"   Product: {info['product']}")
    print(f"   Company: {info['company']}")
    
    if info['status'] == LicenseStatus.NO_LICENSE:
        print(f"\n🎁 Starting trial...")
        try:
            manager.start_trial()
            info = manager.get_license_info()
            print(f"   Status: {info['status']}")
            print(f"   Details: {info['details']}")
        except Exception as e:
            print(f"   Error: {e}")
    
    print("\n✅ Secure License Manager initialized successfully")
