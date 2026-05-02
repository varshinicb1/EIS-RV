"""
Batch Processing API Routes
============================
Process multiple files in parallel with progress tracking.

Author: VidyuthLabs
Date: May 1, 2026
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, BackgroundTasks, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import logging
import uuid
import tempfile
import os
from datetime import datetime

from vanl.backend.core.database import get_db
from vanl.backend.core.models import BatchJob, User
from vanl.backend.api.auth_routes import get_current_user, log_audit
from vanl.backend.api.workspace_routes import check_workspace_access
from vanl.backend.core.batch_processor import (
    get_batch_processor,
    BatchJobConfig,
    aggregate_results,
    generate_batch_report
)

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/batch", tags=["batch-processing"])


# ===================================================================
#  Request/Response Models
# ===================================================================

class CreateBatchJobRequest(BaseModel):
    """Create batch job request."""
    workspace_id: str = Field(..., description="Workspace ID")
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    analysis_types: List[str] = Field(..., description="Analysis types to run")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict)


class BatchJobResponse(BaseModel):
    """Batch job response."""
    id: str
    workspace_id: str
    name: str
    description: Optional[str]
    status: str
    progress: int
    total_files: int
    processed_files: int
    failed_files: int
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]


class BatchJobDetailResponse(BaseModel):
    """Detailed batch job response with results."""
    id: str
    workspace_id: str
    name: str
    description: Optional[str]
    config: Dict[str, Any]
    status: str
    progress: int
    total_files: int
    processed_files: int
    failed_files: int
    results: Optional[Dict[str, Any]]
    errors: Optional[List[str]]
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]


# ===================================================================
#  API Endpoints
# ===================================================================

@router.post("", response_model=BatchJobResponse, status_code=status.HTTP_201_CREATED)
async def create_batch_job(
    workspace_id: str = Form(...),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    analysis_types: str = Form(...),  # Comma-separated
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    """
    Create and start batch processing job.
    
    **Form Data:**
    - `workspace_id`: Workspace ID
    - `name`: Job name
    - `description`: Job description (optional)
    - `analysis_types`: Comma-separated analysis types (e.g., "eis_fitting,drt")
    - `files`: Multiple files to process
    
    **Example:**
    ```bash
    curl -X POST http://localhost:8001/api/batch \
      -H "Authorization: Bearer YOUR_TOKEN" \
      -F "workspace_id=WORKSPACE_ID" \
      -F "name=Batch EIS Analysis" \
      -F "analysis_types=eis_fitting,drt" \
      -F "files=@file1.csv" \
      -F "files=@file2.csv" \
      -F "files=@file3.csv"
    ```
    """
    try:
        # Check workspace access
        workspace = check_workspace_access(workspace_id, current_user, db, required_role="member")
        
        # Parse analysis types
        analysis_list = [a.strip() for a in analysis_types.split(",")]
        
        # Validate analysis types
        valid_types = ["eis_fitting", "drt", "cv_peaks", "quantum"]
        for analysis_type in analysis_list:
            if analysis_type not in valid_types:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid analysis type: {analysis_type}. Must be one of: {', '.join(valid_types)}"
                )
        
        # Save uploaded files to temporary directory
        temp_dir = tempfile.mkdtemp()
        file_paths = []
        
        for file in files:
            file_path = os.path.join(temp_dir, file.filename)
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
            file_paths.append(file_path)
        
        # Create batch job in database
        batch_job = BatchJob(
            workspace_id=workspace.id,
            name=name,
            description=description,
            config={
                "analysis_types": analysis_list,
                "parameters": {}
            },
            files=file_paths,
            status="pending",
            total_files=len(file_paths),
            processed_files=0,
            failed_files=0,
            created_by=current_user.id
        )
        
        db.add(batch_job)
        db.commit()
        db.refresh(batch_job)
        
        # Log audit trail
        log_audit(
            db=db,
            user=current_user,
            action="CREATE",
            resource_type="batch_job",
            resource_id=str(batch_job.id),
            details={
                "workspace_id": str(workspace.id),
                "name": name,
                "total_files": len(file_paths),
                "analysis_types": analysis_list
            }
        )
        
        # Start batch processing in background
        if background_tasks:
            background_tasks.add_task(
                process_batch_job,
                str(batch_job.id),
                file_paths,
                analysis_list,
                db
            )
        
        logger.info(f"Batch job created: {name} with {len(file_paths)} files by {current_user.email}")
        
        return BatchJobResponse(
            id=str(batch_job.id),
            workspace_id=str(batch_job.workspace_id),
            name=batch_job.name,
            description=batch_job.description,
            status=batch_job.status,
            progress=batch_job.progress,
            total_files=batch_job.total_files,
            processed_files=batch_job.processed_files,
            failed_files=batch_job.failed_files,
            created_at=batch_job.created_at.isoformat() if batch_job.created_at else None,
            started_at=batch_job.started_at.isoformat() if batch_job.started_at else None,
            completed_at=batch_job.completed_at.isoformat() if batch_job.completed_at else None
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch job creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Batch job creation failed"
        )


@router.get("", response_model=List[BatchJobResponse])
async def list_batch_jobs(
    workspace_id: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List batch jobs.
    
    **Query Parameters:**
    - `workspace_id`: Filter by workspace
    - `status`: Filter by status (pending, running, completed, failed)
    """
    try:
        # Build query
        query = db.query(BatchJob)
        
        if workspace_id:
            # Check workspace access
            check_workspace_access(workspace_id, current_user, db)
            query = query.filter(BatchJob.workspace_id == workspace_id)
        else:
            # Get all accessible batch jobs
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
            query = query.filter(BatchJob.workspace_id.in_(workspace_ids))
        
        # Apply status filter
        if status:
            query = query.filter(BatchJob.status == status)
        
        # Get batch jobs
        batch_jobs = query.order_by(BatchJob.created_at.desc()).all()
        
        # Build response
        response = []
        for job in batch_jobs:
            response.append(BatchJobResponse(
                id=str(job.id),
                workspace_id=str(job.workspace_id),
                name=job.name,
                description=job.description,
                status=job.status,
                progress=job.progress,
                total_files=job.total_files,
                processed_files=job.processed_files,
                failed_files=job.failed_files,
                created_at=job.created_at.isoformat() if job.created_at else None,
                started_at=job.started_at.isoformat() if job.started_at else None,
                completed_at=job.completed_at.isoformat() if job.completed_at else None
            ))
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List batch jobs failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list batch jobs"
        )


