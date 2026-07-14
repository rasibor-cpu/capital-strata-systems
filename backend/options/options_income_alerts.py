from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping

from backend.options.options_income_dashboard_payloads import DEFAULT_TIMESTAMP, _list, _mapping, _number
from backend.options.paper_position_repository import SAFE_FLAGS


class OptionsIncomeAlertError(ValueError):
    """Raised when alert generation fails closed."""


class OptionsIncomeAlertEngine:
    def build_alerts(
        self,
        *,
        summary: Mapping[str, Any],
        positions: Mapping[str, Any],
        portfolio: Mapping[str, Any],
        risk: Mapping[str, Any],
        operational: Mapping[str, Any] | None = None,
        timestamp: str = DEFAULT_TIMESTAMP,
    ) -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []
        op = _mapping(operational)
        if risk.get("risk_status") == "RED" or risk.get("approval_status", "").startswith("REJECTED"):
            alerts.append(_alert("CRITICAL", "risk-governance", "Risk approval rejected", "Risk-governance approval is rejected.", risk, ["portfolio"], timestamp))
        if _list(risk.get("hard_limit_breaches")):
            alerts.append(_alert("CRITICAL", "risk-limit", "Risk limit breach", "One or more hard risk limits breached.", {"breaches": risk.get("hard_limit_breaches")}, ["portfolio"], timestamp))
        assignment = _mapping(risk.get("assignment_exposure"))
        if _number(assignment.get("portfolio_assignment_ratio")) >= 0.90:
            alerts.append(_alert("WARNING", "assignment", "Assignment concentration elevated", "Portfolio assignment exposure is high.", assignment, list(assignment.get("assignment_concentration", {}).keys()), timestamp))
        if _number(portfolio.get("portfolio_utilization")) >= 0.85:
            alerts.append(_alert("WARNING", "collateral", "Collateral over-utilization", "Portfolio utilization is above advisory threshold.", portfolio, ["portfolio"], timestamp))
        if _list(risk.get("unavailable_risk_data")):
            alerts.append(_alert("WARNING", "data", "Missing Greeks or IV", "Risk payload has unavailable data.", {"unavailable": risk.get("unavailable_risk_data")}, risk.get("unavailable_risk_data"), timestamp))
        if op.get("data_freshness") == "STALE":
            alerts.append(_alert("WARNING", "freshness", "Stale data", str(op.get("stale_data_reason", "Data is stale.")), op, ["options_income"], timestamp))
        if _number(summary.get("remaining_income_target")) > _number(summary.get("monthly_income_target")) * 0.50:
            alerts.append(_alert("INFO", "income-target", "Income target shortfall", "Expected income is below target pace.", summary, ["portfolio"], timestamp))
        near_expiry = [row["position_id"] for row in _list(positions.get("active_positions")) if _number(_mapping(row).get("days_remaining")) <= 7]
        if near_expiry:
            alerts.append(_alert("INFO", "expiry", "Positions near expiry", "One or more paper positions are near expiry.", {"positions": near_expiry}, near_expiry, timestamp))
        rollable = [row["position_id"] for row in _list(positions.get("active_positions")) if _mapping(row).get("roll_eligibility") is True]
        if rollable:
            alerts.append(_alert("INFO", "rolling", "Roll eligibility detected", "One or more paper positions are roll eligible.", {"positions": rollable}, rollable, timestamp))
        if summary.get("execution_allowed") is not False:
            alerts.append(_alert("CRITICAL", "safety", "Execution-enabled posture detected", "Options income dashboard must remain paper-only.", summary, ["options_income"], timestamp))
        alerts.sort(key=lambda row: ({"CRITICAL": 0, "WARNING": 1, "INFO": 2}.get(row["severity"], 9), row["category"], row["alert_id"]))
        return alerts


def _alert(
    severity: str,
    category: str,
    message: str,
    reason: str,
    metrics: Mapping[str, Any],
    entities: Any,
    timestamp: str,
) -> dict[str, Any]:
    base = f"{severity}|{category}|{message}|{','.join(str(item) for item in _list(entities))}"
    return {
        "alert_id": f"OI008-{sha256(base.encode('utf-8')).hexdigest()[:12]}",
        "severity": severity,
        "category": category,
        "message": message,
        "reason": reason,
        "supporting_metrics": dict(metrics),
        "affected_entities": _list(entities),
        "timestamp": timestamp,
        "acknowledged": False,
        "paper_only": True,
        **SAFE_FLAGS,
    }


__all__ = ["OptionsIncomeAlertEngine", "OptionsIncomeAlertError"]
