"""
Authentication API Routes
==========================
User registration, login, logout, and profile management.

Author: VidyuthLabs
Date: May 1, 2026
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta
import logging

from vanl.backend.core.database import get_db
from vanl.backend.core.models import User, AuditLog, APIKey
from vanl.backend.core.auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    validate_password_strength,
    validate_email,
    create_audit_signature,
    create_api_key,
    verify_api_key
)

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/auth", tags=["authentication"])

# Security scheme
security = HTTPBearer()


# ===================================================================
#  Request/Response Models
# ===================================================================

class RegisterRequest(BaseModel):
    """User registration request."""
    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., min_length=8, description="Password (min 8 chars)")
    full_name: str = Field(..., min_length=1, description="Full name")
    role: str = Field("analyst", description="User role (admin, analyst, viewer)")


class LoginRequest(BaseModel):
    """User login request."""
    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., description="Password")


class TokenResponse(BaseModel):
    """Authentication token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400  # 24 hours in seconds
    user: dict


class UserResponse(BaseModel):
    """User profile response."""
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: str
    last_login: Optional[str] = None


class UpdateProfileRequest(BaseModel):
    """Update user profile request."""
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None


class ChangePasswordRequest(BaseModel):
    """Change password request."""
    current_password: str
    new_password: str = Field(..., min_length=8)


# ===================================================================
#  Helper Functions
# ===================================================================

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current authenticated user from JWT token.
    
    Args:
        credentials: HTTP Bearer token
        db: Database session
    
    Returns:
        User object
    
    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials
    
    # Decode token
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )
    
    # Get user from database
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    return user