@router.get("/{job_id}", response_model=BatchJobDetailResponse)
async def get_batch_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get batch job details with results."""
    try:
        # Get batch job
        batch_job = db.query(BatchJob).filter(BatchJob.id == job_id).first()
        if not batch_job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Batch job not found"
            )
        
        # Check workspace access
        check_workspace_access(str(batch_job.workspace_id), current_user, db)
        
        return BatchJobDetailResponse(
            id=str(batch_job.id),
            workspace_id=str(batch_job.workspace_id),
            name=batch_job.name,
            description=batch_job.description,
            config=batch_job.config,
            status=batch_job.status,
            progress=batch_job.progress,
            total_files=batch_job.total_files,
            processed_files=batch_job.processed_files,
            failed_files=batch_job.failed_files,
            results=batch_job.results,
            errors=batch_job.errors,
            created_at=batch_job.created_at.isoformat() if batch_job.created_at else None,
            started_at=batch_job.started_at.isoformat() if batch_job.started_at else None,
            completed_at=batch_job.completed_at.isoformat() if batch_job.completed_at else None
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get batch job failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get batch job"
        )


@router.delete("/{job_id}")
async def cancel_batch_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancel running batch job."""
    try:
        # Get batch job
        batch_job = db.query(BatchJob).filter(BatchJob.id == job_id).first()
        if not batch_job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Batch job not found"
            )
        
        # Check workspace access
        check_workspace_access(str(batch_job.workspace_id), current_user, db)
        
        # Cancel job
        if batch_job.status == "running":
            processor = get_batch_processor()
            processor.cancel_job(job_id)
            
            batch_job.status = "cancelled"
            batch_job.completed_at = datetime.utcnow()
            db.commit()
            
            # Log audit trail
            log_audit(
                db=db,
                user=current_user,
                action="CANCEL",
                resource_type="batch_job",
                resource_id=str(batch_job.id),
                details={"name": batch_job.name}
            )
            
            return {"message": "Batch job cancelled successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel job with status: {batch_job.status}"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cancel batch job failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel batch job"
        )


