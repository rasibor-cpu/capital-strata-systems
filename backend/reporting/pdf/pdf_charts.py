"""Vector-only chart primitives for Executive PDFs."""

from __future__ import annotations

from collections.abc import Mapping

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors

from backend.common.branding import get_brand_service


def score_chart(scores: Mapping[str, float], *, width: float = 460, height: float = 170) -> Drawing:
    brand = get_brand_service()
    labels = list(scores)[:10]
    values = [max(0.0, min(float(scores[label]), 100.0)) for label in labels]
    drawing = Drawing(width, height)
    chart = VerticalBarChart()
    chart.x = 42
    chart.y = 38
    chart.height = height - 58
    chart.width = width - 60
    chart.data = [values or [0.0]]
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = 100
    chart.valueAxis.valueStep = 25
    chart.categoryAxis.categoryNames = [
        label.replace("_", " ").title()[:16]
        for label in (labels or ["No Data"])
    ]
    chart.categoryAxis.labels.angle = 30
    chart.categoryAxis.labels.fontSize = 6
    chart.bars[0].fillColor = colors.HexColor(brand.palette.gold)
    chart.bars[0].strokeColor = colors.HexColor(brand.palette.ink)
    drawing.add(chart)
    drawing.add(String(42, height - 12, "Executive Score Categories", fontSize=9))
    return drawing


__all__ = ["score_chart"]
