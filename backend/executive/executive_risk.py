"""Canonical read-only risk projection."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .executive_models import MetricValue


RISK_METRIC_KEYS = (
    "maximum_drawdown",
    "current_drawdown",
    "volatility",
    "sharpe_ratio",
    "sortino_ratio",
    "leverage",
    "exposure",
)


def build_risk_view(
    metrics: Mapping[str, MetricValue],
    snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    source = dict(snapshot or {})
    return {
        "metrics": {
            key: metrics[key].as_dict()
            for key in RISK_METRIC_KEYS
            if key in metrics
        },
        "limit_status": str(source.get("risk_limit_status") or "UNKNOWN"),
        "breaches": list(source.get("risk_breaches") or []),
        "read_only": True,
        "execution_allowed": False,
    }


__all__ = ["RISK_METRIC_KEYS", "build_risk_view"]
