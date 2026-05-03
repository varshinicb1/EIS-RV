"""
Batch Processing Engine
=======================
Process multiple experiments in parallel with progress tracking.

Author: VidyuthLabs
Date: May 1, 2026
"""

import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
import traceback

logger = logging.getLogger(__name__)


@dataclass
class BatchJobConfig:
    """Batch job configuration."""
    job_id: str
    files: List[str]
    analysis_types: List[str]
    parameters: Dict[str, Any]
    max_workers: int = 4
    timeout_seconds: int = 300


@dataclass
class BatchResult:
    """Result from processing a single file."""
    file_path: str
    success: bool
    results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    processing_time_seconds: float = 0.0


@dataclass
class BatchJobStatus:
    """Batch job status."""
    job_id: str
    status: str  # pending, running, completed, failed
    progress: int  # 0-100
    total_files: int
    processed_files: int
    successful_files: int
    failed_files: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    results: List[BatchResult] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "job_id": self.job_id,
            "status": self.status,
            "progress": self.progress,
            "total_files": self.total_files,
            "processed_files": self.processed_files,
            "successful_files": self.successful_files,
            "failed_files": self.failed_files,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "results": [r.__dict__ for r in self.results] if self.results else []
        }


class BatchProcessor:
    """
    Batch processing engine for analyzing multiple files in parallel.
    
    Features:
    - Parallel processing with configurable workers
    - Progress tracking
    - Error handling and retry
    - Timeout support
    - Result aggregation
    """
    
    def __init__(self, max_workers: int = 4):
        """
        Initialize batch processor.
        
        Args:
            max_workers: Maximum number of parallel workers
        """
        self.max_workers = max_workers
        self.active_jobs: Dict[str, BatchJobStatus] = {}
        logger.info(f"Batch processor initialized with {max_workers} workers")
    
    async def process_batch(
        self,
        config: BatchJobConfig,
        process_func: Callable,
        progress_callback: Optional[Callable] = None
    ) -> BatchJobStatus:
        """
        Process batch of files.
        
        Args:
            config: Batch job configuration
            process_func: Function to process each file
            progress_callback: Optional callback for progress updates
        
        Returns:
            BatchJobStatus with results
        """
        job_id = config.job_id
        
        # Initialize job status
        status = BatchJobStatus(
            job_id=job_id,
            status="running",
            progress=0,
            total_files=len(config.files),
            processed_files=0,
            successful_files=0,
            failed_files=0,
            started_at=datetime.utcnow(),
            results=[]
        )
        
        self.active_jobs[job_id] = status
        
        logger.info(f"Starting batch job {job_id} with {len(config.files)} files")
        
        try:
            # Process files in parallel
            with ProcessPoolExecutor(max_workers=config.max_workers) as executor:
                # Submit all tasks
                future_to_file = {
                    executor.submit(
                        self._process_single_file,
                        file_path,
                        config.analysis_types,
                        config.parameters,
                        config.timeout_seconds
                    ): file_path
                    for file_path in config.files
                }
                
                # Collect results as they complete
                for future in as_completed(future_to_file):
                    file_path = future_to_file[future]
                    
                    try:
                        result = future.result(timeout=config.timeout_seconds)
                        status.results.append(result)
                        
                        if result.success:
                            status.successful_files += 1
                        else:
                            status.failed_files += 1
                        
                    except Exception as e:
                        logger.error(f"Failed to process {file_path}: {e}")
                        status.results.append(BatchResult(
                            file_path=file_path,
                            success=False,
                            error=str(e)
                        ))
                        status.failed_files += 1
                    
                    # Update progress
                    status.processed_files += 1
                    status.progress = int((status.processed_files / status.total_files) * 100)
                    
                    # Call progress callback
                    if progress_callback:
                        await progress_callback(status)
                    
                    logger.info(
                        f"Job {job_id}: {status.processed_files}/{status.total_files} "
                        f"({status.progress}%) - {status.successful_files} success, "
                        f"{status.failed_files} failed"
                    )
            
            # Mark as completed
            status.status = "completed"
            status.completed_at = datetime.utcnow()
            
            logger.info(
                f"Batch job {job_id} completed: {status.successful_files} success, "
                f"{status.failed_files} failed"
            )
            
        except Exception as e:
            logger.error(f"Batch job {job_id} failed: {e}")
            status.status = "failed"
            status.completed_at = datetime.utcnow()
        
        return status
    
    def _process_single_file(
        self,
        file_path: str,
        analysis_types: List[str],
        parameters: Dict[str, Any],
        timeout_seconds: int
    ) -> BatchResult:
        """
        Process a single file.
        
        Args:
            file_path: Path to file
            analysis_types: List of analysis types to run
            parameters: Analysis parameters
            timeout_seconds: Timeout in seconds
        
        Returns:
            BatchResult
        """
        start_time = datetime.utcnow()
        
        try:
            # Import analysis modules
            from src.backend.core.engines.data_import import DataImporter
            from src.backend.core.engines.circuit_fitting import CircuitFitter
            from src.backend.core.engines.drt_analysis import DRTAnalyzer
            
            results = {}
            
            # Import data
            importer = DataImporter()
            
            # Detect data type from analysis types
            if any(t in ["eis_fitting", "drt"] for t in analysis_types):
                data = importer.import_eis_data(file_path, format_type="auto")
                results["data_type"] = "eis"
                results["data"] = {
                    "n_points": len(data.frequencies),
                    "freq_range": [float(data.frequencies.min()), float(data.frequencies.max())]
                }
                
                # Run EIS fitting
                if "eis_fitting" in analysis_types:
                    fitter = CircuitFitter()
                    fit_result = fitter.fit_circuit(
                        frequencies=data.frequencies,
                        Z_real=data.Z_real,
                        Z_imag=data.Z_imag,
                        circuit_model=parameters.get("circuit_model", "randles_cpe"),
                        method=parameters.get("method", "lm")
                    )
                    results["eis_fitting"] = {
                        "parameters": fit_result.parameters,
                        "chi_squared": fit_result.chi_squared,
                        "success": fit_result.success
                    }
                
                # Run DRT analysis
                if "drt" in analysis_types:
                    analyzer = DRTAnalyzer()
                    drt_result = analyzer.calculate_drt(
                        frequencies=data.frequencies,
                        Z_real=data.Z_real,
                        Z_imag=data.Z_imag,
                        lambda_reg=parameters.get("lambda_reg", 1e-3)
                    )
                    results["drt"] = {
                        "n_peaks": len(drt_result.peaks),
                        "peaks": drt_result.peaks,
                        "chi_squared": drt_result.chi_squared
                    }
            
            elif "cv_peaks" in analysis_types:
                data = importer.import_cv_data(file_path, format_type="auto")
                results["data_type"] = "cv"
                results["data"] = {
                    "n_points": len(data.potential),
                    "potential_range": [float(data.potential.min()), float(data.potential.max())],
                    "scan_rate": data.scan_rate
                }
                
                # CV peak detection would go here
                results["cv_peaks"] = {
                    "message": "CV peak detection not yet implemented"
                }
            
            # Calculate processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            return BatchResult(
                file_path=file_path,
                success=True,
                results=results,
                processing_time_seconds=processing_time
            )
        
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            logger.error(traceback.format_exc())
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            return BatchResult(
                file_path=file_path,
                success=False,
                error=str(e),
                processing_time_seconds=processing_time
            )
    
    def get_job_status(self, job_id: str) -> Optional[BatchJobStatus]:
        """
        Get status of batch job.
        
        Args:
            job_id: Job ID
        
        Returns:
            BatchJobStatus or None if not found
        """
        return self.active_jobs.get(job_id)
    
    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel batch job.
        
        Args:
            job_id: Job ID
        
        Returns:
            True if cancelled, False if not found
        """
        if job_id in self.active_jobs:
            status = self.active_jobs[job_id]
            if status.status == "running":
                status.status = "cancelled"
                status.completed_at = datetime.utcnow()
                logger.info(f"Batch job {job_id} cancelled")
                return True
        return False
    
    def cleanup_completed_jobs(self, max_age_hours: int = 24):
        """
        Clean up completed jobs older than max_age_hours.
        
        Args:
            max_age_hours: Maximum age in hours
        """
        now = datetime.utcnow()
        to_remove = []
        
        for job_id, status in self.active_jobs.items():
            if status.status in ["completed", "failed", "cancelled"]:
                if status.completed_at:
                    age_hours = (now - status.completed_at).total_seconds() / 3600
                    if age_hours > max_age_hours:
                        to_remove.append(job_id)
        
        for job_id in to_remove:
            del self.active_jobs[job_id]
            logger.info(f"Cleaned up job {job_id}")
        
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} completed jobs")


# Global batch processor instance
_batch_processor = None


def get_batch_processor() -> BatchProcessor:
    """Get or create global batch processor instance."""
    global _batch_processor
    if _batch_processor is None:
        _batch_processor = BatchProcessor(max_workers=4)
    return _batch_processor


# ===================================================================
#  Utility Functions
# ===================================================================

def aggregate_results(results: List[BatchResult]) -> Dict[str, Any]:
    """
    Aggregate results from batch processing.
    
    Args:
        results: List of batch results
    
    Returns:
        Aggregated statistics
    """
    total = len(results)
    successful = sum(1 for r in results if r.success)
    failed = total - successful
    
    # Calculate average processing time
    avg_time = sum(r.processing_time_seconds for r in results) / total if total > 0 else 0
    
    # Aggregate analysis results
    eis_params = []
    drt_peaks = []
    
    for result in results:
        if result.success and result.results:
            if "eis_fitting" in result.results:
                eis_params.append(result.results["eis_fitting"]["parameters"])
            if "drt" in result.results:
                drt_peaks.extend(result.results["drt"]["peaks"])
    
    return {
        "total_files": total,
        "successful": successful,
        "failed": failed,
        "success_rate": (successful / total * 100) if total > 0 else 0,
        "avg_processing_time_seconds": avg_time,
        "eis_parameters_count": len(eis_params),
        "drt_peaks_count": len(drt_peaks)
    }


def generate_batch_report(
    job_status: BatchJobStatus,
    format: str = "text"
) -> str:
    """
    Generate batch processing report.
    
    Args:
        job_status: Batch job status
        format: Report format (text, html, markdown)
    
    Returns:
        Report string
    """
    if format == "text":
        report = f"""
