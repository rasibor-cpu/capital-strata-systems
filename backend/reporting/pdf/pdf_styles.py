"""Typography and colour standards for canonical CSS PDFs."""

from __future__ import annotations

from pathlib import Path

import reportlab
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from backend.common.branding import get_brand_service

FONT_REGULAR = "CSS-Vera"
FONT_BOLD = "CSS-Vera-Bold"


def register_embedded_fonts() -> tuple[str, str]:
    if FONT_REGULAR not in pdfmetrics.getRegisteredFontNames():
        font_root = Path(reportlab.__file__).resolve().parent / "fonts"
        pdfmetrics.registerFont(TTFont(FONT_REGULAR, str(font_root / "Vera.ttf")))
        pdfmetrics.registerFont(TTFont(FONT_BOLD, str(font_root / "VeraBd.ttf")))
    return FONT_REGULAR, FONT_BOLD


def executive_styles() -> dict[str, ParagraphStyle]:
    regular, bold = register_embedded_fonts()
    brand = get_brand_service()
    sheet = getSampleStyleSheet()
    accent = colors.HexColor(brand.palette.gold)
    ink = colors.HexColor(brand.palette.ink)
    return {
        "title": ParagraphStyle(
            "EISTitle",
            parent=sheet["Title"],
            fontName=bold,
            fontSize=20,
            leading=24,
            textColor=ink,
            spaceAfter=12,
        ),
        "subtitle": ParagraphStyle(
            "EISSubtitle",
            parent=sheet["Normal"],
            fontName=regular,
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#44515a"),
            spaceAfter=16,
        ),
        "heading": ParagraphStyle(
            "EISHeading1",
            parent=sheet["Heading1"],
            fontName=bold,
            fontSize=13,
            leading=16,
            textColor=ink,
            borderColor=accent,
            borderWidth=0,
            borderPadding=0,
            spaceBefore=12,
            spaceAfter=8,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "EISBody",
            parent=sheet["BodyText"],
            fontName=regular,
            fontSize=9,
            leading=13,
            textColor=ink,
            spaceAfter=7,
        ),
        "small": ParagraphStyle(
            "EISSmall",
            parent=sheet["BodyText"],
            fontName=regular,
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#53616b"),
        ),
    }


__all__ = ["FONT_BOLD", "FONT_REGULAR", "executive_styles", "register_embedded_fonts"]
