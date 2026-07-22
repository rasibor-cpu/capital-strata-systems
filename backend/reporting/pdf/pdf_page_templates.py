"""Page templates, metadata, bookmarks, and page decorations."""

from __future__ import annotations

from typing import Callable

from reportlab.platypus import Paragraph, SimpleDocTemplate

from backend.common.branding import CSSBrandService
from backend.executive.executive_models import ExecutiveReport

from .pdf_assets import PDFAssetProvider
from .pdf_footer import draw_footer
from .pdf_header import draw_header
from .pdf_layout_engine import PDFPageSpecification
from .pdf_watermark import draw_watermark


class ExecutivePDFDocument(SimpleDocTemplate):
    """SimpleDocTemplate with searchable outline bookmarks."""

    def afterFlowable(self, flowable) -> None:  # type: ignore[no-untyped-def]
        if isinstance(flowable, Paragraph) and flowable.style.name == "EISHeading1":
            text = flowable.getPlainText()
            key = f"section-{self.seq.nextf('section')}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(text, key, level=0, closed=False)


def page_decorator(
    *,
    report: ExecutiveReport,
    layout: PDFPageSpecification,
    brand: CSSBrandService,
    assets: PDFAssetProvider,
    page_count: int,
) -> Callable:
    def decorate(canvas, _doc) -> None:  # type: ignore[no-untyped-def]
        canvas.setTitle(report.title)
        canvas.setAuthor(brand.organization_name)
        canvas.setSubject(report.subtitle)
        canvas.setCreator("Capital Strata Systems Executive Intelligence Suite")
        canvas.setKeywords(
            [
                "Capital Strata Systems",
                "Executive Intelligence",
                report.report_type.value,
                report.metadata.report_id,
                report.metadata.document_uuid,
            ]
        )
        draw_watermark(canvas, layout=layout, brand=brand, assets=assets)
        draw_header(
            canvas,
            report=report,
            layout=layout,
            brand=brand,
            assets=assets,
        )
        draw_footer(
            canvas,
            report=report,
            layout=layout,
            brand=brand,
            page_number=canvas.getPageNumber(),
            page_count=page_count,
        )

    return decorate


__all__ = ["ExecutivePDFDocument", "page_decorator"]
