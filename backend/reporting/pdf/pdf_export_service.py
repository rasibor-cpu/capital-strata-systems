"""In-memory PDF export boundary; no filesystem or delivery side effects."""

from __future__ import annotations

from typing import Any

from backend.executive.executive_models import ExecutiveReport

from .pdf_renderer import EnterprisePDFRenderer


class PDFExportService:
    def __init__(self, renderer: EnterprisePDFRenderer | None = None) -> None:
        self.renderer = renderer or EnterprisePDFRenderer()

    def export(self, report: ExecutiveReport) -> dict[str, Any]:
        rendered = self.renderer.render(report)
        return {
            **rendered,
            "filename": f"{report.metadata.report_id}.pdf",
            "delivery": "IN_MEMORY_ONLY",
            "filesystem_write": False,
            "email_delivery": False,
        }


__all__ = ["PDFExportService"]
