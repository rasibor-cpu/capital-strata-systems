from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from backend.options.options_income_dashboard_payloads import DEFAULT_TIMESTAMP, _mapping, _timestamp
from backend.options.paper_position_repository import SAFE_FLAGS


OPERATIONAL_STATUSES = {"ONLINE", "DEGRADED", "OFFLINE", "UNAVAILABLE"}


class OptionsIncomeOperationalIntelligenceError(ValueError):
    """Raised when operational status generation must fail closed."""


class OptionsIncomeOperationalIntelligence:
    def assess(
        self,
        *,
        summary: Mapping[str, Any],
        opportunities: Mapping[str, Any],
        positions: Mapping[str, Any],
        rolls: Mapping[str, Any],
        portfolio: Mapping[str, Any],
        risk: Mapping[str, Any],
        generated_at: str = DEFAULT_TIMESTAMP,
        now: str = DEFAULT_TIMESTAMP,
        max_age_seconds: int = 900,
        repository_corruption: bool = False,
        last_failed_assessment: str | None = None,
        failure_reason: str = "",
    ) -> dict[str, Any]:
        _timestamp(generated_at, "generated_at")
        _timestamp(now, "now")
        if max_age_seconds < 0:
            raise OptionsIncomeOperationalIntelligenceError("max_age_seconds cannot be negative")
        sections = {
            "summary": _mapping(summary),
            "opportunities": _mapping(opportunities),
            "positions": _mapping(positions),
            "rolls": _mapping(rolls),
            "portfolio": _mapping(portfolio),
            "risk": _mapping(risk),
        }
        module_availability = {
            "opportunity_scanner": _section_status(sections["opportunities"], ("accepted_candidates", "rejected_candidates")),
            "paper_lifecycle": _section_status(sections["positions"], ("active_positions", "completed_positions")),
            "position_manager": _section_status(sections["positions"], ("active_positions", "completed_positions")),
            "rolling_engine": _section_status(sections["rolls"], ("recommendations",)),
            "portfolio_engine": _section_status(sections["portfolio"], ("portfolio_id", "allocations")),
            "greeks_engine": _section_status(sections["risk"], ("portfolio_delta", "greeks_by_underlying")),
            "risk_engine": _section_status(sections["risk"], ("risk_status", "approval_status")),
            "stress_engine": _section_status(sections["risk"], ("stress_scenarios",)),
            "api_payload": "ONLINE",
        }
        stale = _is_stale(generated_at, now, max_age_seconds)
        invalid_posture = sections["summary"].get("execution_allowed") is not False or sections["summary"].get("live_trading_blocked") is not True
        missing_data = any(status == "UNAVAILABLE" for status in module_availability.values())
        degraded_data = any(status == "DEGRADED" for status in module_availability.values())
        status = "OFFLINE" if repository_corruption or invalid_posture else ("DEGRADED" if stale or missing_data or degraded_data or failure_reason else "ONLINE")
        freshness = "STALE" if stale else "FRESH"
        return {
            "status": status,
            "module_availability": module_availability,
            "data_freshness": freshness,
            "repository_health": "OFFLINE" if repository_corruption else "ONLINE",
            "scanner_health": module_availability["opportunity_scanner"],
            "lifecycle_health": module_availability["paper_lifecycle"],
            "position_manager_health": module_availability["position_manager"],
            "portfolio_engine_health": module_availability["portfolio_engine"],
            "greeks_health": module_availability["greeks_engine"],
            "risk_engine_health": module_availability["risk_engine"],
            "stress_engine_health": module_availability["stress_engine"],
            "api_payload_health": module_availability["api_payload"],
            "last_successful_assessment": generated_at if status in {"ONLINE", "DEGRADED"} else "",
            "last_failed_assessment": str(last_failed_assessment or ""),
            "failure_reason": "unsafe execution posture" if invalid_posture else str(failure_reason or ""),
            "stale_data_reason": f"payload older than {max_age_seconds} seconds" if stale else "",
            "certification_status": "CERTIFIED_PAPER" if status == "ONLINE" else ("DEGRADED_PAPER" if status == "DEGRADED" else "UNAVAILABLE"),
            "paper_only": True,
            **SAFE_FLAGS,
        }


def _section_status(section: Mapping[str, Any], required: tuple[str, ...]) -> str:
    if not section:
        return "UNAVAILABLE"
    missing = [field for field in required if field not in section]
    if missing:
        return "DEGRADED"
    return "ONLINE"


def _is_stale(generated_at: str, now: str, max_age_seconds: int) -> bool:
    start = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    end = datetime.fromisoformat(now.replace("Z", "+00:00"))
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return (end - start).total_seconds() > max_age_seconds


__all__ = ["OPERATIONAL_STATUSES", "OptionsIncomeOperationalIntelligence", "OptionsIncomeOperationalIntelligenceError"]
