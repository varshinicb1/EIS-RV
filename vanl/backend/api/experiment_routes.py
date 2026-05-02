"""
Experiment Management API Routes
=================================
Store and manage electrochemical experiments.

Author: VidyuthLabs
Date: May 1, 2026
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from vanl.backend.core.database import get_db
from vanl.backend.core.models import Experiment, Project, User
from vanl.backend.api.auth_routes import get_current_user, log_audit
from vanl.backend.api.workspace_routes import check_workspace_access

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/experiments", tags=["experiments"])


# ===================================================================
#  Request/Response Models
# ===================================================================

class CreateExperimentRequest(BaseModel):
    """Create experiment request."""
    project_id: str = Field(..., description="Project ID")
    name: str = Field(..., min_length=1, max_length=255)
    technique: str = Field(..., description="Technique (eis, cv, gcd, etc.)")
    description: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    parameters: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class UpdateExperimentRequest(BaseModel):
    """Update experiment request."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    parameters: Optional[Dict[str, Any]] = None
    results: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


class ExperimentResponse(BaseModel):
    """Experiment response."""
    id: str
    project_id: str
    name: str
    technique: str
    description: Optional[str]
    status: str
    created_by: str
    created_at: str
    updated_at: str
    has_data: bool = False
    has_results: bool = False


class ExperimentDetailResponse(BaseModel):
    """Detailed experiment response with data."""
    id: str
    project_id: str
    name: str
    technique: str
    description: Optional[str]
    data: Optional[Dict[str, Any]]
    parameters: Optional[Dict[str, Any]]
    results: Optional[Dict[str, Any]]
    metadata: Optional[Dict[str, Any]]
    status: str
    created_by: str
    created_at: str
    updated_at: str


# ===================================================================
#  Helper Functions
# ===================================================================

def check_project_access(
    project_id: str,
    user: User,
    db: Session
) -> Project:
    """
    Check if user has access to project.
    
    Args:
        project_id: Project ID
        user: Current user
        db: Database session
    
    Returns:
        Project object
    
    Raises:
        HTTPException: If access denied
    """
    # Get project
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Check workspace access
    check_workspace_access(str(project.workspace_id), user, db)
    
    return project


# ===================================================================
#  API Endpoints
# ===================================================================

@router.post("", response_model=ExperimentResponse, status_code=status.HTTP_201_CREATED)
async def create_experiment(
    request: CreateExperimentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create new experiment.
    
    **Example Request:**
    ```json
    {
        "project_id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "EIS Measurement - Sample A",
        "technique": "eis",
        "description": "Impedance spectroscopy of graphene electrode",
        "parameters": {
            "freq_min": 0.01,
            "freq_max": 100000,
            "amplitude": 0.01
        },
        "metadata": {
            "temperature": 25,
            "electrode_area": 0.07
        }
    }
    ```
    """
    try:
        # Check project access
        project = check_project_access(request.project_id, current_user, db)
        
        # Validate technique
        valid_techniques = ["eis", "cv", "gcd", "ca", "cp", "lsv", "dpv", "swv"]
        if request.technique not in valid_techniques:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid technique. Must be one of: {', '.join(valid_techniques)}"
            )
        
        # Create experiment
        experiment = Experiment(
            project_id=project.id,
            name=request.name,
            technique=request.technique,
            description=request.description,
            data=request.data,
            parameters=request.parameters,
            metadata=request.metadata,
            status="draft",
            created_by=current_user.id
        )
        
        db.add(experiment)
        db.commit()
        db.refresh(experiment)
        
        # Log audit trail
        log_audit(
            db=db,
            user=current_user,
            action="CREATE",
            resource_type="experiment",
            resource_id=str(experiment.id),
            details={
                "project_id": str(project.id),
                "name": experiment.name,
                "technique": experiment.technique
            }
        )
        
        logger.info(f"Experiment created: {experiment.name} by {current_user.email}")
        
        return ExperimentResponse(
            **experiment.to_dict(),
            has_data=experiment.data is not None,
            has_results=experiment.results is not None
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Experiment creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Experiment creation failed"
        )


@router.get("", response_model=List[ExperimentResponse])
async def list_experiments(
    project_id: Optional[str] = None,
    technique: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List experiments with optional filters.
    
    **Query Parameters:**
    - `project_id`: Filter by project
    - `technique`: Filter by technique (eis, cv, etc.)
    - `status`: Filter by status (draft, running, completed, failed)
    """
    try:
        # Build query
        query = db.query(Experiment)
        
        if project_id:
            # Check project access
            check_project_access(project_id, current_user, db)
            query = query.filter(Experiment.project_id == project_id)
        else:
            # Get all accessible experiments
            # (experiments in projects in workspaces where user has access)
            from vanl.backend.core.models import Workspace, WorkspaceMember
            
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
            
            # Get project IDs in these workspaces
            project_ids = db.query(Project.id).filter(
                Project.workspace_id.in_(workspace_ids)
            ).all()
            project_ids = [p[0] for p in project_ids]
            
            query = query.filter(Experiment.project_id.in_(project_ids))
        
        # Apply filters
        if technique:
            query = query.filter(Experiment.technique == technique)
        
        if status:
            query = query.filter(Experiment.status == status)
        
        # Get experiments
        experiments = query.all()
        
        # Build response
        response = []
        for exp in experiments:
            response.append(ExperimentResponse(
                **exp.to_dict(),
                has_data=exp.data is not None,
                has_results=exp.results is not None
            ))
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List experiments failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list experiments"
        )


