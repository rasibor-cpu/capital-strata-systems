from __future__ import annotations

from typing import Any, Dict, List

from dashboard.runtime._utils import safe_float, safe_int


class RiskSummaryBuilder:
    """
    PCNRASS-safe risk summary builder.

    Purpose:
    - Normalize runtime risk payloads for dashboard presentation.
    - Keep risk aggregation separate from renderers.
    - Avoid making or overriding governance decisions.
    """

    def build(
        self,
        account_state: Dict[str, Any] | None,
        position_state: Dict[str, Any] | None,
        risk_payload: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        account = account_state or {}
        positions = position_state or {}
        risk = risk_payload or {}

        account_equity = safe_float(
            account.get("equity", account.get("balance", 0.0))
        )
        total_exposure = safe_float(positions.get("total_exposure", 0.0))
        exposure_utilization_pct = 0.0

        if account_equity > 0:
            exposure_utilization_pct = (total_exposure / account_equity) * 100.0

        limit_breaches = risk.get("risk_limits_breached", [])

        if not isinstance(limit_breaches, list):
            limit_breaches = [str(limit_breaches)]

        return {
            "risk_state": str(risk.get("risk_state", "NORMAL")),
            "gate_status": str(risk.get("gate_status", "OPEN")),
            "total_exposure": safe_float(
                risk.get("total_exposure", total_exposure)
            ),
            "exposure_utilization_pct": safe_float(
                risk.get("exposure_utilization_pct", exposure_utilization_pct)
            ),
            "current_drawdown_pct": safe_float(
                risk.get("current_drawdown_pct", 0.0)
            ),
            "max_drawdown_pct": safe_float(risk.get("max_drawdown_pct", 0.0)),
            "daily_loss_limit": safe_float(risk.get("daily_loss_limit", 0.0)),
            "position_limit": safe_int(risk.get("position_limit", 0)),
            "exposure_limit": safe_float(risk.get("exposure_limit", 0.0)),
            "risk_limits_breached": self._normalize_strings(limit_breaches),
        }

    @staticmethod
    def _normalize_strings(values: List[Any]) -> List[str]:
        return [str(value) for value in values if str(value)]
