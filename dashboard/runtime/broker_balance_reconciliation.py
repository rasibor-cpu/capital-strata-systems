from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


BROKER_RECONCILIATION_PAYLOAD_VERSION = "css.broker_reconciliation.v1"
BROKER_RECONCILED = "BROKER_RECONCILED"
BROKER_WARNING = "BROKER_WARNING"
BROKER_DIVERGED = "BROKER_DIVERGED"
BROKER_UNAVAILABLE = "BROKER_UNAVAILABLE"

_MONEY_FIELDS = ("cash_balance", "total_equity", "buying_power")
_ACCOUNT_ALIASES = {
    "cash_balance": ("cash_balance", "cash", "cash_available", "balance"),
    "total_equity": ("total_equity", "equity", "account_equity", "net_liquidation"),
    "buying_power": ("buying_power", "available_margin", "available_funds"),
}
_SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "secret",
    "token",
    "password",
    "credential",
    "private",
    "pem",
    "authorization",
    "bearer",
)


@dataclass(frozen=True)
class ReconciliationFinding:
    code: str
    severity: str
    field: str
    css_value: Any
    broker_value: Any
    difference: str = ""
    message: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "field": self.field,
            "css_value": _json_safe(self.css_value),
            "broker_value": _json_safe(self.broker_value),
            "difference": self.difference,
            "message": self.message,
        }


@dataclass(frozen=True)
class BrokerReconciliationReport:
    broker: str
    mode: str
    status: str
    escalation_level: str
    safe_degradation_required: bool
    recommended_runtime_mode: str
    generated_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    cash_tolerance: Decimal = Decimal("1.00")
    equity_tolerance: Decimal = Decimal("1.00")
    position_qty_tolerance: Decimal = Decimal("0.00000001")
    findings: tuple[ReconciliationFinding, ...] = ()
    css_account: dict[str, Any] = field(default_factory=dict)
    broker_account: dict[str, Any] = field(default_factory=dict)
    css_position_count: int = 0
    broker_position_count: int = 0

    def as_dict(self) -> dict[str, Any]:
        return _json_safe(
            {
                "payload_version": BROKER_RECONCILIATION_PAYLOAD_VERSION,
                "generated_utc": self.generated_utc,
                "broker": self.broker,
                "mode": self.mode,
                "status": self.status,
                "escalation_level": self.escalation_level,
                "safe_degradation_required": self.safe_degradation_required,
                "recommended_runtime_mode": self.recommended_runtime_mode,
                "thresholds": {
                    "cash_tolerance": self.cash_tolerance,
                    "equity_tolerance": self.equity_tolerance,
                    "position_qty_tolerance": self.position_qty_tolerance,
                },
                "summary": {
                    "finding_count": len(self.findings),
                    "css_position_count": self.css_position_count,
                    "broker_position_count": self.broker_position_count,
                },
                "dashboard_visibility": {
                    "visible": True,
                    "header": "LIVE CAPITAL ACTIVE",
                    "status": "visible",
                },
                "css_account": self.css_account,
                "broker_account": self.broker_account,
                "findings": [finding.as_dict() for finding in self.findings],
            }
        )


def reconcile_dashboard_payload(
    dashboard_payload: Mapping[str, Any],
    *,
    cash_tolerance: Decimal | str | int | float = Decimal("1.00"),
    equity_tolerance: Decimal | str | int | float = Decimal("1.00"),
    position_qty_tolerance: Decimal | str | int | float = Decimal("0.00000001"),
) -> BrokerReconciliationReport:
    broker_summary = _mapping(dashboard_payload.get("broker_summary"))
    account_summary = _mapping(dashboard_payload.get("account_summary"))
    position_state = _mapping(dashboard_payload.get("position_state"))
    broker_account = _broker_account_snapshot(broker_summary)
    broker_positions = _broker_position_snapshot(broker_summary)
    mode = _mode(
        dashboard_payload.get(
            "resolved_mode",
            broker_summary.get("broker_mode", "paper"),
        )
    )

    return reconcile_broker_snapshots(
        css_account=account_summary,
        css_positions=_position_items(position_state),
        broker_account=broker_account,
        broker_positions=broker_positions,
        broker=str(broker_summary.get("selected_broker", "NONE")),
        mode=mode,
        broker_connected=bool(broker_summary.get("connected")),
        readiness_status=str(
            broker_summary.get("readiness_status", "BROKER_BLOCKED")
        ),
        cash_tolerance=cash_tolerance,
        equity_tolerance=equity_tolerance,
        position_qty_tolerance=position_qty_tolerance,
    )


def build_broker_reconciliation_payload(
    dashboard_payload: Mapping[str, Any],
) -> dict[str, Any]:
    return reconcile_dashboard_payload(dashboard_payload).as_dict()