@router.get("/{job_id}/report")
async def get_batch_report(
    job_id: str,
    format: str = "text",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get batch processing report.
    
    **Query Parameters:**
    - `format`: Report format (text, markdown)
    """
    try:
        # Get batch job
        batch_job = db.query(BatchJob).filter(BatchJob.id == job_id).first()
        if not batch_job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Batch job not found"
            )
        
        # Check workspace access
        check_workspace_access(str(batch_job.workspace_id), current_user, db)
        
        # Get job status from processor
        processor = get_batch_processor()
        job_status = processor.get_job_status(job_id)
        
        if job_status:
            report = generate_batch_report(job_status, format=format)
        else:
            # Generate report from database
            report = f"Batch Job Report\n\nJob ID: {job_id}\nStatus: {batch_job.status}\nProgress: {batch_job.progress}%"
        
        return {"report": report, "format": format}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get batch report failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get batch report"
        )


# ===================================================================
#  Background Processing
# ===================================================================

async def process_batch_job(
    job_id: str,
    file_paths: List[str],
    analysis_types: List[str],
    db: Session
):
    """
    Process batch job in background.
    
    Args:
        job_id: Batch job ID
        file_paths: List of file paths
        analysis_types: List of analysis types
        db: Database session
    """
    try:
        # Get batch job
        batch_job = db.query(BatchJob).filter(BatchJob.id == job_id).first()
        if not batch_job:
            logger.error(f"Batch job {job_id} not found")
            return
        
        # Update status
        batch_job.status = "running"
        batch_job.started_at = datetime.utcnow()
        db.commit()
        
        # Create batch config
        config = BatchJobConfig(
            job_id=job_id,
            files=file_paths,
            analysis_types=analysis_types,
            parameters=batch_job.config.get("parameters", {}),
            max_workers=4
        )
        
        # Process batch
        processor = get_batch_processor()
        
        async def progress_callback(status):
            """Update database with progress."""
            batch_job.progress = status.progress
            batch_job.processed_files = status.processed_files
            batch_job.failed_files = status.failed_files
            db.commit()
        
        result = await processor.process_batch(
            config,
            process_func=None,  # Uses internal processing
            progress_callback=progress_callback
        )
        
        # Update batch job with results
        batch_job.status = result.status
        batch_job.progress = result.progress
        batch_job.processed_files = result.processed_files
        batch_job.failed_files = result.successful_files
        batch_job.results = aggregate_results(result.results)
        batch_job.completed_at = result.completed_at
        db.commit()
        
        logger.info(f"Batch job {job_id} completed")
    
    except Exception as e:
        logger.error(f"Batch job {job_id} failed: {e}")
        batch_job.status = "failed"
        batch_job.completed_at = datetime.utcnow()
        db.commit()


# ===================================================================
#  Health Check
# ===================================================================

@router.get("/health")
async def health_check():
    """Health check endpoint for batch processing module."""
    processor = get_batch_processor()
    
    return {
        "status": "healthy",
        "module": "batch-processing",
        "features": [
            "parallel_processing",
            "progress_tracking",
            "error_handling",
            "result_aggregation"
        ],
        "max_workers": processor.max_workers,
        "active_jobs": len(processor.active_jobs)
    }
