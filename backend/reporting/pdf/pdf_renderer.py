"""The sole canonical CSS PDF renderer."""

from __future__ import annotations

import hashlib
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import PageBreak, Paragraph, Spacer, Table, TableStyle

from backend.common.branding import get_brand_service
from backend.executive.executive_models import ExecutiveReport

from .pdf_assets import PDFAssetProvider
from .pdf_charts import score_chart
from .pdf_layout_engine import PDFLayoutEngine, PDFPageSpecification
from .pdf_page_templates import ExecutivePDFDocument, page_decorator
from .pdf_styles import FONT_BOLD, FONT_REGULAR, executive_styles, register_embedded_fonts
from .pdf_tables import build_pdf_table


PDF_RENDERER_VERSION = "css.enterprise.pdf.v1"


class EnterprisePDFRenderer:
    """Render an ExecutiveReport to an ISO A4, searchable, bookmarked PDF."""

    def __init__(self) -> None:
        self.brand = get_brand_service()
        self.assets = PDFAssetProvider(self.brand)
        self.layouts = PDFLayoutEngine()

    def render(self, report: ExecutiveReport) -> dict[str, Any]:
        register_embedded_fonts()
        layout = self.layouts.resolve(report)
        page_count = self._count_pages(report, layout)
        output = BytesIO()
        document = self._document(output, report, layout)
        decorate = page_decorator(
            report=report,
            layout=layout,
            brand=self.brand,
            assets=self.assets,
            page_count=page_count,
        )
        document.build(
            self._story(report, layout),
            onFirstPage=decorate,
            onLaterPages=decorate,
        )
        pdf_bytes = output.getvalue()
        if not pdf_bytes.startswith(b"%PDF"):
            raise ValueError("canonical_pdf_signature_invalid")
        return {
            "status": "OK",
            "format": "PDF",
            "canonical": True,
            "renderer_version": PDF_RENDERER_VERSION,
            "pdf_bytes": pdf_bytes,
            "sha256": hashlib.sha256(pdf_bytes).hexdigest(),
            "size_bytes": len(pdf_bytes),
            "page_count": page_count,
            "layout": layout.as_dict(),
            "metadata": {
                **report.as_dict()["metadata"],
                "title": report.title,
                "author": self.brand.organization_name,
                "bookmarks": [section.title for section in report.sections],
                "searchable_text": True,
                "selectable_text": True,
                "embedded_fonts": True,
                "vector_charts": True,
                "digital_signature_ready": True,
            },
            "safety": report.as_dict()["safety"],
        }

    def _count_pages(
        self,
        report: ExecutiveReport,
        layout: PDFPageSpecification,
    ) -> int:
        counter: dict[str, int] = {"pages": 0}

        class CountingCanvas(Canvas):
            def showPage(self) -> None:
                counter["pages"] += 1
                super().showPage()

        sink = BytesIO()
        document = self._document(sink, report, layout)
        document.build(
            self._story(report, layout),
            canvasmaker=CountingCanvas,
        )
        return max(counter["pages"], 1)

    def _document(
        self,
        target: BytesIO,
        report: ExecutiveReport,
        layout: PDFPageSpecification,
    ) -> ExecutivePDFDocument:
        return ExecutivePDFDocument(
            target,
            pagesize=(layout.width_points, layout.height_points),
            leftMargin=layout.margin_left,
            rightMargin=layout.margin_right,
            topMargin=layout.margin_top,
            bottomMargin=layout.margin_bottom,
            title=report.title,
            author=self.brand.organization_name,
            subject=report.subtitle,
            creator="Capital Strata Systems Executive Intelligence Suite",
            pageCompression=1,
        )

    def _story(
        self,
        report: ExecutiveReport,
        layout: PDFPageSpecification,
    ) -> list[Any]:
        styles = executive_styles()
        available_width = (
            layout.width_points - layout.margin_left - layout.margin_right
        )
        story: list[Any] = [
            Paragraph(_escape(report.title), styles["title"]),
            Paragraph(_escape(report.subtitle), styles["subtitle"]),
            self._metadata_table(report, available_width),
            Spacer(1, 12),
            Paragraph(
                _escape(self.brand.document_standard.confidentiality_banner),
                styles["small"],
            ),
            PageBreak(),
        ]
        if not report.sections:
            story.extend(
                [
                    Paragraph("Executive Report", styles["heading"]),
                    Paragraph("No report content available.", styles["body"]),
                ]
            )
            return story

        for section in report.sections:
            if section.page_break_before and story:
                story.append(PageBreak())
            story.append(Paragraph(_escape(section.title), styles["heading"]))
            for paragraph in section.paragraphs:
                story.append(Paragraph(_escape(paragraph), styles["body"]))
            if section.metrics:
                metric_table = Table(
                    [
                        ["KPI", "Value", "Unit", "Status", "As Of"],
                        *[
                            [
                                metric.label,
                                _format_value(metric.value),
                                metric.unit,
                                metric.status.value,
                                metric.as_of or "UNAVAILABLE",
                            ]
                            for metric in section.metrics
                        ],
                    ],
                    repeatRows=1,
                    colWidths=[
                        available_width * 0.28,
                        available_width * 0.17,
                        available_width * 0.12,
                        available_width * 0.13,
                        available_width * 0.30,
                    ],
                )
                metric_table.setStyle(_metric_table_style())
                story.extend([metric_table, Spacer(1, 10)])
            for table in section.tables:
                story.append(Paragraph(_escape(table.title), styles["small"]))
                story.append(build_pdf_table(table, available_width=available_width))
                story.append(Spacer(1, 10))
                if table.title == "Weighted Score Categories":
                    scores = {
                        str(row[0]): float(row[1])
                        for row in table.rows
                        if len(row) > 1
                    }
                    story.append(score_chart(scores, width=min(available_width, 500)))
                    story.append(Spacer(1, 8))
        return story

    def _metadata_table(self, report: ExecutiveReport, width: float) -> Table:
        data = [
            ["Classification", report.metadata.classification],
            ["Report ID", report.metadata.report_id],
            ["UUID", report.metadata.document_uuid],
            ["Runtime Version", report.metadata.runtime_version],
            ["Generation Timestamp", report.metadata.generation_timestamp],
            ["Reporting Period", report.metadata.reporting_period],
        ]
        table = Table(data, colWidths=[width * 0.28, width * 0.72])
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, -1), FONT_BOLD),
                    ("FONTNAME", (1, 0), (1, -1), FONT_REGULAR),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#c4cbd0")),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f3f4")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        return table


def _metric_table_style() -> TableStyle:
    brand = get_brand_service()
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(brand.palette.ink)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
            ("FONTNAME", (0, 1), (-1, -1), FONT_REGULAR),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#aeb7bd")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6f7")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]
    )


def _escape(value: object) -> str:
    return (
        str(value if value is not None else "UNAVAILABLE")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _format_value(value: object) -> str:
    if isinstance(value, float):
        return f"{value:,.4f}"
    return str(value if value is not None else "UNAVAILABLE")


__all__ = ["EnterprisePDFRenderer", "PDF_RENDERER_VERSION"]