def reconcile_broker_snapshots(
    *,
    css_account: Mapping[str, Any],
    css_positions: Sequence[Mapping[str, Any]],
    broker_account: Mapping[str, Any] | None = None,
    broker_positions: Sequence[Mapping[str, Any]] | None = None,
    broker: str = "NONE",
    mode: str = "paper",
    broker_connected: bool = False,
    readiness_status: str = "BROKER_BLOCKED",
    cash_tolerance: Decimal | str | int | float = Decimal("1.00"),
    equity_tolerance: Decimal | str | int | float = Decimal("1.00"),
    position_qty_tolerance: Decimal | str | int | float = Decimal("0.00000001"),
) -> BrokerReconciliationReport:
    money_thresholds = {
        "cash_balance": _decimal(cash_tolerance),
        "total_equity": _decimal(equity_tolerance),
        "buying_power": _decimal(equity_tolerance),
    }
    qty_threshold = _decimal(position_qty_tolerance)
    broker_account_map = _mapping(broker_account)
    broker_position_items = _positions_sequence(broker_positions)
    css_position_items = _positions_sequence(css_positions)
    findings: list[ReconciliationFinding] = []
    normalized_mode = _mode(mode)

    if not broker_connected:
        findings.append(
            ReconciliationFinding(
                code="BROKER_NOT_CONNECTED",
                severity="warning",
                field="broker.connected",
                css_value=True,
                broker_value=False,
                message="Broker is not connected; balance reconciliation is shadow-only.",
            )
        )

    if not broker_account_map and not broker_position_items:
        findings.append(
            ReconciliationFinding(
                code="BROKER_SNAPSHOT_MISSING",
                severity="warning",
                field="broker_snapshot",
                css_value="PRESENT",
                broker_value="MISSING",
                message="Broker account and position snapshots are unavailable.",
            )
        )
    elif not broker_account_map:
        findings.append(
            ReconciliationFinding(
                code="BROKER_ACCOUNT_SNAPSHOT_MISSING",
                severity="warning",
                field="broker_account",
                css_value="PRESENT",
                broker_value="MISSING",
                message="Broker account snapshot is unavailable.",
            )
        )
    elif css_position_items and not broker_position_items:
        findings.append(
            ReconciliationFinding(
                code="BROKER_POSITION_SNAPSHOT_MISSING",
                severity="warning",
                field="broker_positions",
                css_value=len(css_position_items),
                broker_value="MISSING",
                message="Broker position snapshot is unavailable.",
            )
        )

    if broker_account_map:
        findings.extend(
            _account_findings(
                css_account,
                broker_account_map,
                thresholds=money_thresholds,
            )
        )

    if broker_position_items:
        findings.extend(
            _position_findings(
                css_position_items,
                broker_position_items,
                qty_tolerance=qty_threshold,
            )
        )

    status, escalation_level = _status_from_findings(
        findings,
        broker_snapshot_present=bool(broker_account_map or broker_position_items),
    )
    safe_degradation_required = normalized_mode == "live" and status != BROKER_RECONCILED
    recommended_runtime_mode = "paper" if safe_degradation_required else normalized_mode

    if readiness_status == "BROKER_BLOCKED" and normalized_mode == "live":
        safe_degradation_required = True
        recommended_runtime_mode = "paper"
        if status == BROKER_RECONCILED:
            status = BROKER_WARNING
            escalation_level = "warning"

    return BrokerReconciliationReport(
        broker=str(broker or "NONE"),
        mode=normalized_mode,
        status=status,
        escalation_level=escalation_level,
        safe_degradation_required=safe_degradation_required,
        recommended_runtime_mode=recommended_runtime_mode,
        cash_tolerance=money_thresholds["cash_balance"],
        equity_tolerance=money_thresholds["total_equity"],
        position_qty_tolerance=qty_threshold,
        findings=tuple(findings),
        css_account=_safe_account(css_account),
        broker_account=_safe_account(broker_account_map),
        css_position_count=len(css_position_items),
        broker_position_count=len(broker_position_items),
    )


def append_reconciliation_log(
    report: BrokerReconciliationReport,
    path: str | Path,
) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(report.as_dict(), sort_keys=True) + "\n")


def _account_findings(
    css_account: Mapping[str, Any],
    broker_account: Mapping[str, Any],
    *,
    thresholds: Mapping[str, Decimal],
) -> tuple[ReconciliationFinding, ...]:
    findings: list[ReconciliationFinding] = []
    for field_name in _MONEY_FIELDS:
        css_value = _decimal(_first_present(css_account, (field_name,)))
        broker_value = _decimal(_first_present(broker_account, _ACCOUNT_ALIASES[field_name]))
        difference = abs(css_value - broker_value)
        threshold = thresholds[field_name]
        if difference > threshold:
            findings.append(
                ReconciliationFinding(
                    code="ACCOUNT_BALANCE_DIVERGENCE",
                    severity="error",
                    field=field_name,
                    css_value=css_value,
                    broker_value=broker_value,
                    difference=str(difference),
                    message=f"{field_name} differs by {difference}, above tolerance {threshold}.",
                )
            )
    return tuple(findings)


