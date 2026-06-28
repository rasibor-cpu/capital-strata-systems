"""
Reporting Service for CSS Reporting Framework

Orchestrates template generation, file archiving, manifest index logging,
and job schedules.
"""

import time
from typing import Optional
from backend.events.event_models import Event
from backend.common.configuration import ReportingConfig
from backend.common.exceptions import ValidationException
from backend.common.logger import get_logger
from backend.reporting.report_generator import ReportGenerator
from backend.reporting.report_archive import ReportArchive
from backend.reporting.report_history import ReportHistory
from backend.reporting.report_scheduler import ReportScheduler

logger = get_logger("css.reporting.service")

class ReportingService:
    """
    Primary service orchestrating reporting tasks.
    Supports dependency injection and manages report generation flows.
    
    Responsibility: Orchestrate template generation, file archiving, history manifest indexing, and job schedules.
    Dependencies: ReportingConfig, ReportGenerator, ReportArchive, ReportHistory, ReportScheduler
    Thread-safety: Synchronization should be handled by caller or sub-components.
    Integration: Interface invoked by scheduler tasks or execution logs.
    """
    def __init__(
        self,
        config: ReportingConfig,
        generator: ReportGenerator,
        archive: ReportArchive,
        history: ReportHistory,
        scheduler: ReportScheduler
    ):
        config.validate()
        self.config = config
        self.generator = generator
        self.archive = archive
        self.history = history
        self.scheduler = scheduler
        import threading
        self._ingest_lock = threading.RLock()

    def create_report(self, report_type: str, title: str, context: dict, metadata: dict = None) -> Event:
        """
        Render templates and package it as a canonical report Event.
        Archives report details to disk and indexes to the manifest log.
        """
        event = self.generator.generate(
            report_type=report_type,
            title=title,
            context=context,
            metadata=metadata
        )
        
        event.source = self.config.default_source
        event.validate()
        
        # Archive individual file
        self.archive.append(event)
        
        # Index to manifest
        self.history.append(event)
        
        logger.info(f"Report '{title}' ({report_type}) created and archived successfully.")
        return event

    def process_schedule(self, current_time: Optional[float] = None) -> int:
        """
        Poll scheduled tasks and generate reports due for execution.
        """
        if current_time is None:
            current_time = time.time()
            
        due_jobs = self.scheduler.get_due_jobs(current_time)
        for job in due_jobs:
            context = job.context_generator()
            # Append timestamp context for templates
            if "timestamp" not in context:
                context["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(current_time))
            
            self.create_report(
                report_type=job.report_type,
                title=job.title,
                context=context,
                metadata={"job_id": job.job_id}
            )
            self.scheduler.trigger_job(job.job_id, current_time)
            
        return len(due_jobs)

    def handle_event(self, event: Event) -> None:
        """Passive event bus subscriber callback for reporting framework."""
        try:
            from backend.common.persistence import load_json, save_json
            buffer_file = "artifacts/reports/ingested_events.json"
            data = load_json(buffer_file, self._ingest_lock)
            if not isinstance(data, list):
                data = []
            data.append(event.to_dict())
            save_json(buffer_file, data, self._ingest_lock)
        except Exception as e:
            logger.error(f"Error in ReportingService handle_event: {e}")

