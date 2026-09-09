from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from backend.brokers.questrade_readonly import parse_questrade_readonly_response
from dashboard.runtime.broker_balance_reconciliation import reconcile_broker_snapshots


CURRENT = "CURRENT"
STALE = "STALE"
UNAVAILABLE = "UNAVAILABLE"
_FRESHNESS_SECONDS = 300


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return result if result.is_finite() else None


def _timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc)


def _money(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


@dataclass(frozen=True)
class MissionControlBrokerState:
    broker_name: str = "UNKNOWN"
    account_reference: str | None = None
    account_mode: str = "UNKNOWN"
    capital_provenance: str = "UNKNOWN"
    broker_connected: bool = False
    broker_authenticated: bool = False
    data_freshness: str = UNAVAILABLE
    data_timestamp: str | None = None
    account_currency: str | None = None
    total_equity: Decimal | None = None
    cash: Decimal | None = None
    buying_power: Decimal | None = None
    margin_used: Decimal | None = None
    margin_available: Decimal | None = None
    positions_count: int | None = None
    open_orders_count: int | None = None
    session_realized_pnl: Decimal | None = None
    session_unrealized_pnl: Decimal | None = None
    session_total_pnl: Decimal | None = None
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False
    advisory_only: bool = True
    state_complete: bool = False
    state_reason_codes: tuple[str, ...] = field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    positions: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    maturity_profile: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    reconciliation_status: str = "UNAVAILABLE"
    reconciliation_findings: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in (
            "total_equity", "cash", "buying_power", "margin_used",
            "margin_available", "session_realized_pnl", "session_unrealized_pnl",
            "session_total_pnl",
        ):
            payload[key] = _money(payload[key])
        payload["state_reason_codes"] = list(self.state_reason_codes)
        payload["evidence_refs"] = list(self.evidence_refs)
        payload["positions"] = [dict(item) for item in self.positions]
        payload["maturity_profile"] = [dict(item) for item in self.maturity_profile]
        payload["read_only"] = True
        return payload


def build_mission_control_state(
    broker_payload: dict[str, Any] | None = None,
    *,
    local_account: dict[str, Any] | None = None,
    local_positions: list[dict[str, Any]] | None = None,
) -> MissionControlBrokerState:
    raw = dict(broker_payload or {})
    requested_provenance = str(raw.get("capital_provenance", "")).upper()
    if str(raw.get("broker_name", raw.get("selected_broker", "UNKNOWN"))).upper() == "QUESTRADE":
        normalized = parse_questrade_readonly_response(raw.get("response", raw))
        if requested_provenance:
            normalized["capital_provenance"] = requested_provenance
    else:
        normalized = raw

    account = normalized.get("account") if isinstance(normalized.get("account"), dict) else normalized
    balances = normalized.get("balances") if isinstance(normalized.get("balances"), dict) else account
    status = str(normalized.get("status", "UNAVAILABLE")).upper()
    timestamp = normalized.get("data_timestamp") or normalized.get("timestamp")
    parsed_timestamp = _timestamp(timestamp)
    age = (datetime.now(timezone.utc) - parsed_timestamp).total_seconds() if parsed_timestamp else None
    freshness = UNAVAILABLE if status != "AVAILABLE" or parsed_timestamp is None else (STALE if age > _FRESHNESS_SECONDS else CURRENT)

    connected = bool(normalized.get("broker_connected", normalized.get("connected", status == "AVAILABLE")))
    authenticated = bool(normalized.get("broker_authenticated", normalized.get("authenticated", status == "AVAILABLE")))
    mode = str(normalized.get("account_mode", normalized.get("broker_mode", "UNKNOWN"))).upper()
    explicit_provenance = str(normalized.get("capital_provenance", "")).upper()
    provenance = explicit_provenance if explicit_provenance in {"REAL_BROKER", "SIMULATED_PAPER", "UNKNOWN", "UNAVAILABLE"} else ("SIMULATED_PAPER" if mode in {"PAPER", "SIMULATED"} else "UNKNOWN")
    reasons = set(str(item) for item in normalized.get("reason_codes", []) if item)
    if not connected:
        reasons.add("BROKER_NOT_CONNECTED")
    if not authenticated:
        reasons.add("AUTHENTICATION_REQUIRED")
    if freshness == STALE:
        reasons.add("DATA_STALE")
    if freshness == UNAVAILABLE:
        reasons.add("BALANCE_UNAVAILABLE")
    if provenance == "SIMULATED_PAPER":
        reasons.add("SIMULATED_ACCOUNT")
    positions = normalized.get("positions")
    position_rows = tuple(dict(item) for item in positions if isinstance(item, dict)) if isinstance(positions, list) else tuple()
    if positions is None:
        reasons.add("POSITIONS_UNAVAILABLE")
    execution_armed = bool(normalized.get("broker_execution_armed", False))
    execution_allowed = bool(normalized.get("execution_allowed", False)) and provenance == "REAL_BROKER" and freshness == CURRENT and execution_armed
    reasons.add("ADVISORY_ONLY")
    reasons.add("LIVE_AUTHORITY_ABSENT")
    reasons.add("EXECUTION_BLOCKED")
    if not execution_armed:
        reasons.add("EXECUTION_NOT_ARMED")
    reconciliation_status = "UNAVAILABLE"
    reconciliation_findings: tuple[dict[str, Any], ...] = tuple()
    if local_account is not None or local_positions is not None:
        report = reconcile_broker_snapshots(
            css_account=local_account or {},
            css_positions=local_positions or [],
            broker_account=balances if isinstance(balances, dict) else {},
            broker_positions=position_rows,
            broker=str(normalized.get("broker_name", "UNKNOWN")),
            mode=mode,
            broker_connected=connected,
        )
        reconciliation_status = {
            "BROKER_RECONCILED": "MATCHED",
            "BROKER_DIVERGED": "MISMATCH",
            "BROKER_WARNING": "INCOMPLETE",
            "BROKER_UNAVAILABLE": "UNAVAILABLE",
        }.get(report.status, "UNAVAILABLE")
        reconciliation_findings = tuple(item.as_dict() for item in report.findings)
    return MissionControlBrokerState(
        broker_name=str(normalized.get("broker_name", normalized.get("selected_broker", "UNKNOWN"))).upper(),
        account_reference=str(account.get("account_reference", account.get("accountId"))) if account.get("account_reference", account.get("accountId")) is not None else None,
        account_mode=mode,
        capital_provenance=provenance,
        broker_connected=connected,
        broker_authenticated=authenticated,
        data_freshness=freshness,
        data_timestamp=str(timestamp) if timestamp else None,
        account_currency=account.get("currency", account.get("account_currency")),
        total_equity=_decimal(balances.get("total_equity", balances.get("equity"))),
        cash=_decimal(balances.get("cash", balances.get("cash_balance"))),
        buying_power=_decimal(balances.get("buying_power")),
        margin_used=_decimal(balances.get("margin_used")),
        margin_available=_decimal(balances.get("margin_available", balances.get("available_margin"))),
        positions_count=len(position_rows) if positions is not None else None,
        open_orders_count=(
            int(normalized["open_orders_count"])
            if isinstance(normalized.get("open_orders_count"), int)
            else None
        ),
        session_realized_pnl=_decimal(normalized.get("session_realized_pnl")),
        session_unrealized_pnl=_decimal(normalized.get("session_unrealized_pnl")),
        session_total_pnl=_decimal(normalized.get("session_total_pnl")),
        execution_allowed=execution_allowed,
        live_trading_blocked=True,
        broker_execution_armed=execution_armed,
        advisory_only=True,
        state_complete=bool(connected and authenticated and freshness == CURRENT and balances is not None and positions is not None),
        state_reason_codes=tuple(sorted(reasons)),
        evidence_refs=tuple(str(item) for item in normalized.get("evidence_refs", ["QUESTRADE_READONLY"])),
        positions=position_rows,
        maturity_profile=tuple(dict(item) for item in normalized.get("maturity_profile", []) if isinstance(item, dict)),
        reconciliation_status=reconciliation_status,
        reconciliation_findings=reconciliation_findings,
    )


__all__ = ["MissionControlBrokerState", "build_mission_control_state", "CURRENT", "STALE", "UNAVAILABLE"]