def log_audit(
    db: Session,
    user: User,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None
):
    """
    Log audit trail entry.
    
    Args:
        db: Database session
        user: User performing action
        action: Action type (CREATE, READ, UPDATE, DELETE)
        resource_type: Resource type (user, workspace, etc.)
        resource_id: Resource ID
        details: Additional details
        ip_address: User's IP address
    """
    # Create audit log entry
    audit_data = {
        "user_id": str(user.id),
        "user_email": user.email,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "details": details or {},
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Create signature
    signature = create_audit_signature(audit_data)
    
    # Save to database
    audit_log = AuditLog(
        user_id=user.id,
        user_email=user.email,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
        signature=signature
    )
    
    db.add(audit_log)
    db.commit()


# ===================================================================
#  API Endpoints
# ===================================================================

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """
    Register new user account.
    
    **Example Request:**
    ```json
    {
        "email": "scientist@example.com",
        "password": "SecurePass123!",
        "full_name": "Dr. Jane Smith",
        "role": "analyst"
    }
    ```
    
    **Example Response:**
    ```json
    {
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "token_type": "bearer",
        "expires_in": 86400,
        "user": {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "email": "scientist@example.com",
            "full_name": "Dr. Jane Smith",
            "role": "analyst"
        }
    }
    ```
    """
    try:
        # Validate email
        if not validate_email(request.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email format"
            )
        
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == request.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Validate password strength
        is_valid, error_msg = validate_password_strength(request.password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        
        # Validate role
        valid_roles = ["admin", "analyst", "viewer"]
        if request.role not in valid_roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}"
            )
        
        # Hash password
        password_hash = hash_password(request.password)
        
        # Create user
        user = User(
            email=request.email,
            password_hash=password_hash,
            full_name=request.full_name,
            role=request.role,
            is_active=True
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Log audit trail
        log_audit(
            db=db,
            user=user,
            action="CREATE",
            resource_type="user",
            resource_id=str(user.id),
            details={"email": user.email, "role": user.role}
        )
        
        # Create access token
        token_data = {
            "user_id": str(user.id),
            "email": user.email,
            "role": user.role
        }
        access_token = create_access_token(token_data)
        
        logger.info(f"User registered: {user.email}")
        
        return TokenResponse(
            access_token=access_token,
            user=user.to_dict()
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    Login with email and password.
    
    **Example Request:**
    ```json
    {
        "email": "scientist@example.com",
        "password": "SecurePass123!"
    }
    ```
    """
    try:
        # Find user
        user = db.query(User).filter(User.email == request.email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive"
            )
        
        # Verify password
        if not verify_password(request.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Update last login
        user.last_login = datetime.utcnow()
        db.commit()
        
        # Log audit trail
        log_audit(
            db=db,
            user=user,
            action="LOGIN",
            resource_type="user",
            resource_id=str(user.id)
        )
        
        # Create access token
        token_data = {
            "user_id": str(user.id),
            "email": user.email,
            "role": user.role
        }
        access_token = create_access_token(token_data)
        
        logger.info(f"User logged in: {user.email}")
        
        return TokenResponse(
            access_token=access_token,
            user=user.to_dict()
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user profile.
    
    Requires authentication token in Authorization header:
    ```
    Authorization: Bearer <token>
    ```
    """
    return UserResponse(**current_user.to_dict())


@router.put("/me", response_model=UserResponse)
async def update_profile(
    request: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update current user profile.
    
    **Example Request:**
    ```json
    {
        "full_name": "Dr. Jane Smith, PhD",
        "email": "jane.smith@example.com"
    }
    ```
    """
    try:
        old_values = {}
        new_values = {}
        
        # Update full name
        if request.full_name is not None:
            old_values["full_name"] = current_user.full_name
            current_user.full_name = request.full_name
            new_values["full_name"] = request.full_name
        
        # Update email
        if request.email is not None:
            # Validate email
            if not validate_email(request.email):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid email format"
                )
            
            # Check if email is already taken
            existing_user = db.query(User).filter(
                User.email == request.email,
                User.id != current_user.id
            ).first()
            
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already in use"
                )
            
            old_values["email"] = current_user.email
            current_user.email = request.email
            new_values["email"] = request.email
        
        db.commit()
        db.refresh(current_user)
        
        # Log audit trail
        log_audit(
            db=db,
            user=current_user,
            action="UPDATE",
            resource_type="user",
            resource_id=str(current_user.id),
            details={"old_values": old_values, "new_values": new_values}
        )
        
        logger.info(f"User profile updated: {current_user.email}")
        
        return UserResponse(**current_user.to_dict())
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Profile update failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Profile update failed"
        )


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Change user password.
    
    **Example Request:**
    ```json
    {
        "current_password": "OldPass123!",
        "new_password": "NewPass456!"
    }
    ```
    """
    try:
        # Verify current password
        if not verify_password(request.current_password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect"
            )
        
        # Validate new password strength
        is_valid, error_msg = validate_password_strength(request.new_password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        
        # Hash new password
        new_password_hash = hash_password(request.new_password)
        
        # Update password
        current_user.password_hash = new_password_hash
        db.commit()
        
        # Log audit trail
        log_audit(
            db=db,
            user=current_user,
            action="UPDATE",
            resource_type="user",
            resource_id=str(current_user.id),
            details={"action": "password_changed"}
        )
        
        logger.info(f"Password changed: {current_user.email}")
        
        return {"message": "Password changed successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password change failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed"
        )


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Logout current user.
    
    Note: JWT tokens are stateless, so logout is client-side only.
    The client should discard the token.
    """
    # Log audit trail
    log_audit(
        db=db,
        user=current_user,
        action="LOGOUT",
        resource_type="user",
        resource_id=str(current_user.id)
    )
    
    logger.info(f"User logged out: {current_user.email}")
    
    return {"message": "Logged out successfully"}


@router.delete("/me")
async def delete_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete current user account.
    
    WARNING: This action cannot be undone!
    """
    try:
        # Log audit trail before deletion
        log_audit(
            db=db,
            user=current_user,
            action="DELETE",
            resource_type="user",
            resource_id=str(current_user.id),
            details={"email": current_user.email}
        )
        
        # Soft delete (set is_active to False)
        current_user.is_active = False
        db.commit()
        
        logger.info(f"User account deleted: {current_user.email}")
        
        return {"message": "Account deleted successfully"}
    
    except Exception as e:
        logger.error(f"Account deletion failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Account deletion failed"
        )


# ===================================================================
#  Health Check
# ===================================================================

@router.get("/health")
async def health_check():
    """Health check endpoint for authentication module."""
    return {
        "status": "healthy",
        "module": "authentication",
        "features": [
            "registration",
            "login",
            "profile_management",
            "password_change",
            "logout",
            "account_deletion"
        ]
    }


# ===================================================================
#  API Key Management
# ===================================================================

class CreateAPIKeyRequest(BaseModel):
    """Create API key request."""
    name: str = Field(..., min_length=1, max_length=255, description="API key name")
    scopes: list[str] = Field(default_factory=list, description="API key scopes/permissions")
    expires_in_days: Optional[int] = Field(None, description="Expiration in days (None = never)")


class APIKeyResponse(BaseModel):
    """API key response."""
    id: str
    name: str
    key: str  # Only returned on creation
    scopes: list[str]
    created_at: str
    expires_at: Optional[str]


class APIKeyListResponse(BaseModel):
    """API key list response (without actual key)."""
    id: str
    name: str
    scopes: list[str]
    is_active: bool
    last_used: Optional[str]
    created_at: str
    expires_at: Optional[str]


@router.post("/api-keys", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key_endpoint(
    request: CreateAPIKeyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create API key for automation.
    
    **Scopes** (permissions):
    - `experiments:read` - Read experiments
    - `experiments:write` - Create/update experiments
    - `batch:execute` - Execute batch jobs
    - `reports:generate` - Generate reports
    - `*` - All permissions (admin only)
    
    **Example:**
    ```bash
    curl -X POST http://localhost:8001/api/auth/api-keys \
      -H "Authorization: Bearer YOUR_JWT_TOKEN" \
      -H "Content-Type: application/json" \
      -d '{
        "name": "CI/CD Pipeline",
        "scopes": ["experiments:read", "batch:execute"],
        "expires_in_days": 365
      }'
    ```
    """
    try:
        # Generate API key
        api_key, key_hash = create_api_key()
        
        # Calculate expiration
        expires_at = None
        if request.expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=request.expires_in_days)
        
        # Create API key record
        api_key_record = APIKey(
            user_id=current_user.id,
            name=request.name,
            key_hash=key_hash,
            scopes=request.scopes,
            expires_at=expires_at
        )
        
        db.add(api_key_record)
        db.commit()
        db.refresh(api_key_record)
        
        # Log audit trail
        log_audit(
            db=db,
            user=current_user,
            action="CREATE",
            resource_type="api_key",
            resource_id=str(api_key_record.id),
            details={
                "name": request.name,
                "scopes": request.scopes,
                "expires_in_days": request.expires_in_days
            }
        )
        
        logger.info(f"API key created: {request.name} by {current_user.email}")
        
        return APIKeyResponse(
            id=str(api_key_record.id),
            name=api_key_record.name,
            key=api_key,  # Only returned on creation!
            scopes=api_key_record.scopes,
            created_at=api_key_record.created_at.isoformat() if api_key_record.created_at else None,
            expires_at=api_key_record.expires_at.isoformat() if api_key_record.expires_at else None
        )
    
    except Exception as e:
        logger.error(f"API key creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key creation failed"
        )


@router.get("/api-keys", response_model=list[APIKeyListResponse])
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all API keys for current user."""
    try:
        api_keys = db.query(APIKey).filter(APIKey.user_id == current_user.id).all()
        
        return [
            APIKeyListResponse(
                id=str(key.id),
                name=key.name,
                scopes=key.scopes,
                is_active=key.is_active,
                last_used=key.last_used.isoformat() if key.last_used else None,
                created_at=key.created_at.isoformat() if key.created_at else None,
                expires_at=key.expires_at.isoformat() if key.expires_at else None
            )
            for key in api_keys
        ]
    
    except Exception as e:
        logger.error(f"List API keys failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list API keys"
        )


@router.delete("/api-keys/{key_id}")
async def delete_api_key(
    key_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete API key."""
    try:
        # Get API key
        api_key = db.query(APIKey).filter(
            APIKey.id == key_id,
            APIKey.user_id == current_user.id
        ).first()
        
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        # Delete API key
        db.delete(api_key)
        db.commit()
        
        # Log audit trail
        log_audit(
            db=db,
            user=current_user,
            action="DELETE",
            resource_type="api_key",
            resource_id=str(api_key.id),
            details={"name": api_key.name}
        )
        
        logger.info(f"API key deleted: {api_key.name} by {current_user.email}")
        
        return {"message": "API key deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API key deletion failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key deletion failed"
        )


# ===================================================================
#  API Key Authentication Dependency
# ===================================================================

async def get_current_user_from_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current user from API key.
    
    Use this dependency for API key authentication instead of JWT.
    """
    try:
        api_key = credentials.credentials
        
        # Verify API key
        key_hash = verify_api_key(api_key)
        if not key_hash:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key"
            )
        
        # Get API key record
        api_key_record = db.query(APIKey).filter(
            APIKey.key_hash == key_hash,
            APIKey.is_active == True
        ).first()
        
        if not api_key_record:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or inactive API key"
            )
        
        # Check expiration
        if api_key_record.expires_at and api_key_record.expires_at < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key expired"
            )
        
        # Update last used
        api_key_record.last_used = datetime.utcnow()
        db.commit()
        
        # Get user
        user = db.query(User).filter(User.id == api_key_record.user_id).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        return user
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API key authentication failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )
