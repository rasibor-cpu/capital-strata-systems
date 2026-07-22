"""Canonical CSS PDF page footer."""

from __future__ import annotations

from reportlab.lib import colors
from reportlab.pdfgen.canvas import Canvas

from backend.common.branding import CSSBrandService
from backend.executive.executive_models import ExecutiveReport

from .pdf_layout_engine import PDFPageSpecification
from .pdf_styles import FONT_REGULAR


def draw_footer(
    canvas: Canvas,
    *,
    report: ExecutiveReport,
    layout: PDFPageSpecification,
    brand: CSSBrandService,
    page_number: int,
    page_count: int,
) -> None:
    canvas.saveState()
    y = 34
    canvas.setStrokeColor(colors.HexColor("#aeb7bd"))
    canvas.setLineWidth(0.4)
    canvas.line(
        layout.margin_left,
        y + 16,
        layout.width_points - layout.margin_right,
        y + 16,
    )
    canvas.setFillColor(colors.HexColor("#53616b"))
    canvas.setFont(FONT_REGULAR, 6.3)
    canvas.drawString(
        layout.margin_left,
        y + 5,
        (
            f"Runtime {report.metadata.runtime_version} · Document "
            f"{report.metadata.document_version} · {report.metadata.generation_timestamp}"
        ),
    )
    canvas.drawRightString(
        layout.width_points - layout.margin_right,
        y + 5,
        f"Page {page_number} of {page_count}",
    )
    canvas.setFont(FONT_REGULAR, 5.8)
    canvas.drawString(
        layout.margin_left,
        y - 5,
        f"© {report.metadata.generation_timestamp[:4]} {brand.organization_name}",
    )
    canvas.drawRightString(
        layout.width_points - layout.margin_right,
        y - 5,
        brand.document_standard.confidentiality_banner,
    )
    canvas.restoreState()


__all__ = ["draw_footer"]
