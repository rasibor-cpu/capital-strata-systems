"""Derived renderers fed exclusively by the canonical ExecutiveReport model."""

from __future__ import annotations

from html import escape
from typing import Any

from backend.common.branding import get_brand_service
from backend.reporting.pdf import PDFExportService

from .executive_models import ExecutiveReport


class ExecutiveRenderingService:
    def __init__(self, *, pdf_exporter: PDFExportService | None = None) -> None:
        self.pdf_exporter = pdf_exporter or PDFExportService()

    def pdf(self, report: ExecutiveReport) -> dict[str, Any]:
        """Canonical and default rendering path."""
        return self.pdf_exporter.export(report)

    def html(self, report: ExecutiveReport) -> str:
        brand = get_brand_service()
        orientation = report.orientation.value
        page_size = "297mm 210mm" if orientation == "landscape" else "210mm 297mm"
        sections: list[str] = []
        for section in report.sections:
            blocks = [f"<h2>{escape(section.title)}</h2>"]
            blocks.extend(f"<p>{escape(text)}</p>" for text in section.paragraphs)
            if section.metrics:
                blocks.append(
                    "<table><thead><tr><th>KPI</th><th>Value</th><th>Unit</th><th>Status</th></tr></thead><tbody>"
                )
                blocks.extend(
                    "<tr>"
                    f"<td>{escape(metric.label)}</td>"
                    f"<td>{escape(str(metric.value))}</td>"
                    f"<td>{escape(metric.unit)}</td>"
                    f"<td>{escape(metric.status.value)}</td>"
                    "</tr>"
                    for metric in section.metrics
                )
                blocks.append("</tbody></table>")
            for table in section.tables:
                blocks.append(f"<h3>{escape(table.title)}</h3><table><thead><tr>")
                blocks.extend(f"<th>{escape(column)}</th>" for column in table.columns)
                blocks.append("</tr></thead><tbody>")
                for row in table.rows:
                    blocks.append("<tr>")
                    blocks.extend(f"<td>{escape(str(value))}</td>" for value in row)
                    blocks.append("</tr>")
                blocks.append("</tbody></table>")
            sections.append("".join(blocks))
        if not sections:
            sections.append(
                "<h2>Executive Report</h2><p>No report content available.</p>"
            )
        return (
            "<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>{escape(report.title)}</title><style>"
            f"@page{{size:{page_size};margin:18mm;}}"
            "body{font-family:Arial,sans-serif;color:#10202a;}"
            ".page{position:relative;isolation:isolate;min-height:250mm;}"
            "table{border-collapse:collapse;width:100%;font-size:9pt;}"
            "th,td{border:1px solid #aeb7bd;padding:5px;text-align:left;}"
            f"{brand.watermark_css(page_selector='.page')}"
            "</style></head><body><main class='page'>"
            f"{brand.watermark_markup()}"
            f"<h1>{escape(report.title)}</h1><p>{escape(report.subtitle)}</p>"
            f"<p>{escape(report.metadata.classification)} · "
            f"{escape(report.metadata.report_id)} · {escape(report.metadata.reporting_period)}</p>"
            + "".join(sections)
            + f"<footer>{escape(brand.document_standard.confidentiality_banner)}</footer>"
            "</main></body></html>"
        )

    def print_preview(self, report: ExecutiveReport) -> str:
        return self.html(report)

    def api(self, report: ExecutiveReport) -> dict[str, Any]:
        return report.as_dict()


__all__ = ["ExecutiveRenderingService"]
