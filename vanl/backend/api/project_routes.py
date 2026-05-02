"""
Project Management API Routes
==============================
Organize experiments into projects within workspaces.

Author: VidyuthLabs
Date: May 1, 2026
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging

from vanl.backend.core.database import get_db
from vanl.backend.core.models import Project, Workspace, Experiment, User
from vanl.backend.api.auth_routes import get_current_user, log_audit
from vanl.backend.api.workspace_routes import check_workspace_access

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/projects", tags=["projects"])


# ===================================================================
#  Request/Response Models
# ===================================================================

class CreateProjectRequest(BaseModel):
    """Create project request."""
    workspace_id: str = Field(..., description="Workspace ID")
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    tags: Optional[List[str]] = None


class UpdateProjectRequest(BaseModel):
    """Update project request."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    tags: Optional[List[str]] = None


class ProjectResponse(BaseModel):
    """Project response."""
    id: str
    workspace_id: str
    name: str
    description: Optional[str]
    tags: Optional[List[str]]
    created_by: str
    created_at: str
    updated_at: str
    experiment_count: int = 0


# ===================================================================
#  API Endpoints
# ===================================================================

@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    request: CreateProjectRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create new project.
    
    **Example Request:**
    ```json
    {
        "workspace_id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "Lithium-Ion Battery Study",
        "description": "Investigating cathode materials for Li-ion batteries",
        "tags": ["battery", "lithium", "cathode"]
    }
    ```
    """
    try:
        # Check workspace access
        workspace = check_workspace_access(request.workspace_id, current_user, db, required_role="member")
        
        # Create project
        project = Project(
            workspace_id=workspace.id,
            name=request.name,
            description=request.description,
            tags=request.tags,
            created_by=current_user.id
        )
        
        db.add(project)
        db.commit()
        db.refresh(project)
        
        # Log audit trail
        log_audit(
            db=db,
            user=current_user,
            action="CREATE",
            resource_type="project",
            resource_id=str(project.id),
            details={
                "workspace_id": str(workspace.id),
                "name": project.name,
                "tags": project.tags
            }
        )
        
        logger.info(f"Project created: {project.name} by {current_user.email}")
        
        return ProjectResponse(
            **project.to_dict(),
            experiment_count=0
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Project creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Project creation failed"
        )


@router.get("", response_model=List[ProjectResponse])
async def list_projects(
    workspace_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List projects.
    
    If workspace_id is provided, list projects in that workspace.
    Otherwise, list all projects accessible to current user.
    """
    try:
        if workspace_id:
            # Check workspace access
            workspace = check_workspace_access(workspace_id, current_user, db)
            
            # Get projects in workspace
            projects = db.query(Project).filter(
                Project.workspace_id == workspace.id
            ).all()
        else:
            # Get all accessible projects
            # (projects in workspaces where user is owner or member)
            from vanl.backend.core.models import WorkspaceMember
            
            # Get workspace IDs where user has access
            owned_workspace_ids = db.query(Workspace.id).filter(
                Workspace.owner_id == current_user.id,
                Workspace.is_active == True
            ).all()
            
            member_workspace_ids = db.query(Workspace.id).join(WorkspaceMember).filter(
                WorkspaceMember.user_id == current_user.id,
                Workspace.is_active == True
            ).all()
            
            workspace_ids = [w[0] for w in owned_workspace_ids + member_workspace_ids]
            
            # Get projects in these workspaces
            projects = db.query(Project).filter(
                Project.workspace_id.in_(workspace_ids)
            ).all()
        
        # Build response with experiment counts
        response = []
        for project in projects:
            experiment_count = db.query(Experiment).filter(
                Experiment.project_id == project.id
            ).count()
            
            response.append(ProjectResponse(
                **project.to_dict(),
                experiment_count=experiment_count
            ))
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List projects failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list projects"
        )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get project details."""
    try:
        # Get project
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # Check workspace access
        check_workspace_access(str(project.workspace_id), current_user, db)
        
        # Get experiment count
        experiment_count = db.query(Experiment).filter(
            Experiment.project_id == project.id
        ).count()
        
        return ProjectResponse(
            **project.to_dict(),
            experiment_count=experiment_count
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get project failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get project"
        )


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    request: UpdateProjectRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update project details."""
    try:
        # Get project
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # Check workspace access (member role required)
        check_workspace_access(str(project.workspace_id), current_user, db, required_role="member")
        
        old_values = {}
        new_values = {}
        
        # Update name
        if request.name is not None:
            old_values["name"] = project.name
            project.name = request.name
            new_values["name"] = request.name
        
        # Update description
        if request.description is not None:
            old_values["description"] = project.description
            project.description = request.description
            new_values["description"] = request.description
        
        # Update tags
        if request.tags is not None:
            old_values["tags"] = project.tags
            project.tags = request.tags
            new_values["tags"] = request.tags
        
        project.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(project)
        
        # Log audit trail
        log_audit(
            db=db,
            user=current_user,
            action="UPDATE",
            resource_type="project",
            resource_id=str(project.id),
            details={"old_values": old_values, "new_values": new_values}
        )
        
        # Get experiment count
        experiment_count = db.query(Experiment).filter(
            Experiment.project_id == project.id
        ).count()
        
        return ProjectResponse(
            **project.to_dict(),
            experiment_count=experiment_count
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update project failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update project"
        )


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete project.
    
    WARNING: This will also delete all experiments in the project!
    """
    try:
        # Get project
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # Check workspace access (admin role required for deletion)
        check_workspace_access(str(project.workspace_id), current_user, db, required_role="admin")
        
        # Count experiments
        experiment_count = db.query(Experiment).filter(
            Experiment.project_id == project.id
        ).count()
        
        # Log audit trail before deletion
        log_audit(
            db=db,
            user=current_user,
            action="DELETE",
            resource_type="project",
            resource_id=str(project.id),
            details={
                "name": project.name,
                "experiment_count": experiment_count
            }
        )
        
        # Delete project (cascade will delete experiments)
        db.delete(project)
        db.commit()
        
        logger.info(f"Project deleted: {project.name} by {current_user.email}")
        
        return {
            "message": "Project deleted successfully",
            "experiments_deleted": experiment_count
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete project failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete project"
        )


@router.get("/{project_id}/experiments", response_model=List[dict])
async def list_project_experiments(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all experiments in project."""
    try:
        # Get project
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # Check workspace access
        check_workspace_access(str(project.workspace_id), current_user, db)
        
        # Get experiments
        experiments = db.query(Experiment).filter(
            Experiment.project_id == project.id
        ).all()
        
        return [exp.to_dict() for exp in experiments]
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List project experiments failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list experiments"
        )


# ===================================================================
#  Health Check
# ===================================================================

@router.get("/health")
async def health_check():
    """Health check endpoint for project module."""
    return {
        "status": "healthy",
        "module": "projects",
        "features": [
            "create_project",
            "list_projects",
            "update_project",
            "delete_project",
            "list_experiments"
        ]
    }
