"""Read-only portfolio margin dashboard projection."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from math import isfinite
from typing import Any

from engine.risk.margin_state import MarginState
from engine.risk.portfolio_margin_snapshot import PortfolioMarginSnapshot

PORTFOLIO_MARGIN_DASHBOARD_BUILDER_VERSION = "css.portfolio_margin_dashboard_builder.v2"

_REQUIRED_SNAPSHOT_FIELDS = (
    "portfolio_equity",
    "portfolio_buying_power",
    "portfolio_margin_used",
    "portfolio_margin_available",
    "portfolio_risk_state",
    "broker_count",
    "timestamp",
)
_TREND_VALUES = frozenset({"DATA_UNAVAILABLE", "DETERIORATING", "FLAT", "IMPROVING"})
_SEVERITY = {
    "NORMAL": 0,
    "WARNING": 1,
    "RESTRICTED": 2,
    "CRITICAL": 3,
    "LIQUIDATION_RISK": 4,
}


class PortfolioMarginDashboardBuilder:
    """Builds a read-only dashboard payload from supplied canonical snapshots."""

    def __init__(self, history_store: Any | None = None) -> None:
        self.history_store = history_store

    def build_payload(
        self,
        snapshots: Sequence[Mapping[str, Any] | PortfolioMarginSnapshot] | None = None,
        *,
        risk_events: Sequence[Mapping[str, Any]] | None = None,
        generated_at_utc: str | None = None,
    ) -> dict[str, Any]:
        return build_portfolio_margin_dashboard_payload(
            snapshots=snapshots,
            risk_events=risk_events,
            generated_at_utc=generated_at_utc,
        )


def build_portfolio_margin_dashboard_payload(
    *,
    snapshots: Sequence[Mapping[str, Any] | PortfolioMarginSnapshot] | None = None,
    risk_events: Sequence[Mapping[str, Any]] | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    normalized_snapshots, snapshot_blockers = _normalize_snapshots(snapshots)
    normalized_events, event_blockers = _normalize_events(risk_events)
    blockers = snapshot_blockers + event_blockers
    latest = normalized_snapshots[-1] if normalized_snapshots else {}
    status = "OK" if normalized_snapshots and not blockers else "DATA_UNAVAILABLE"

    return {
        "payload_version": PORTFOLIO_MARGIN_DASHBOARD_BUILDER_VERSION,
        "generated_at_utc": generated_at_utc or _utc_now(),
        "status": status,
        "readiness_status": "READY" if status == "OK" else "BLOCKED",
        "current_snapshot": latest,
        "account_summary": _account_summary(latest),
        "risk_status": _risk_status(latest, blockers),
        "risk_escalation": _risk_escalation(latest),
        "early_warning": _early_warning(normalized_snapshots, normalized_events),
        "trends": _trends(normalized_snapshots, normalized_events),
        "snapshots": normalized_snapshots,
        "risk_events": normalized_events,
        "malformed_snapshot_count": len(snapshot_blockers),
        "malformed_event_count": len(event_blockers),
        "warnings": _warnings(normalized_snapshots, blockers),
        "authority": {
            "runtime_authority": False,
            "execution_authority": False,
            "order_authority": False,
            "broker_authority": False,
        },
        "trading_armed": False,
        "execution_allowed": False,
        "orders_enabled": False,
        "source_metadata": {
            "source": "dashboard.runtime.portfolio_margin_dashboard_builder",
            "canonical_input": "engine.risk.portfolio_margin_snapshot.PortfolioMarginSnapshot",
            "read_only": True,
            "projection_only": True,
            "no_broker_calls": True,
            "no_environment_reads": True,
            "no_filesystem_reads": True,
            "no_filesystem_writes": True,
            "no_order_placement": True,
        },
    }


def _normalize_snapshots(
    snapshots: Sequence[Mapping[str, Any] | PortfolioMarginSnapshot] | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    if not snapshots:
        return [], ["portfolio_margin_snapshots_missing"]

    normalized: list[dict[str, Any]] = []
    blockers: list[str] = []
    for index, snapshot in enumerate(snapshots):
        try:
            raw = _snapshot_mapping(snapshot)
            missing = [field for field in _REQUIRED_SNAPSHOT_FIELDS if raw.get(field) is None]
            if missing:
                blockers.append(f"snapshot_{index}_missing_{missing[0]}")
                continue
            equity = _finite_number(raw["portfolio_equity"])
            buying_power = _finite_number(raw["portfolio_buying_power"])
            margin_used = _finite_number(raw["portfolio_margin_used"])
            margin_available = _finite_number(raw["portfolio_margin_available"])
            broker_count = _finite_int(raw["broker_count"])
            risk_state = _risk_state_value(raw["portfolio_risk_state"])
            timestamp = _text(raw["timestamp"])
            if not timestamp:
                blockers.append(f"snapshot_{index}_missing_timestamp")
                continue
            denominator = margin_used + margin_available
            if denominator <= 0:
                blockers.append(f"snapshot_{index}_invalid_margin_capacity")
                continue
            normalized.append(
                {
                    "portfolio_equity": equity,
                    "portfolio_buying_power": buying_power,
                    "portfolio_margin_used": margin_used,
                    "portfolio_margin_available": margin_available,
                    "portfolio_risk_state": risk_state,
                    "broker_count": broker_count,
                    "maintenance_margin": margin_used,
                    "margin_utilization_pct": round((margin_used / denominator) * 100.0, 6),
                    "timestamp": timestamp,
                }
            )
        except (TypeError, ValueError) as exc:
            blockers.append(f"snapshot_{index}_malformed:{exc}")
    normalized.sort(key=lambda item: (item["timestamp"], item["portfolio_risk_state"]))
    return normalized, blockers


def _normalize_events(
    risk_events: Sequence[Mapping[str, Any]] | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    normalized: list[dict[str, Any]] = []
    blockers: list[str] = []
    for index, event in enumerate(risk_events or ()):
        if not isinstance(event, Mapping):
            blockers.append(f"event_{index}_malformed")
            continue
        risk_state = event.get("risk_state")
        escalation_level = event.get("escalation_level")
        timestamp = _text(event.get("timestamp"))
        if risk_state is None or escalation_level is None or not timestamp:
            blockers.append(f"event_{index}_missing_required_field")
            continue
        try:
            normalized.append(
                {
                    "risk_state": _risk_state_value(risk_state),
                    "escalation_level": _finite_int(escalation_level),
                    "timestamp": timestamp,
                    "message": _text(event.get("message")),
                }
            )
        except (TypeError, ValueError) as exc:
            blockers.append(f"event_{index}_malformed:{exc}")
    normalized.sort(key=lambda item: (item["timestamp"], item["risk_state"], item["escalation_level"]))
    return normalized, blockers


def _snapshot_mapping(
    snapshot: Mapping[str, Any] | PortfolioMarginSnapshot,
) -> dict[str, Any]:
    if isinstance(snapshot, PortfolioMarginSnapshot):
        return {
            "portfolio_equity": snapshot.portfolio_equity,
            "portfolio_buying_power": snapshot.portfolio_buying_power,
            "portfolio_margin_used": snapshot.portfolio_margin_used,
            "portfolio_margin_available": snapshot.portfolio_margin_available,
            "portfolio_risk_state": snapshot.portfolio_risk_state,
            "broker_count": snapshot.broker_count,
            "timestamp": snapshot.timestamp,
        }
    if isinstance(snapshot, Mapping):
        return dict(snapshot)
    raise TypeError("snapshot must be a mapping or PortfolioMarginSnapshot")


def _account_summary(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    if not snapshot:
        return {
            "equity": None,
            "buying_power": None,
            "maintenance_margin": None,
            "margin_available": None,
            "margin_utilization_pct": None,
            "broker_count": None,
            "timestamp": "",
            "status": "DATA_UNAVAILABLE",
        }
    return {
        "equity": snapshot["portfolio_equity"],
        "buying_power": snapshot["portfolio_buying_power"],
        "maintenance_margin": snapshot["maintenance_margin"],
        "margin_available": snapshot["portfolio_margin_available"],
        "margin_utilization_pct": snapshot["margin_utilization_pct"],
        "broker_count": snapshot["broker_count"],
        "timestamp": snapshot["timestamp"],
        "status": "READY",
    }


def _risk_status(snapshot: Mapping[str, Any], blockers: Sequence[str]) -> dict[str, Any]:
    if not snapshot:
        risk_state = "UNKNOWN"
    else:
        risk_state = str(snapshot["portfolio_risk_state"])
    return {
        "risk_state": risk_state,
        "risk_banner": _risk_banner(risk_state),
        "fail_closed": bool(blockers),
        "blockers": list(blockers),
    }


def _risk_escalation(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    risk_state = str(snapshot.get("portfolio_risk_state") or "UNKNOWN")
    level = _SEVERITY.get(risk_state, 0)
    return {
        "risk_state": risk_state,
        "risk_banner": _risk_banner(risk_state),
        "escalation_level": level,
        "escalation_required": level > 0,
        "escalation_message": _escalation_message(risk_state),
    }


def _early_warning(
    snapshots: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if not snapshots:
        return {
            "warning_level": "DATA_UNAVAILABLE",
            "snapshot_count": 0,
            "event_count": len(events),
            "trend_direction": "DATA_UNAVAILABLE",
            "summary": "Data unavailable",
        }
    margin_trend = _margin_utilization_trend(snapshots)
    risk_trend = _risk_state_trend(snapshots)
    latest_state = str(snapshots[-1]["portfolio_risk_state"])
    if latest_state in {"CRITICAL", "LIQUIDATION_RISK"} or (
        risk_trend == "DETERIORATING" and len(events) > 3
    ):
        warning_level = "RED"
        summary = "Persistent escalation trend or liquidation proximity."
    elif latest_state == "RESTRICTED" or len(events) > 1:
        warning_level = "ORANGE"
        summary = "Repeated escalation events."
    elif latest_state == "WARNING" or margin_trend == "DETERIORATING":
        warning_level = "YELLOW"
        summary = "Observable deterioration."
    else:
        warning_level = "GREEN"
        summary = "No material deterioration."
    return {
        "warning_level": warning_level,
        "snapshot_count": len(snapshots),
        "event_count": len(events),
        "trend_direction": margin_trend,
        "summary": summary,
    }


def _trends(
    snapshots: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "margin_utilization_trend": _margin_utilization_trend(snapshots),
        "buying_power_trend": _number_trend(snapshots, "portfolio_buying_power"),
        "equity_trend": _number_trend(snapshots, "portfolio_equity"),
        "risk_state_trend": _risk_state_trend(snapshots),
        "escalation_frequency": float(len(events)),
    }


def _margin_utilization_trend(snapshots: Sequence[Mapping[str, Any]]) -> str:
    return _number_trend(snapshots, "margin_utilization_pct", deteriorates_when="up")


def _number_trend(
    snapshots: Sequence[Mapping[str, Any]],
    field: str,
    *,
    deteriorates_when: str = "down",
) -> str:
    if not snapshots:
        return "DATA_UNAVAILABLE"
    if len(snapshots) < 2:
        return "FLAT"
    previous = float(snapshots[-2][field])
    latest = float(snapshots[-1][field])
    if latest == previous:
        return "FLAT"
    improving = latest > previous if deteriorates_when == "down" else latest < previous
    return "IMPROVING" if improving else "DETERIORATING"


def _risk_state_trend(snapshots: Sequence[Mapping[str, Any]]) -> str:
    if not snapshots:
        return "DATA_UNAVAILABLE"
    if len(snapshots) < 2:
        return "FLAT"
    previous = _SEVERITY.get(str(snapshots[-2]["portfolio_risk_state"]), -1)
    latest = _SEVERITY.get(str(snapshots[-1]["portfolio_risk_state"]), -1)
    if latest == previous:
        return "FLAT"
    return "DETERIORATING" if latest > previous else "IMPROVING"


def _warnings(snapshots: Sequence[Mapping[str, Any]], blockers: Sequence[str]) -> list[str]:
    warnings: list[str] = []
    if not snapshots:
        warnings.append("PORTFOLIO_MARGIN_DATA_UNAVAILABLE")
    if blockers:
        warnings.append("PORTFOLIO_MARGIN_AUTHORITY_FAIL_CLOSED")
    return warnings


def _risk_state_value(value: Any) -> str:
    if isinstance(value, MarginState):
        return value.name
    text = str(value or "").strip().upper()
    if text not in _SEVERITY:
        raise ValueError("unknown portfolio_risk_state")
    return text


def _risk_banner(risk_state: str) -> str:
    return {
        "NORMAL": "Portfolio Margin Healthy",
        "WARNING": "Portfolio Margin Warning",
        "RESTRICTED": "Margin Restrictions Active",
        "CRITICAL": "Margin Stress Detected",
        "LIQUIDATION_RISK": "Immediate Margin Intervention Required",
    }.get(risk_state, "Unknown Margin State")


def _escalation_message(risk_state: str) -> str:
    return {
        "NORMAL": "Portfolio margin is healthy. No escalation required.",
        "WARNING": "Level 1 Escalation: Portfolio margin warning. Monitor closely.",
        "RESTRICTED": "Level 2 Escalation: Margin restrictions active.",
        "CRITICAL": "Level 3 Escalation: Margin stress detected.",
        "LIQUIDATION_RISK": "Level 4 Escalation: Immediate margin intervention required.",
    }.get(risk_state, "Portfolio margin data is unavailable.")


def _finite_number(value: Any) -> float:
    if isinstance(value, bool):
        raise TypeError("boolean is not numeric")
    number = float(value)
    if not isfinite(number):
        raise ValueError("non-finite numeric value")
    return number


def _finite_int(value: Any) -> int:
    if isinstance(value, bool):
        raise TypeError("boolean is not numeric")
    number = int(value)
    if number < 0:
        raise ValueError("negative integer value")
    return number


def _text(value: Any) -> str:
    return str(value or "").strip()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "PORTFOLIO_MARGIN_DASHBOARD_BUILDER_VERSION",
    "PortfolioMarginDashboardBuilder",
    "build_portfolio_margin_dashboard_payload",
]
