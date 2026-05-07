from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class RiskRenderContract:
    """
    PCNRASS-safe immutable render contract for risk display.
    """

    risk_state: str
    gate_status: str
    total_exposure: float
    exposure_utilization_pct: float
    current_drawdown_pct: float
    max_drawdown_pct: float
    daily_loss_limit: float
    position_limit: int
    exposure_limit: float
    risk_limits_breached: List[str]

    @classmethod
    def from_summary(cls, risk_summary: dict) -> "RiskRenderContract":
        summary = risk_summary or {}

        return cls(
            risk_state=str(summary.get("risk_state", "NORMAL")),
            gate_status=str(summary.get("gate_status", "OPEN")),
            total_exposure=float(summary.get("total_exposure", 0.0)),
            exposure_utilization_pct=float(
                summary.get("exposure_utilization_pct", 0.0)
            ),
            current_drawdown_pct=float(
                summary.get("current_drawdown_pct", 0.0)
            ),
            max_drawdown_pct=float(summary.get("max_drawdown_pct", 0.0)),
            daily_loss_limit=float(summary.get("daily_loss_limit", 0.0)),
            position_limit=int(summary.get("position_limit", 0)),
            exposure_limit=float(summary.get("exposure_limit", 0.0)),
            risk_limits_breached=list(
                summary.get("risk_limits_breached", [])
            ),
        )
