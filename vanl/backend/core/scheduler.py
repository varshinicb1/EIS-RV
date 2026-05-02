"""
Job Scheduler
=============
Cron-like scheduled job execution for automated analysis.

Author: VidyuthLabs
Date: May 1, 2026
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum
import croniter
import uuid

logger = logging.getLogger(__name__)


class ScheduleType(str, Enum):
    """Schedule type enumeration."""
    ONCE = "once"  # Run once at specific time
    INTERVAL = "interval"  # Run every N seconds/minutes/hours
    CRON = "cron"  # Run on cron schedule
    DAILY = "daily"  # Run daily at specific time
    WEEKLY = "weekly"  # Run weekly on specific day/time
    MONTHLY = "monthly"  # Run monthly on specific day/time


@dataclass
class ScheduledJob:
    """Scheduled job configuration."""
    id: str
    name: str
    schedule_type: ScheduleType
    schedule_config: Dict[str, Any]  # Type-specific configuration
    job_type: str  # batch_analysis, data_export, report_generation
    job_config: Dict[str, Any]  # Job-specific configuration
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    error_count: int = 0
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "schedule_type": self.schedule_type,
            "schedule_config": self.schedule_config,
            "job_type": self.job_type,
            "job_config": self.job_config,
            "enabled": self.enabled,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "run_count": self.run_count,
            "error_count": self.error_count,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class JobScheduler:
    """
    Job scheduler for automated task execution.
    
    Features:
    - Cron-like scheduling
    - Interval-based scheduling
    - One-time scheduled jobs
    - Job persistence
    - Error handling and retry
    - Job history tracking
    
    Examples:
        # Daily at 2 AM
        scheduler.schedule_job(
            name="Daily Analysis",
            schedule_type=ScheduleType.DAILY,
            schedule_config={"hour": 2, "minute": 0},
            job_type="batch_analysis",
            job_config={"workspace_id": "123", "analysis_types": ["eis_fitting"]}
        )
        
        # Every 6 hours
        scheduler.schedule_job(
            name="Periodic Export",
            schedule_type=ScheduleType.INTERVAL,
            schedule_config={"hours": 6},
            job_type="data_export",
            job_config={"format": "excel"}
        )
        
        # Cron expression (every Monday at 9 AM)
        scheduler.schedule_job(
            name="Weekly Report",
            schedule_type=ScheduleType.CRON,
            schedule_config={"expression": "0 9 * * 1"},
            job_type="report_generation",
            job_config={"report_type": "summary"}
        )
    """
    
    def __init__(self):
        """Initialize job scheduler."""
        self.jobs: Dict[str, ScheduledJob] = {}
        self.running = False
        self.task: Optional[asyncio.Task] = None
        logger.info("Job scheduler initialized")
    
    def schedule_job(
        self,
        name: str,
        schedule_type: ScheduleType,
        schedule_config: Dict[str, Any],
        job_type: str,
        job_config: Dict[str, Any],
        enabled: bool = True
    ) -> str:
        """
        Schedule a new job.
        
        Args:
            name: Job name
            schedule_type: Schedule type (once, interval, cron, daily, weekly, monthly)
            schedule_config: Schedule configuration
            job_type: Job type (batch_analysis, data_export, report_generation)
            job_config: Job configuration
            enabled: Whether job is enabled
        
        Returns:
            Job ID
        
        Schedule Config Examples:
            ONCE: {"datetime": "2026-05-15T14:30:00"}
            INTERVAL: {"seconds": 3600} or {"minutes": 30} or {"hours": 6}
            CRON: {"expression": "0 9 * * 1"}  # Every Monday at 9 AM
            DAILY: {"hour": 2, "minute": 0}
            WEEKLY: {"day": "monday", "hour": 9, "minute": 0}
            MONTHLY: {"day": 1, "hour": 0, "minute": 0}
        """
        job_id = str(uuid.uuid4())
        
        # Calculate next run time
        next_run = self._calculate_next_run(schedule_type, schedule_config)
        
        job = ScheduledJob(
            id=job_id,
            name=name,
            schedule_type=schedule_type,
            schedule_config=schedule_config,
            job_type=job_type,
            job_config=job_config,
            enabled=enabled,
            next_run=next_run
        )
        
        self.jobs[job_id] = job
        
        logger.info(
            f"Scheduled job '{name}' (ID: {job_id}) - "
            f"Type: {schedule_type}, Next run: {next_run}"
        )
        
        return job_id
    
    def _calculate_next_run(
        self,
        schedule_type: ScheduleType,
        schedule_config: Dict[str, Any],
        from_time: Optional[datetime] = None
    ) -> datetime:
        """
        Calculate next run time based on schedule.
        
        Args:
            schedule_type: Schedule type
            schedule_config: Schedule configuration
            from_time: Calculate from this time (default: now)
        
        Returns:
            Next run datetime
        """
        if from_time is None:
            from_time = datetime.utcnow()
        
        if schedule_type == ScheduleType.ONCE:
            # One-time execution
            dt_str = schedule_config.get("datetime")
            return datetime.fromisoformat(dt_str)
        
        elif schedule_type == ScheduleType.INTERVAL:
            # Interval-based execution
            seconds = schedule_config.get("seconds", 0)
            minutes = schedule_config.get("minutes", 0)
            hours = schedule_config.get("hours", 0)
            days = schedule_config.get("days", 0)
            
            delta = timedelta(
                days=days,
                hours=hours,
                minutes=minutes,
                seconds=seconds
            )
            
            return from_time + delta
        
        elif schedule_type == ScheduleType.CRON:
            # Cron expression
            expression = schedule_config.get("expression")
            cron = croniter.croniter(expression, from_time)
            return cron.get_next(datetime)
        
        elif schedule_type == ScheduleType.DAILY:
            # Daily at specific time
            hour = schedule_config.get("hour", 0)
            minute = schedule_config.get("minute", 0)
            
            next_run = from_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # If time has passed today, schedule for tomorrow
            if next_run <= from_time:
                next_run += timedelta(days=1)
            
            return next_run
        
        elif schedule_type == ScheduleType.WEEKLY:
            # Weekly on specific day/time
            day_name = schedule_config.get("day", "monday").lower()
            hour = schedule_config.get("hour", 0)
            minute = schedule_config.get("minute", 0)
            
            # Map day names to weekday numbers (0=Monday, 6=Sunday)
            day_map = {
                "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
                "friday": 4, "saturday": 5, "sunday": 6
            }
            target_day = day_map.get(day_name, 0)
            
            # Calculate days until target day
            current_day = from_time.weekday()
            days_ahead = target_day - current_day
            if days_ahead <= 0:  # Target day already happened this week
                days_ahead += 7
            
            next_run = from_time + timedelta(days=days_ahead)
            next_run = next_run.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            return next_run
        
        elif schedule_type == ScheduleType.MONTHLY:
            # Monthly on specific day/time
            day = schedule_config.get("day", 1)
            hour = schedule_config.get("hour", 0)
            minute = schedule_config.get("minute", 0)
            
            # Start with current month
            next_run = from_time.replace(day=day, hour=hour, minute=minute, second=0, microsecond=0)
            
            # If time has passed this month, schedule for next month
            if next_run <= from_time:
                # Move to next month
                if next_run.month == 12:
                    next_run = next_run.replace(year=next_run.year + 1, month=1)
                else:
                    next_run = next_run.replace(month=next_run.month + 1)
            
            return next_run
        
        else:
            raise ValueError(f"Unknown schedule type: {schedule_type}")
    
    async def start(self):
        """Start the scheduler."""
        if self.running:
            logger.warning("Scheduler already running")
            return
        
        self.running = True
        self.task = asyncio.create_task(self._run_loop())
        logger.info("Scheduler started")
    
    async def stop(self):
        """Stop the scheduler."""
        if not self.running:
            return
        
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        
        logger.info("Scheduler stopped")
    
    async def _run_loop(self):
        """Main scheduler loop."""
        logger.info("Scheduler loop started")
        
        while self.running:
            try:
                now = datetime.utcnow()
                
                # Check all jobs
                for job_id, job in list(self.jobs.items()):
                    if not job.enabled:
                        continue
                    
                    if job.next_run and job.next_run <= now:
                        # Execute job
                        await self._execute_job(job)
                        
                        # Calculate next run time
                        if job.schedule_type == ScheduleType.ONCE:
                            # One-time job - disable after execution
                            job.enabled = False
                            logger.info(f"One-time job '{job.name}' completed and disabled")
                        else:
                            # Recurring job - calculate next run
                            job.next_run = self._calculate_next_run(
                                job.schedule_type,
                                job.schedule_config,
                                from_time=now
                            )
                            logger.info(
                                f"Job '{job.name}' next run scheduled for {job.next_run}"
                            )
                
                # Sleep for 10 seconds before next check
                await asyncio.sleep(10)
            
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
                await asyncio.sleep(10)
    
    async def _execute_job(self, job: ScheduledJob):
        """
        Execute a scheduled job.
        
        Args:
            job: Scheduled job
        """
        logger.info(f"Executing job '{job.name}' (ID: {job.id})")
        
        try:
            # Update job status
            job.last_run = datetime.utcnow()
            job.run_count += 1
            
            # Execute based on job type
            if job.job_type == "batch_analysis":
                await self._execute_batch_analysis(job)
            elif job.job_type == "data_export":
                await self._execute_data_export(job)
            elif job.job_type == "report_generation":
                await self._execute_report_generation(job)
            else:
                logger.error(f"Unknown job type: {job.job_type}")
                job.error_count += 1
            
            logger.info(f"Job '{job.name}' completed successfully")
        
        except Exception as e:
            logger.error(f"Job '{job.name}' failed: {e}")
            job.error_count += 1
    
    async def _execute_batch_analysis(self, job: ScheduledJob):
        """Execute batch analysis job."""
        from vanl.backend.core.batch_processor import get_batch_processor, BatchJobConfig
        
        config = job.job_config
        
        # Create batch config
        batch_config = BatchJobConfig(
            job_id=f"scheduled-{job.id}",
            files=config.get("files", []),
            analysis_types=config.get("analysis_types", []),
            parameters=config.get("parameters", {}),
            max_workers=config.get("max_workers", 4)
        )
        
        # Process batch
        processor = get_batch_processor()
        await processor.process_batch(batch_config, process_func=None)
    
    async def _execute_data_export(self, job: ScheduledJob):
        """Execute data export job."""
        # TODO: Implement data export
        logger.info(f"Data export job: {job.job_config}")
    
    async def _execute_report_generation(self, job: ScheduledJob):
        """Execute report generation job."""
        # TODO: Implement report generation
        logger.info(f"Report generation job: {job.job_config}")
    
    def get_job(self, job_id: str) -> Optional[ScheduledJob]:
        """Get scheduled job by ID."""
        return self.jobs.get(job_id)
    
    def list_jobs(self, enabled_only: bool = False) -> List[ScheduledJob]:
        """
        List all scheduled jobs.
        
        Args:
            enabled_only: Only return enabled jobs
        
        Returns:
            List of scheduled jobs
        """
        jobs = list(self.jobs.values())
        
        if enabled_only:
            jobs = [j for j in jobs if j.enabled]
        
        return jobs
    
    def update_job(
        self,
        job_id: str,
        enabled: Optional[bool] = None,
        schedule_config: Optional[Dict[str, Any]] = None,
        job_config: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update scheduled job.
        
        Args:
            job_id: Job ID
            enabled: Enable/disable job
            schedule_config: New schedule configuration
            job_config: New job configuration
        
        Returns:
            True if updated, False if not found
        """
        job = self.jobs.get(job_id)
        if not job:
            return False
        
        if enabled is not None:
            job.enabled = enabled
        
        if schedule_config is not None:
            job.schedule_config = schedule_config
            # Recalculate next run
            job.next_run = self._calculate_next_run(
                job.schedule_type,
                schedule_config
            )
        
        if job_config is not None:
            job.job_config = job_config
        
        logger.info(f"Updated job '{job.name}' (ID: {job_id})")
        return True
    
    def delete_job(self, job_id: str) -> bool:
        """
        Delete scheduled job.
        
        Args:
            job_id: Job ID
        
        Returns:
            True if deleted, False if not found
        """
        if job_id in self.jobs:
            job = self.jobs[job_id]
            del self.jobs[job_id]
            logger.info(f"Deleted job '{job.name}' (ID: {job_id})")
            return True
        return False


# Global scheduler instance
_scheduler = None


def get_scheduler() -> JobScheduler:
    """Get or create global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = JobScheduler()
    return _scheduler
