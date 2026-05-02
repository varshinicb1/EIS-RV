"""
Automation API Routes
=====================
Scheduled jobs and webhook management.

Author: VidyuthLabs
Date: May 1, 2026
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import logging

from vanl.backend.core.database import get_db
from vanl.backend.core.models import User
from vanl.backend.api.auth_routes import get_current_user, log_audit
from vanl.backend.core.scheduler import (
    get_scheduler,
    ScheduleType,
    ScheduledJob
)
from vanl.backend.core.webhooks import (
    get_webhook_manager,
    WebhookEvent,
    WebhookConfig
)

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/automation", tags=["automation"])


# ===================================================================
#  Scheduled Jobs
# ===================================================================

class CreateScheduledJobRequest(BaseModel):
    """Create scheduled job request."""
    name: str = Field(..., min_length=1, max_length=255)
    schedule_type: ScheduleType
    schedule_config: Dict[str, Any]
    job_type: str = Field(..., description="batch_analysis, data_export, report_generation")
    job_config: Dict[str, Any]
    enabled: bool = True


class ScheduledJobResponse(BaseModel):
    """Scheduled job response."""
    id: str
    name: str
    schedule_type: str
    schedule_config: Dict[str, Any]
    job_type: str
    job_config: Dict[str, Any]
    enabled: bool
    last_run: Optional[str]
    next_run: Optional[str]
    run_count: int
    error_count: int
    created_at: str


@router.post("/jobs", response_model=ScheduledJobResponse, status_code=status.HTTP_201_CREATED)
async def create_scheduled_job(
    request: CreateScheduledJobRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create scheduled job.
    
    **Schedule Types:**
    - `once` - Run once at specific time
    - `interval` - Run every N seconds/minutes/hours
    - `cron` - Run on cron schedule
    - `daily` - Run daily at specific time
    - `weekly` - Run weekly on specific day/time
    - `monthly` - Run monthly on specific day/time
    
    **Schedule Config Examples:**
    ```json
    // Once
    {"datetime": "2026-05-15T14:30:00"}
    
    // Interval
    {"hours": 6}  // Every 6 hours
    {"minutes": 30}  // Every 30 minutes
    
    // Cron
    {"expression": "0 9 * * 1"}  // Every Monday at 9 AM
    
    // Daily
    {"hour": 2, "minute": 0}  // Every day at 2:00 AM
    
    // Weekly
    {"day": "monday", "hour": 9, "minute": 0}  // Every Monday at 9:00 AM
    
    // Monthly
    {"day": 1, "hour": 0, "minute": 0}  // First day of month at midnight
    ```
    
    **Job Types:**
    - `batch_analysis` - Run batch analysis
    - `data_export` - Export data
    - `report_generation` - Generate reports
    """
    try:
        # Only admins and analysts can create scheduled jobs
        if current_user.role not in ["admin", "analyst"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        
        # Create scheduled job
        scheduler = get_scheduler()
        job_id = scheduler.schedule_job(
            name=request.name,
            schedule_type=request.schedule_type,
            schedule_config=request.schedule_config,
            job_type=request.job_type,
            job_config=request.job_config,
            enabled=request.enabled
        )
        
        # Get job details
        job = scheduler.get_job(job_id)
        
        # Log audit trail
        log_audit(
            db=db,
            user=current_user,
            action="CREATE",
            resource_type="scheduled_job",
            resource_id=job_id,
            details={
                "name": request.name,
                "schedule_type": request.schedule_type,
                "job_type": request.job_type
            }
        )
        
        logger.info(f"Scheduled job created: {request.name} by {current_user.email}")
        
        return ScheduledJobResponse(
            id=job.id,
            name=job.name,
            schedule_type=job.schedule_type,
            schedule_config=job.schedule_config,
            job_type=job.job_type,
            job_config=job.job_config,
            enabled=job.enabled,
            last_run=job.last_run.isoformat() if job.last_run else None,
            next_run=job.next_run.isoformat() if job.next_run else None,
            run_count=job.run_count,
            error_count=job.error_count,
            created_at=job.created_at.isoformat() if job.created_at else None
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Scheduled job creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Scheduled job creation failed"
        )


@router.get("/jobs", response_model=List[ScheduledJobResponse])
async def list_scheduled_jobs(
    enabled_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all scheduled jobs."""
    try:
        scheduler = get_scheduler()
        jobs = scheduler.list_jobs(enabled_only=enabled_only)
        
        return [
            ScheduledJobResponse(
                id=job.id,
                name=job.name,
                schedule_type=job.schedule_type,
                schedule_config=job.schedule_config,
                job_type=job.job_type,
                job_config=job.job_config,
                enabled=job.enabled,
                last_run=job.last_run.isoformat() if job.last_run else None,
                next_run=job.next_run.isoformat() if job.next_run else None,
                run_count=job.run_count,
                error_count=job.error_count,
                created_at=job.created_at.isoformat() if job.created_at else None
            )
            for job in jobs
        ]
    
    except Exception as e:
        logger.error(f"List scheduled jobs failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list scheduled jobs"
        )


@router.get("/jobs/{job_id}", response_model=ScheduledJobResponse)
async def get_scheduled_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get scheduled job details."""
    try:
        scheduler = get_scheduler()
        job = scheduler.get_job(job_id)
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scheduled job not found"
            )
        
        return ScheduledJobResponse(
            id=job.id,
            name=job.name,
            schedule_type=job.schedule_type,
            schedule_config=job.schedule_config,
            job_type=job.job_type,
            job_config=job.job_config,
            enabled=job.enabled,
            last_run=job.last_run.isoformat() if job.last_run else None,
            next_run=job.next_run.isoformat() if job.next_run else None,
            run_count=job.run_count,
            error_count=job.error_count,
            created_at=job.created_at.isoformat() if job.created_at else None
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get scheduled job failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get scheduled job"
        )


@router.delete("/jobs/{job_id}")
async def delete_scheduled_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete scheduled job."""
    try:
        # Only admins and analysts can delete scheduled jobs
        if current_user.role not in ["admin", "analyst"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        
        scheduler = get_scheduler()
        success = scheduler.delete_job(job_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scheduled job not found"
            )
        
        # Log audit trail
        log_audit(
            db=db,
            user=current_user,
            action="DELETE",
            resource_type="scheduled_job",
            resource_id=job_id,
            details={}
        )
        
        return {"message": "Scheduled job deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete scheduled job failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete scheduled job"
        )


# ===================================================================
#  Webhooks
# ===================================================================

class CreateWebhookRequest(BaseModel):
    """Create webhook request."""
    url: HttpUrl
    events: List[WebhookEvent]
    secret: Optional[str] = None
    enabled: bool = True


class WebhookResponse(BaseModel):
    """Webhook response."""
    id: str
    url: str
    events: List[str]
    enabled: bool


@router.post("/webhooks", response_model=WebhookResponse, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    request: CreateWebhookRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create webhook endpoint.
    
    **Events:**
    - `batch_job.started` - Batch job started
    - `batch_job.completed` - Batch job completed
    - `batch_job.failed` - Batch job failed
    - `batch_job.progress` - Batch job progress update
    - `experiment.created` - Experiment created
    - `experiment.updated` - Experiment updated
    - `experiment.deleted` - Experiment deleted
    - `analysis.completed` - Analysis completed
    - `report.generated` - Report generated
    - `error.occurred` - Error occurred
    
    **Example:**
    ```bash
    curl -X POST http://localhost:8001/api/automation/webhooks \
      -H "Authorization: Bearer YOUR_TOKEN" \
      -H "Content-Type: application/json" \
      -d '{
        "url": "https://your-server.com/webhook",
        "events": ["batch_job.completed", "batch_job.failed"],
        "secret": "your-secret-key"
      }'
    ```
    """
    try:
        # Only admins and analysts can create webhooks
        if current_user.role not in ["admin", "analyst"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        
        # Create webhook
        manager = get_webhook_manager()
        webhook_id = manager.register_webhook(
            url=str(request.url),
            events=request.events,
            secret=request.secret,
            enabled=request.enabled
        )
        
        # Get webhook details
        webhook = manager.get_webhook(webhook_id)
        
        # Log audit trail
        log_audit(
            db=db,
            user=current_user,
            action="CREATE",
            resource_type="webhook",
            resource_id=webhook_id,
            details={
                "url": str(request.url),
                "events": [e.value for e in request.events]
            }
        )
        
        logger.info(f"Webhook created: {request.url} by {current_user.email}")
        
        return WebhookResponse(
            id=webhook.id,
            url=webhook.url,
            events=[e.value for e in webhook.events],
            enabled=webhook.enabled
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook creation failed"
        )


@router.get("/webhooks", response_model=List[WebhookResponse])
async def list_webhooks(
    enabled_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all webhooks."""
    try:
        manager = get_webhook_manager()
        webhooks = manager.list_webhooks(enabled_only=enabled_only)
        
        return [
            WebhookResponse(
                id=webhook.id,
                url=webhook.url,
                events=[e.value for e in webhook.events],
                enabled=webhook.enabled
            )
            for webhook in webhooks
        ]
    
    except Exception as e:
        logger.error(f"List webhooks failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list webhooks"
        )


@router.delete("/webhooks/{webhook_id}")
async def delete_webhook(
    webhook_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete webhook."""
    try:
        # Only admins and analysts can delete webhooks
        if current_user.role not in ["admin", "analyst"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        
        manager = get_webhook_manager()
        success = manager.delete_webhook(webhook_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook not found"
            )
        
        # Log audit trail
        log_audit(
            db=db,
            user=current_user,
            action="DELETE",
            resource_type="webhook",
            resource_id=webhook_id,
            details={}
        )
        
        return {"message": "Webhook deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete webhook failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete webhook"
        )


# ===================================================================
#  Health Check
# ===================================================================

@router.get("/health")
async def health_check():
    """Health check endpoint for automation module."""
    scheduler = get_scheduler()
    webhook_manager = get_webhook_manager()
    
    return {
        "status": "healthy",
        "module": "automation",
        "features": [
            "scheduled_jobs",
            "webhooks",
            "cron_expressions",
            "event_notifications"
        ],
        "scheduler": {
            "running": scheduler.running,
            "jobs_count": len(scheduler.jobs)
        },
        "webhooks": {
            "count": len(webhook_manager.webhooks)
        }
    }
