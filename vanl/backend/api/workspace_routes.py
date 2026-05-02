"""
Workspace Management API Routes
================================
Create and manage team workspaces for collaboration.

Author: VidyuthLabs
Date: May 1, 2026
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging
import uuid

from vanl.backend.core.database import get_db
from vanl.backend.core.models import Workspace, WorkspaceMember, User, Project
from vanl.backend.api.auth_routes import get_current_user, log_audit
from vanl.backend.core.auth import check_permission

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


# ===================================================================
#  Request/Response Models
# ===================================================================

class CreateWorkspaceRequest(BaseModel):
    """Create workspace request."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class UpdateWorkspaceRequest(BaseModel):
    """Update workspace request."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None


class AddMemberRequest(BaseModel):
    """Add member to workspace request."""
    user_email: str = Field(..., description="Email of user to add")
    role: str = Field("member", description="Role (admin, member, viewer)")


class WorkspaceResponse(BaseModel):
    """Workspace response."""
    id: str
    name: str
    description: Optional[str]
    owner_id: str
    is_active: bool
    created_at: str
    updated_at: str
    member_count: int = 0
    project_count: int = 0


class MemberResponse(BaseModel):
    """Workspace member response."""
    id: str
    user_id: str
    user_email: str
    user_name: str
    role: str
    joined_at: str


# ===================================================================
#  Helper Functions
# ===================================================================

def check_workspace_access(
    workspace_id: str,
    user: User,
    db: Session,
    required_role: Optional[str] = None
) -> Workspace:
    """
    Check if user has access to workspace.
    
    Args:
        workspace_id: Workspace ID
        user: Current user
        db: Database session
        required_role: Required role (admin, member, viewer)
    
    Returns:
        Workspace object
    
    Raises:
        HTTPException: If access denied
    """
    # Get workspace
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found"
        )
    
    # Check if user is owner
    if workspace.owner_id == user.id:
        return workspace
    
    # Check if user is member
    member = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == user.id
    ).first()
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this workspace"
        )
    
    # Check role if required
    if required_role:
        role_hierarchy = {"viewer": 1, "member": 2, "admin": 3}
        user_role_level = role_hierarchy.get(member.role, 0)
        required_role_level = role_hierarchy.get(required_role, 0)
        
        if user_role_level < required_role_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {required_role} role"
            )
    
    return workspace


# ===================================================================
#  API Endpoints
# ===================================================================

@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    request: CreateWorkspaceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create new workspace.
    
    **Example Request:**
    ```json
    {
        "name": "Materials Research Lab",
        "description": "Workspace for battery research team"
    }
    ```
    """
    try:
        # Check permission
        check_permission(current_user.role, "workspaces", "create")
        
        # Create workspace
        workspace = Workspace(
            name=request.name,
            description=request.description,
            owner_id=current_user.id,
            is_active=True
        )
        
        db.add(workspace)
        db.commit()
        db.refresh(workspace)
        
        # Add owner as admin member
        member = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=current_user.id,
            role="admin"
        )
        db.add(member)
        db.commit()
        
        # Log audit trail
        log_audit(
            db=db,
            user=current_user,
            action="CREATE",
            resource_type="workspace",
            resource_id=str(workspace.id),
            details={"name": workspace.name}
        )
        
        logger.info(f"Workspace created: {workspace.name} by {current_user.email}")
        
        return WorkspaceResponse(
            **workspace.to_dict(),
            member_count=1,
            project_count=0
        )
    
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Workspace creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Workspace creation failed"
        )


