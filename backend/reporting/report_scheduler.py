"""
Report Scheduler for CSS Reporting Framework

Tracks scheduled report generation tasks and determines due jobs.
"""

import time
from dataclasses import dataclass
from typing import List, Callable, Dict, Any

@dataclass
class ScheduledReportJob:
    """
    Dataclass holding context details for scheduled report triggers.
    
    Responsibility: Entity holding scheduling definition details.
    Dependencies: None.
    Thread-safety: Read/write properties, not thread-safe.
    Integration: Kept inside ReportScheduler schedule list.
    """
    job_id: str
    report_type: str
    title: str
    context_generator: Callable[[], Dict[str, Any]]
    interval_seconds: float
    last_run: float = 0.0

class ReportScheduler:
    """
    Tracks and triggers recurring scheduled reports.
    
    Responsibility: Determine when reports are due to generate.
    Dependencies: ScheduledReportJob
    Thread-safety: Not thread-safe (should be synchronized by caller).
    Integration: Polled by ReportingService.
    """
    def __init__(self):
        self._jobs: List[ScheduledReportJob] = []

    def schedule_job(
        self,
        job_id: str,
        report_type: str,
        title: str,
        context_generator: Callable[[], Dict[str, Any]],
        interval_seconds: float
    ) -> None:
        """Add a report generation job to the schedule list."""
        self._jobs.append(
            ScheduledReportJob(
                job_id=job_id,
                report_type=report_type.upper(),
                title=title,
                context_generator=context_generator,
                interval_seconds=interval_seconds,
                last_run=time.time()
            )
        )

    def get_due_jobs(self, current_time: float = None) -> List[ScheduledReportJob]:
        """Collect all jobs that are due based on elapsed time."""
        if current_time is None:
            current_time = time.time()
        
        due = []
        for job in self._jobs:
            if current_time - job.last_run >= job.interval_seconds:
                due.append(job)
        return due

    def trigger_job(self, job_id: str, current_time: float = None) -> bool:
        """Mark a job as executed at current time."""
        if current_time is None:
            current_time = time.time()
        for job in self._jobs:
            if job.job_id == job_id:
                job.last_run = current_time
                return True
        return False