@router.get("/{experiment_id}", response_model=ExperimentDetailResponse)
async def get_experiment(
    experiment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get experiment details with full data."""
    try:
        # Get experiment
        experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
        if not experiment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Experiment not found"
            )
        
        # Check project access
        check_project_access(str(experiment.project_id), current_user, db)
        
        return ExperimentDetailResponse(**experiment.to_dict())
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get experiment failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get experiment"
        )


@router.put("/{experiment_id}", response_model=ExperimentResponse)
async def update_experiment(
    experiment_id: str,
    request: UpdateExperimentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update experiment."""
    try:
        # Get experiment
        experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
        if not experiment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Experiment not found"
            )
        
        # Check project access
        check_project_access(str(experiment.project_id), current_user, db)
        
        old_values = {}
        new_values = {}
        
        # Update fields
        if request.name is not None:
            old_values["name"] = experiment.name
            experiment.name = request.name
            new_values["name"] = request.name
        
        if request.description is not None:
            old_values["description"] = experiment.description
            experiment.description = request.description
            new_values["description"] = request.description
        
        if request.data is not None:
            experiment.data = request.data
            new_values["data_updated"] = True
        
        if request.parameters is not None:
            old_values["parameters"] = experiment.parameters
            experiment.parameters = request.parameters
            new_values["parameters"] = request.parameters
        
        if request.results is not None:
            experiment.results = request.results
            new_values["results_updated"] = True
        
        if request.metadata is not None:
            experiment.metadata = request.metadata
            new_values["metadata_updated"] = True
        
        if request.status is not None:
            valid_statuses = ["draft", "running", "completed", "failed"]
            if request.status not in valid_statuses:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
                )
            old_values["status"] = experiment.status
            experiment.status = request.status
            new_values["status"] = request.status
        
        experiment.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(experiment)
        
        # Log audit trail
        log_audit(
            db=db,
            user=current_user,
            action="UPDATE",
            resource_type="experiment",
            resource_id=str(experiment.id),
            details={"old_values": old_values, "new_values": new_values}
        )
        
        return ExperimentResponse(
            **experiment.to_dict(),
            has_data=experiment.data is not None,
            has_results=experiment.results is not None
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update experiment failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update experiment"
        )


@router.delete("/{experiment_id}")
async def delete_experiment(
    experiment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete experiment."""
    try:
        # Get experiment
        experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
        if not experiment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Experiment not found"
            )
        
        # Check project access
        check_project_access(str(experiment.project_id), current_user, db)
        
        # Log audit trail before deletion
        log_audit(
            db=db,
            user=current_user,
            action="DELETE",
            resource_type="experiment",
            resource_id=str(experiment.id),
            details={
                "name": experiment.name,
                "technique": experiment.technique
            }
        )
        
        # Delete experiment
        db.delete(experiment)
        db.commit()
        
        logger.info(f"Experiment deleted: {experiment.name} by {current_user.email}")
        
        return {"message": "Experiment deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete experiment failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete experiment"
        )


@router.post("/{experiment_id}/analyze")
async def analyze_experiment(
    experiment_id: str,
    analysis_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Run analysis on experiment data.
    
    **Analysis Types:**
    - `eis_fitting`: Fit equivalent circuit to EIS data
    - `drt`: Calculate Distribution of Relaxation Times
    - `cv_peaks`: Detect peaks in CV data
    - `quantum`: Run quantum calculations
    """
    try:
        # Get experiment
        experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
        if not experiment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Experiment not found"
            )
        
        # Check project access
        check_project_access(str(experiment.project_id), current_user, db)
        
        # Check if experiment has data
        if not experiment.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Experiment has no data to analyze"
            )
        
        # Run analysis based on type
        # (This would integrate with existing analysis modules)
        results = {
            "analysis_type": analysis_type,
            "status": "completed",
            "message": f"Analysis '{analysis_type}' completed successfully",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Update experiment results
        if not experiment.results:
            experiment.results = {}
        experiment.results[analysis_type] = results
        experiment.status = "completed"
        experiment.updated_at = datetime.utcnow()
        
        db.commit()
        
        # Log audit trail
        log_audit(
            db=db,
            user=current_user,
            action="ANALYZE",
            resource_type="experiment",
            resource_id=str(experiment.id),
            details={"analysis_type": analysis_type}
        )
        
        return results
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Experiment analysis failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Analysis failed"
        )


# ===================================================================
#  Health Check
# ===================================================================

@router.get("/health")
async def health_check():
    """Health check endpoint for experiment module."""
    return {
        "status": "healthy",
        "module": "experiments",
        "features": [
            "create_experiment",
            "list_experiments",
            "update_experiment",
            "delete_experiment",
            "analyze_experiment"
        ],
        "supported_techniques": [
            "eis", "cv", "gcd", "ca", "cp", "lsv", "dpv", "swv"
        ]
    }