@router.get("", response_model=List[WorkspaceResponse])
async def list_workspaces(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all workspaces accessible to current user.
    """
    try:
        # Get workspaces where user is owner or member
        owned_workspaces = db.query(Workspace).filter(
            Workspace.owner_id == current_user.id,
            Workspace.is_active == True
        ).all()
        
        member_workspaces = db.query(Workspace).join(WorkspaceMember).filter(
            WorkspaceMember.user_id == current_user.id,
            Workspace.is_active == True
        ).all()
        
        # Combine and deduplicate
        all_workspaces = list({w.id: w for w in owned_workspaces + member_workspaces}.values())
        
        # Build response with counts
        response = []
        for workspace in all_workspaces:
            member_count = db.query(WorkspaceMember).filter(
                WorkspaceMember.workspace_id == workspace.id
            ).count()
            
            project_count = db.query(Project).filter(
                Project.workspace_id == workspace.id
            ).count()
            
            response.append(WorkspaceResponse(
                **workspace.to_dict(),
                member_count=member_count,
                project_count=project_count
            ))
        
        return response
    
    except Exception as e:
        logger.error(f"List workspaces failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list workspaces"
        )


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get workspace details."""
    try:
        workspace = check_workspace_access(workspace_id, current_user, db)
        
        # Get counts
        member_count = db.query(WorkspaceMember).filter(
            WorkspaceMember.workspace_id == workspace.id
        ).count()
        
        project_count = db.query(Project).filter(
            Project.workspace_id == workspace.id
        ).count()
        
        return WorkspaceResponse(
            **workspace.to_dict(),
            member_count=member_count,
            project_count=project_count
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get workspace failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get workspace"
        )


@router.put("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: str,
    request: UpdateWorkspaceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update workspace details."""
    try:
        workspace = check_workspace_access(workspace_id, current_user, db, required_role="admin")
        
        old_values = {}
        new_values = {}
        
        # Update name
        if request.name is not None:
            old_values["name"] = workspace.name
            workspace.name = request.name
            new_values["name"] = request.name
        
        # Update description
        if request.description is not None:
            old_values["description"] = workspace.description
            workspace.description = request.description
            new_values["description"] = request.description
        
        workspace.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(workspace)
        
        # Log audit trail
        log_audit(
            db=db,
            user=current_user,
            action="UPDATE",
            resource_type="workspace",
            resource_id=str(workspace.id),
            details={"old_values": old_values, "new_values": new_values}
        )
        
        # Get counts
        member_count = db.query(WorkspaceMember).filter(
            WorkspaceMember.workspace_id == workspace.id
        ).count()
        
        project_count = db.query(Project).filter(
            Project.workspace_id == workspace.id
        ).count()
        
        return WorkspaceResponse(
            **workspace.to_dict(),
            member_count=member_count,
            project_count=project_count
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update workspace failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update workspace"
        )


@router.delete("/{workspace_id}")
async def delete_workspace(
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete workspace (soft delete)."""
    try:
        workspace = check_workspace_access(workspace_id, current_user, db)
        
        # Only owner can delete
        if workspace.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only workspace owner can delete workspace"
            )
        
        # Soft delete
        workspace.is_active = False
        workspace.updated_at = datetime.utcnow()
        db.commit()
        
        # Log audit trail
        log_audit(
            db=db,
            user=current_user,
            action="DELETE",
            resource_type="workspace",
            resource_id=str(workspace.id),
            details={"name": workspace.name}
        )
        
        logger.info(f"Workspace deleted: {workspace.name} by {current_user.email}")
        
        return {"message": "Workspace deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete workspace failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete workspace"
        )


# ===================================================================
#  Member Management
# ===================================================================

@router.get("/{workspace_id}/members", response_model=List[MemberResponse])
async def list_members(
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List workspace members."""
    try:
        workspace = check_workspace_access(workspace_id, current_user, db)
        
        # Get members with user details
        members = db.query(WorkspaceMember, User).join(User).filter(
            WorkspaceMember.workspace_id == workspace.id
        ).all()
        
        response = []
        for member, user in members:
            response.append(MemberResponse(
                id=str(member.id),
                user_id=str(user.id),
                user_email=user.email,
                user_name=user.full_name,
                role=member.role,
                joined_at=member.joined_at.isoformat() if member.joined_at else None
            ))
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List members failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list members"
        )


@router.post("/{workspace_id}/members", status_code=status.HTTP_201_CREATED)
async def add_member(
    workspace_id: str,
    request: AddMemberRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add member to workspace."""
    try:
        workspace = check_workspace_access(workspace_id, current_user, db, required_role="admin")
        
        # Find user by email
        user = db.query(User).filter(User.email == request.user_email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Check if already member
        existing_member = db.query(WorkspaceMember).filter(
            WorkspaceMember.workspace_id == workspace.id,
            WorkspaceMember.user_id == user.id
        ).first()
        
        if existing_member:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already a member"
            )
        
        # Validate role
        valid_roles = ["admin", "member", "viewer"]
        if request.role not in valid_roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}"
            )
        
        # Add member
        member = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=user.id,
            role=request.role
        )
        
        db.add(member)
        db.commit()
        
        # Log audit trail
        log_audit(
            db=db,
            user=current_user,
            action="CREATE",
            resource_type="workspace_member",
            resource_id=str(member.id),
            details={
                "workspace_id": str(workspace.id),
                "user_email": user.email,
                "role": request.role
            }
        )
        
        logger.info(f"Member added to workspace: {user.email} to {workspace.name}")
        
        return {"message": "Member added successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Add member failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add member"
        )


@router.delete("/{workspace_id}/members/{user_id}")
async def remove_member(
    workspace_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove member from workspace."""
    try:
        workspace = check_workspace_access(workspace_id, current_user, db, required_role="admin")
        
        # Find member
        member = db.query(WorkspaceMember).filter(
            WorkspaceMember.workspace_id == workspace.id,
            WorkspaceMember.user_id == user_id
        ).first()
        
        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found"
            )
        
        # Cannot remove owner
        if str(workspace.owner_id) == user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove workspace owner"
            )
        
        # Get user for logging
        user = db.query(User).filter(User.id == user_id).first()
        
        # Remove member
        db.delete(member)
        db.commit()
        
        # Log audit trail
        log_audit(
            db=db,
            user=current_user,
            action="DELETE",
            resource_type="workspace_member",
            resource_id=str(member.id),
            details={
                "workspace_id": str(workspace.id),
                "user_email": user.email if user else "unknown"
            }
        )
        
        logger.info(f"Member removed from workspace: {user.email if user else user_id} from {workspace.name}")
        
        return {"message": "Member removed successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Remove member failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove member"
        )


# ===================================================================
#  Health Check
# ===================================================================

@router.get("/health")
async def health_check():
    """Health check endpoint for workspace module."""
    return {
        "status": "healthy",
        "module": "workspaces",
        "features": [
            "create_workspace",
            "list_workspaces",
            "update_workspace",
            "delete_workspace",
            "member_management"
        ]
    }
