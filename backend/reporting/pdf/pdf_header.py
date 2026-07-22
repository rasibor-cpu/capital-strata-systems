"""Canonical CSS PDF page header."""

from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

from backend.common.branding import CSSBrandService
from backend.executive.executive_models import ExecutiveReport

from .pdf_assets import PDFAssetProvider
from .pdf_layout_engine import PDFPageSpecification
from .pdf_styles import FONT_BOLD, FONT_REGULAR


def draw_header(
    canvas: Canvas,
    *,
    report: ExecutiveReport,
    layout: PDFPageSpecification,
    brand: CSSBrandService,
    assets: PDFAssetProvider,
) -> None:
    canvas.saveState()
    top = layout.height_points - 30
    canvas.drawImage(
        ImageReader(str(assets.logo())),
        layout.margin_left,
        top - 24,
        width=24,
        height=24,
        preserveAspectRatio=True,
        mask="auto",
    )
    text_x = layout.margin_left + 32
    canvas.setFont(FONT_BOLD, 8.5)
    canvas.setFillColor(colors.HexColor(brand.palette.ink))
    canvas.drawString(text_x, top - 5, brand.organization_name)
    canvas.setFont(FONT_REGULAR, 7)
    canvas.drawString(text_x, top - 16, report.title)
    canvas.setFont(FONT_REGULAR, 6.5)
    canvas.drawRightString(
        layout.width_points - layout.margin_right,
        top - 5,
        report.metadata.classification,
    )
    canvas.drawRightString(
        layout.width_points - layout.margin_right,
        top - 16,
        f"{report.metadata.report_id} · {report.metadata.document_uuid}",
    )
    canvas.setStrokeColor(colors.HexColor(brand.palette.gold))
    canvas.setLineWidth(0.6)
    canvas.line(
        layout.margin_left,
        top - 30,
        layout.width_points - layout.margin_right,
        top - 30,
    )
    canvas.restoreState()


__all__ = ["draw_header"]
