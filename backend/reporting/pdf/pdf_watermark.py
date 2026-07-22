"""Branding-Service-backed watermark applied to every PDF page."""

from __future__ import annotations

from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

from backend.common.branding import CSSBrandService

from .pdf_assets import PDFAssetProvider
from .pdf_layout_engine import PDFPageSpecification


def draw_watermark(
    canvas: Canvas,
    *,
    layout: PDFPageSpecification,
    brand: CSSBrandService,
    assets: PDFAssetProvider,
) -> None:
    canvas.saveState()
    width = layout.width_points * (brand.watermark.width_percent / 100.0)
    height = width
    x = (layout.width_points - width) / 2.0
    y = (layout.height_points - height) / 2.0
    if hasattr(canvas, "setFillAlpha"):
        canvas.setFillAlpha(brand.watermark.opacity)
    canvas.drawImage(
        ImageReader(str(assets.watermark())),
        x,
        y,
        width=width,
        height=height,
        preserveAspectRatio=True,
        anchor="c",
        mask="auto",
    )
    canvas.restoreState()


__all__ = ["draw_watermark"]