Batch Processing Report
=======================
Job ID: {job_status.job_id}
Status: {job_status.status}
Progress: {job_status.progress}%

Files Processed: {job_status.processed_files}/{job_status.total_files}
Successful: {job_status.successful_files}
Failed: {job_status.failed_files}
Success Rate: {(job_status.successful_files/job_status.total_files*100):.1f}%

Started: {job_status.started_at}
Completed: {job_status.completed_at}
Duration: {(job_status.completed_at - job_status.started_at).total_seconds():.1f}s

Results:
--------
"""
        for i, result in enumerate(job_status.results[:10], 1):  # Show first 10
            status_icon = "✅" if result.success else "❌"
            report += f"{i}. {status_icon} {result.file_path}\n"
            if result.error:
                report += f"   Error: {result.error}\n"
        
        if len(job_status.results) > 10:
            report += f"\n... and {len(job_status.results) - 10} more files\n"
        
        return report
    
    elif format == "markdown":
        report = f"""# Batch Processing Report

**Job ID**: {job_status.job_id}  
**Status**: {job_status.status}  
**Progress**: {job_status.progress}%

## Summary

- **Files Processed**: {job_status.processed_files}/{job_status.total_files}
- **Successful**: {job_status.successful_files}
- **Failed**: {job_status.failed_files}
- **Success Rate**: {(job_status.successful_files/job_status.total_files*100):.1f}%

## Timing

- **Started**: {job_status.started_at}
- **Completed**: {job_status.completed_at}
- **Duration**: {(job_status.completed_at - job_status.started_at).total_seconds():.1f}s

## Results

| # | Status | File | Time (s) |
|---|--------|------|----------|
"""
        for i, result in enumerate(job_status.results[:10], 1):
            status_icon = "✅" if result.success else "❌"
            report += f"| {i} | {status_icon} | {result.file_path} | {result.processing_time_seconds:.2f} |\n"
        
        if len(job_status.results) > 10:
            report += f"\n*... and {len(job_status.results) - 10} more files*\n"
        
        return report
    
    else:
        raise ValueError(f"Unsupported format: {format}")
