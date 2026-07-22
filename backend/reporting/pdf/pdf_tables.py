"""Wrapping and split-safe enterprise PDF tables."""

from __future__ import annotations

from reportlab.lib import colors
from reportlab.platypus import Paragraph, Table, TableStyle

from backend.common.branding import get_brand_service
from backend.executive.executive_models import ReportTable

from .pdf_styles import FONT_BOLD, FONT_REGULAR, executive_styles


def build_pdf_table(table: ReportTable, *, available_width: float) -> Table:
    styles = executive_styles()
    data = [
        [Paragraph(_escape(column), styles["small"]) for column in table.columns],
        *[
            [Paragraph(_escape(value), styles["small"]) for value in row]
            for row in table.rows
        ],
    ]
    columns = max(len(table.columns), 1)
    widths = [available_width / columns] * columns
    brand = get_brand_service()
    result = Table(
        data,
        colWidths=widths,
        repeatRows=1 if table.repeat_header else 0,
        hAlign="LEFT",
        splitByRow=1,
    )
    result.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(brand.palette.ink)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
                ("FONTNAME", (0, 1), (-1, -1), FONT_REGULAR),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("LEADING", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#aeb7bd")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6f7")]),
            ]
        )
    )
    return result


def _escape(value: object) -> str:
    return (
        str(value if value is not None else "UNAVAILABLE")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


__all__ = ["build_pdf_table"]
