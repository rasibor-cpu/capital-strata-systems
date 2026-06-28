"""
Tests for Component B: Enterprise Reporting Framework
"""

import os
import pytest
from backend.reporting import (
    ReportTemplates,
    ReportGenerator,
    ReportArchive,
    ReportHistory,
    ReportScheduler,
    ReportingConfig,
    ReportingService,
)

def test_template_rendering():
    templates = ReportTemplates()
    context = {
        "timestamp": "2026-06-17 12:00:00",
        "trades_count": 5,
        "total_volume": 1200.5,
        "pnl": 450.25
    }
    rendered = templates.render("DAILY", context)
    assert "Daily Operational Report" in rendered
    assert "Trades: 5" in rendered
    assert "PnL: 450.25" in rendered


def test_generator_and_persistence(tmp_path):
    archive_dir = tmp_path / "reports"
    history_file = tmp_path / "report_history.json"

    templates = ReportTemplates()
    generator = ReportGenerator(templates)
    archive = ReportArchive(archive_dir=str(archive_dir))
    history = ReportHistory(history_file=str(history_file))

    config = ReportingConfig(default_source="test_source")
    service = ReportingService(
        config=config,
        generator=generator,
        archive=archive,
        history=history,
        scheduler=ReportScheduler()
    )

    context = {
        "timestamp": "2026-06-17 12:00:00",
        "trades_count": 10,
        "total_volume": 5000.0,
        "pnl": -250.0
    }

    report_event = service.create_report(
        report_type="DAILY",
        title="June 17 Daily Report",
        context=context,
        metadata={"run_mode": "test"}
    )

    # Check Event fields
    assert report_event.event_type == "REPORT_GENERATED"
    assert report_event.source == "test_source"
    assert report_event.payload["report_type"] == "DAILY"
    assert "Daily Operational Report" in report_event.payload["content"]

    # Check Archive persistence
    assert os.path.exists(archive_dir / f"report_{report_event.event_id}.json")
    archived_reports = archive.load()
    assert len(archived_reports) == 1
    assert archived_reports[0].event_id == report_event.event_id

    # Check History manifest index
    assert os.path.exists(history_file)
    history_events = history.load()
    assert len(history_events) == 1
    assert history_events[0].event_id == report_event.event_id


def test_scheduler_timing():
    scheduler = ReportScheduler()
    
    run_tracker = []
    def dummy_context():
        run_tracker.append(True)
        return {
            "timestamp": "2026-06-17 12:00:00",
            "trades_count": 0,
            "total_volume": 0.0,
            "pnl": 0.0
        }

    scheduler.schedule_job(
        job_id="daily_job",
        report_type="DAILY",
        title="Scheduled Daily",
        context_generator=dummy_context,
        interval_seconds=60.0
    )

    due = scheduler.get_due_jobs()
    assert len(due) == 0

    # Advance current time manually
    fake_now = scheduler._jobs[0].last_run + 70.0
    due = scheduler.get_due_jobs(fake_now)
    assert len(due) == 1
    assert due[0].job_id == "daily_job"

    # Trigger job
    triggered = scheduler.trigger_job("daily_job", fake_now)
    assert triggered is True
    assert len(scheduler.get_due_jobs(fake_now)) == 0
