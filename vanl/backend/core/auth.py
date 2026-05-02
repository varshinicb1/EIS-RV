"""
Authentication & Authorization
===============================
JWT-based authentication with bcrypt password hashing.

Author: VidyuthLabs
Date: May 1, 2026
"""

import os
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict
import logging

# JWT and password hashing
try:
    from jose import JWTError, jwt
    from passlib.context import CryptContext
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False
    logging.warning("JWT libraries not installed - authentication disabled")

logger = logging.getLogger(__name__)

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours

# Password hashing context
if JWT_AVAILABLE:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
else:
    pwd_context = None


def hash_password(password: str) -> str:
    """
    Hash password using bcrypt.
    
    Args:
        password: Plain text password
    
    Returns:
        Hashed password
    """
    if not JWT_AVAILABLE:
        raise RuntimeError("JWT libraries not installed")
    
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify password against hash.
    
    Args:
        plain_password: Plain text password
        hashed_password: Hashed password from database
    
    Returns:
        True if password matches, False otherwise
    """
    if not JWT_AVAILABLE:
        raise RuntimeError("JWT libraries not installed")
    
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token.
    
    Args:
        data: Data to encode in token (user_id, email, role, etc.)
        expires_delta: Token expiration time
    
    Returns:
        JWT token string
    """
    if not JWT_AVAILABLE:
        raise RuntimeError("JWT libraries not installed")
    
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict]:
    """
    Decode JWT access token.
    
    Args:
        token: JWT token string
    
    Returns:
        Decoded token data or None if invalid
    """
    if not JWT_AVAILABLE:
        raise RuntimeError("JWT libraries not installed")
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        logger.error(f"JWT decode error: {e}")
        return None


def create_api_key() -> tuple[str, str]:
    """
    Create API key for automation.
    
    Returns:
        Tuple of (api_key, api_key_hash)
    """
    import secrets
    
    # Generate random API key
    api_key = f"raman_{secrets.token_urlsafe(32)}"
    
    # Hash for storage
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    return api_key, api_key_hash


def verify_api_key(api_key: str, api_key_hash: str) -> bool:
    """
    Verify API key against hash.
    
    Args:
        api_key: Plain API key
        api_key_hash: Hashed API key from database
    
    Returns:
        True if API key matches, False otherwise
    """
    computed_hash = hashlib.sha256(api_key.encode()).hexdigest()
    return computed_hash == api_key_hash


def create_audit_signature(data: dict) -> str:
    """
    Create tamper-proof signature for audit log entry.
    
    Uses HMAC-SHA256 to create signature that can detect tampering.
    
    Args:
        data: Audit log data
    
    Returns:
        Signature string
    """
    import hmac
    import json
    
    # Convert data to canonical JSON string
    canonical = json.dumps(data, sort_keys=True)
    
    # Create HMAC signature
    signature = hmac.new(
        SECRET_KEY.encode(),
        canonical.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return signature


def verify_audit_signature(data: dict, signature: str) -> bool:
    """
    Verify audit log signature.
    
    Args:
        data: Audit log data
        signature: Signature to verify
    
    Returns:
        True if signature is valid, False otherwise
    """
    expected_signature = create_audit_signature(data)
    return hmac.compare_digest(expected_signature, signature)


# Role-based access control (RBAC)

ROLE_PERMISSIONS = {
    "admin": {
        "workspaces": ["create", "read", "update", "delete"],
        "projects": ["create", "read", "update", "delete"],
        "experiments": ["create", "read", "update", "delete"],
        "users": ["create", "read", "update", "delete"],
        "audit_logs": ["read"],
        "api_keys": ["create", "read", "delete"]
    },
    "analyst": {
        "workspaces": ["read"],
        "projects": ["create", "read", "update"],
        "experiments": ["create", "read", "update", "delete"],
        "users": ["read"],
        "audit_logs": [],
        "api_keys": ["create", "read", "delete"]
    },
    "viewer": {
        "workspaces": ["read"],
        "projects": ["read"],
        "experiments": ["read"],
        "users": [],
        "audit_logs": [],
        "api_keys": []
    }
}


def has_permission(role: str, resource: str, action: str) -> bool:
    """
    Check if role has permission for action on resource.
    
    Args:
        role: User role (admin, analyst, viewer)
        resource: Resource type (workspaces, projects, experiments, etc.)
        action: Action (create, read, update, delete)
    
    Returns:
        True if permission granted, False otherwise
    """
    if role not in ROLE_PERMISSIONS:
        return False
    
    if resource not in ROLE_PERMISSIONS[role]:
        return False
    
    return action in ROLE_PERMISSIONS[role][resource]


def check_permission(role: str, resource: str, action: str):
    """
    Check permission and raise exception if denied.
    
    Args:
        role: User role
        resource: Resource type
        action: Action
    
    Raises:
        PermissionError: If permission denied
    """
    if not has_permission(role, resource, action):
        raise PermissionError(
            f"Role '{role}' does not have permission to '{action}' on '{resource}'"
        )


# Password strength validation

def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validate password strength.
    
    Requirements:
    - At least 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    
    Args:
        password: Password to validate
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit"
    
    special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    if not any(c in special_chars for c in password):
        return False, "Password must contain at least one special character"
    
    return True, ""


# Email validation

def validate_email(email: str) -> bool:
    """
    Validate email format.
    
    Args:
        email: Email address
    
    Returns:
        True if valid, False otherwise
    """
    import re
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None
