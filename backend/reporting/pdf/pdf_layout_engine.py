"""ISO paper and orientation policy for canonical PDF reports."""

from __future__ import annotations

from dataclasses import dataclass

from reportlab.lib.pagesizes import A3, A4, landscape, portrait

from backend.executive.executive_models import ExecutiveReport, PageOrientation


@dataclass(frozen=True)
class PDFPageSpecification:
    paper_size: str
    orientation: PageOrientation
    width_points: float
    height_points: float
    margin_left: float
    margin_right: float
    margin_top: float
    margin_bottom: float

    def as_dict(self) -> dict[str, float | str]:
        return {
            "paper_size": self.paper_size,
            "orientation": self.orientation.value,
            "width_points": self.width_points,
            "height_points": self.height_points,
            "margin_left": self.margin_left,
            "margin_right": self.margin_right,
            "margin_top": self.margin_top,
            "margin_bottom": self.margin_bottom,
        }


class PDFLayoutEngine:
    SUPPORTED_PAPER = {"A4": A4, "A3": A3}

    def resolve(self, report: ExecutiveReport) -> PDFPageSpecification:
        paper_name = report.paper_size.upper()
        base = self.SUPPORTED_PAPER.get(paper_name, A4)
        page = (
            landscape(base)
            if report.orientation == PageOrientation.LANDSCAPE
            else portrait(base)
        )
        return PDFPageSpecification(
            paper_size=paper_name if paper_name in self.SUPPORTED_PAPER else "A4",
            orientation=report.orientation,
            width_points=float(page[0]),
            height_points=float(page[1]),
            margin_left=42.0,
            margin_right=42.0,
            margin_top=86.0,
            margin_bottom=62.0,
        )


__all__ = ["PDFLayoutEngine", "PDFPageSpecification"]