def _position_findings(
    css_positions: Sequence[Mapping[str, Any]],
    broker_positions: Sequence[Mapping[str, Any]],
    *,
    qty_tolerance: Decimal,
) -> tuple[ReconciliationFinding, ...]:
    findings: list[ReconciliationFinding] = []
    css_by_key = {_position_key(item): item for item in css_positions}
    broker_by_key = {_position_key(item): item for item in broker_positions}
    all_keys = sorted(set(css_by_key) | set(broker_by_key))

    for key in all_keys:
        css_item = css_by_key.get(key)
        broker_item = broker_by_key.get(key)

        if css_item is None:
            findings.append(
                ReconciliationFinding(
                    code="BROKER_POSITION_NOT_IN_CSS",
                    severity="error",
                    field=f"position.{key}",
                    css_value="MISSING",
                    broker_value=_position_summary(broker_item or {}),
                    message="Broker reports a position not present in CSS state.",
                )
            )
            continue

        if broker_item is None:
            findings.append(
                ReconciliationFinding(
                    code="CSS_POSITION_NOT_IN_BROKER",
                    severity="error",
                    field=f"position.{key}",
                    css_value=_position_summary(css_item),
                    broker_value="MISSING",
                    message="CSS reports a position not present in broker state.",
                )
            )
            continue

        css_qty = _decimal(_first_present(css_item, ("qty", "quantity", "units")))
        broker_qty = _decimal(
            _first_present(broker_item, ("qty", "quantity", "units", "position"))
        )
        difference = abs(css_qty - broker_qty)

        if difference > qty_tolerance:
            findings.append(
                ReconciliationFinding(
                    code="POSITION_QTY_DIVERGENCE",
                    severity="error",
                    field=f"position.{key}.qty",
                    css_value=css_qty,
                    broker_value=broker_qty,
                    difference=str(difference),
                    message=f"Position quantity differs by {difference}, above tolerance {qty_tolerance}.",
                )
            )

        css_side = _side(css_item.get("side"))
        broker_side = _side(broker_item.get("side"))

        if broker_side and css_side and css_side != broker_side:
            findings.append(
                ReconciliationFinding(
                    code="POSITION_SIDE_DIVERGENCE",
                    severity="error",
                    field=f"position.{key}.side",
                    css_value=css_side,
                    broker_value=broker_side,
                    message="Position side differs between CSS and broker.",
                )
            )

    return tuple(findings)


def _status_from_findings(
    findings: Sequence[ReconciliationFinding],
    *,
    broker_snapshot_present: bool,
) -> tuple[str, str]:
    if not broker_snapshot_present:
        return BROKER_UNAVAILABLE, "info"
    if any(finding.severity == "error" for finding in findings):
        return BROKER_DIVERGED, "error"
    if findings:
        return BROKER_WARNING, "warning"
    return BROKER_RECONCILED, "none"


def _broker_account_snapshot(broker_summary: Mapping[str, Any]) -> Mapping[str, Any]:
    return _mapping(
        broker_summary.get("account_snapshot")
        or broker_summary.get("broker_account_snapshot")
        or broker_summary.get("account")
    )


def _broker_position_snapshot(
    broker_summary: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    raw = (
        broker_summary.get("position_snapshot")
        or broker_summary.get("broker_position_snapshot")
        or broker_summary.get("positions")
        or []
    )
    return _positions_sequence(raw)


def _position_items(position_state: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    return _positions_sequence(position_state.get("positions", []))


def _positions_sequence(value: Any) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _position_key(item: Mapping[str, Any]) -> str:
    asset_class = str(item.get("asset_class", "UNKNOWN")).strip().upper() or "UNKNOWN"
    symbol = str(item.get("symbol", "UNKNOWN")).strip().upper() or "UNKNOWN"
    return f"{asset_class}:{symbol}"


def _position_summary(item: Mapping[str, Any]) -> dict[str, Any]:
    return _json_safe(
        {
            "symbol": item.get("symbol", "UNKNOWN"),
            "asset_class": item.get("asset_class", "UNKNOWN"),
            "side": item.get("side", "UNKNOWN"),
            "qty": item.get("qty", item.get("quantity", item.get("units", 0))),
        }
    )


def _safe_account(value: Mapping[str, Any]) -> dict[str, Any]:
    return _json_safe(
        {
            "cash_balance": _first_present(value, _ACCOUNT_ALIASES["cash_balance"]),
            "total_equity": _first_present(value, _ACCOUNT_ALIASES["total_equity"]),
            "buying_power": _first_present(value, _ACCOUNT_ALIASES["buying_power"]),
            "currency": value.get("currency", "USD"),
        }
    )


def _first_present(value: Mapping[str, Any], keys: Sequence[str]) -> Any:
    for key in keys:
        if key in value and value.get(key) not in (None, ""):
            return value.get(key)
    return 0


def _side(value: Any) -> str:
    normalized = str(value or "").strip().upper()
    if normalized in {"BUY", "LONG"}:
        return "LONG"
    if normalized in {"SELL", "SHORT"}:
        return "SHORT"
    return normalized


def _mode(value: Any) -> str:
    return "live" if str(value or "").strip().lower() == "live" else "paper"


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value if value not in (None, "") else 0))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): (
                "REDACTED" if _is_sensitive_key(str(key)) else _json_safe(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    return value


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    return any(part in lowered for part in _SENSITIVE_KEY_PARTS)