"""
Report Generator for CSS Reporting Framework

Uses ReportTemplates to build Event-mapped reports from raw contexts.
"""

from backend.events.event_models import Event
from backend.reporting.report_models import create_report_event
from backend.reporting.report_templates import ReportTemplates

class ReportGenerator:
    """
    Constructs report Event objects from contexts.
    
    Responsibility: Render string templates and encapsulate contents into canonical Event models.
    Dependencies: ReportTemplates, create_report_event
    Thread-safety: Stateless and thread-safe.
    Integration: Leveraged by ReportingService.
    """
    def __init__(self, templates: ReportTemplates):
        self.templates = templates

    def generate(self, report_type: str, title: str, context: dict, metadata: dict = None) -> Event:
        """Render report text and format it into a canonical Event object."""
        content = self.templates.render(report_type, context)
        return create_report_event(
            report_type=report_type,
            title=title,
            content=content,
            metadata=metadata
        )
