from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from backend.app.brokers.broker_registry import (
    broker_supports_asset_class,
    broker_supports_mode,
    get_adapter,
    get_broker_spec,
)
from backend.app.brokers.credential_loader import (
    credential_file_exists,
    load_credentials,
)
from backend.app.brokers.execution_boundary import validate_execution_boundary
from backend.governance.css_unified_trade_gate import CSSUnifiedTradeGate


LIVE_READINESS_PASS = "PASS"
LIVE_READINESS_FAIL = "FAIL"
LIVE_READINESS_PAYLOAD_VERSION = "css.broker_live_readiness_certification.v1"

KNOWN_ENGINE_MODES = {
    "SAFE",
    "CONSERVATIVE",
    "BALANCED",
    "AGGRESSIVE",
    "EXPANSION",
}
OPERATOR_APPROVAL_ROLES = {"ADMIN", "SUPER_USER"}
FAKE_CAPITAL_SOURCES = {"", "SIMULATED", "PAPER", "DEMO", "FAKE", "UNKNOWN"}
LIVE_CAPITAL_SOURCES = {"LIVE", "BROKER", "REAL", "EXTERNAL_BROKER"}
SENSITIVE_KEY_PARTS = (
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


AuditSink = Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class LiveReadinessCertificationResult:
    broker: str
    broker_mode: str
    asset_class: str
    status: str
    blocking_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    dry_run_only: bool = True
    operator_approval_required: bool = True
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    audit_payload: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return _json_safe(
            {
                "payload_version": LIVE_READINESS_PAYLOAD_VERSION,
                "broker": self.broker,
                "broker_mode": self.broker_mode,
                "asset_class": self.asset_class,
                "status": self.status,
                "blocking_reasons": list(self.blocking_reasons),
                "warnings": list(self.warnings),
                "dry_run_only": self.dry_run_only,
                "operator_approval_required": self.operator_approval_required,
                "timestamp": self.timestamp,
                "audit_payload": self.audit_payload,
            }
        )


def certify_live_readiness(
    *,
    selected_broker: str,
    broker_mode: str,
    asset_class: str,
    capital_source_label: str,
    balance_source: str,
    dry_run_order: Mapping[str, Any] | None,
    session: Mapping[str, Any] | None,
    portfolio_state: Mapping[str, Any] | None,
    engine_mode: str,
    operator_approval: Mapping[str, Any] | None = None,
    requested_broker: str | None = None,
    credential_base_dir: str | Path = ".",
    audit_sink: AuditSink | None = None,
) -> LiveReadinessCertificationResult:
    """
    Certify that a broker has enough evidence for live-readiness review.

    This framework never places orders, never enables live mode, and never
    returns credential values. It fails closed unless every blocking check
    passes, including explicit operator approval.
    """

    broker = _normalize_broker(selected_broker)
    requested = _normalize_broker(requested_broker or selected_broker)
    mode = _normalize_mode(broker_mode)
    asset = _normalize_asset(asset_class)
    order = _mapping(dry_run_order)
    session_payload = _mapping(session)
    portfolio_payload = _mapping(portfolio_state)
    approval = _mapping(operator_approval)
    engine = str(engine_mode or "").strip().upper()
    blocking: list[str] = []
    warnings: list[str] = []

    _check_broker_identity(
        blocking,
        warnings,
        broker=broker,
        requested=requested,
        mode=mode,
        asset_class=asset,
    )
    _check_credentials(
        blocking,
        warnings,
        broker=broker,
        credential_base_dir=credential_base_dir,
    )
    _check_capital_source(
        blocking,
        mode=mode,
        capital_source_label=capital_source_label,
        balance_source=balance_source,
    )
    _check_execution_safety(
        blocking,
        warnings,
        broker=broker,
        asset_class=asset,
        order=order,
    )
    _check_governance(
        blocking,
        warnings,
        asset_class=asset,
        order=order,
        session=session_payload,
        portfolio_state=portfolio_payload,
        engine_mode=engine,
        approval=approval,
    )

    status = LIVE_READINESS_PASS if not blocking else LIVE_READINESS_FAIL
    audit_payload = _audit_payload(
        broker=broker or "NONE",
        mode=mode,
        asset_class=asset or "UNKNOWN",
        status=status,
        blocking_reasons=blocking,
        warnings=warnings,
        order=order,
        session=session_payload,
        approval=approval,
    )
    result = LiveReadinessCertificationResult(
        broker=broker or "NONE",
        broker_mode=mode,
        asset_class=asset or "UNKNOWN",
        status=status,
        blocking_reasons=tuple(blocking),
        warnings=tuple(warnings),
        audit_payload=audit_payload,
    )

    if audit_sink is not None:
        audit_sink(result.audit_payload)

    return result


def append_live_readiness_certification_log(
    result: LiveReadinessCertificationResult,
    path: str | Path,
) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(result.as_dict(), sort_keys=True) + "\n")


def _check_broker_identity(
    blocking: list[str],
    warnings: list[str],
    *,
    broker: str,
    requested: str,
    mode: str,
    asset_class: str,
) -> None:
    if not broker:
        blocking.append("broker_not_selected")
        return

    if requested and requested != broker:
        blocking.append("selected_broker_mismatch")

    try:
        get_broker_spec(broker)
    except Exception:
        blocking.append("broker_not_registered")
        return

    try:
        get_adapter(broker)
    except Exception:
        blocking.append("broker_adapter_unavailable")

    try:
        if not broker_supports_mode(broker, mode):
            blocking.append("broker_mode_not_supported")
    except Exception:
        blocking.append("broker_mode_unknown")

    try:
        if not broker_supports_asset_class(broker, asset_class):
            blocking.append("asset_class_not_supported")
    except Exception:
        blocking.append("asset_class_support_unknown")

    if broker in {"none", "demo", "paper"}:
        warnings.append("non_executable_broker_identity")


def _check_credentials(
    blocking: list[str],
    warnings: list[str],
    *,
    broker: str,
    credential_base_dir: str | Path,
) -> None:
    if not broker:
        return

    base_dir = str(credential_base_dir)
    try:
        if not credential_file_exists(broker, base_dir=base_dir):
            blocking.append("credentials_missing")
            return
    except Exception:
        blocking.append("credential_manifest_unavailable")
        return

    credentials = load_credentials(broker, base_dir=base_dir)
    if not credentials:
        blocking.append("credentials_unloadable")
        return

    if not isinstance(credentials, Mapping):
        blocking.append("credentials_invalid_shape")
        return

    warnings.append("credentials_loaded_redacted")


def _check_capital_source(
    blocking: list[str],
    *,
    mode: str,
    capital_source_label: str,
    balance_source: str,
) -> None:
    capital_source = str(capital_source_label or "").strip().upper()
    source = str(balance_source or "").strip().upper()
    boundary = validate_execution_boundary(
        selected_mode=mode,
        capital_source_label=capital_source,
    )
    if not boundary.allowed:
        blocking.append(boundary.reason)

    if not source:
        blocking.append("balance_source_missing")

    if mode == "live":
        if capital_source in FAKE_CAPITAL_SOURCES:
            blocking.append("live_mode_requires_real_capital_source")
        if source not in LIVE_CAPITAL_SOURCES:
            blocking.append("live_mode_requires_broker_balance_source")

    if mode == "paper" and (
        capital_source in LIVE_CAPITAL_SOURCES or source in LIVE_CAPITAL_SOURCES
    ):
        blocking.append("paper_mode_cannot_use_live_capital")


def _check_execution_safety(
    blocking: list[str],
    warnings: list[str],
    *,
    broker: str,
    asset_class: str,
    order: Mapping[str, Any],
) -> None:
    if not order:
        blocking.append("dry_run_order_missing")
        return

    if _normalize_broker(order.get("broker", broker)) != broker:
        blocking.append("dry_run_order_broker_mismatch")

    if _normalize_asset(order.get("asset_class", asset_class)) != asset_class:
        blocking.append("dry_run_order_asset_mismatch")

    if not _bool(order.get("dry_run")):
        blocking.append("dry_run_flag_missing")

    if _bool(order.get("submitted_to_broker")):
        blocking.append("dry_run_order_was_submitted")

    if _bool(order.get("would_place_live_order")):
        blocking.append("dry_run_would_place_live_order")

    if _safe_float(order.get("quantity")) <= 0:
        blocking.append("dry_run_quantity_invalid")

    if not str(order.get("symbol") or "").strip():
        blocking.append("dry_run_symbol_missing")

    if not str(order.get("side") or "").strip():
        blocking.append("dry_run_side_missing")

    warnings.append("dry_run_only_no_order_placement")


def _check_governance(
    blocking: list[str],
    warnings: list[str],
    *,
    asset_class: str,
    order: Mapping[str, Any],
    session: Mapping[str, Any],
    portfolio_state: Mapping[str, Any],
    engine_mode: str,
    approval: Mapping[str, Any],
) -> None:
    if engine_mode not in KNOWN_ENGINE_MODES:
        blocking.append("engine_mode_unknown")

    if not session:
        blocking.append("session_missing")

    if not approval:
        blocking.append("operator_approval_missing")
    elif not _operator_approval_valid(approval):
        blocking.append("operator_approval_invalid")

    try:
        gate = CSSUnifiedTradeGate()
        decision = gate.approve_trade(
            candidate={
                "symbol": order.get("symbol"),
                "asset_class": asset_class,
                "expected_value": _safe_float(order.get("expected_value"), 1.0),
                "cost": _safe_float(order.get("cost"), 0.0),
                "probability": _safe_float(order.get("probability"), 1.0),
            },
            session=dict(session),
            portfolio_state=dict(portfolio_state),
            engine_mode=engine_mode,
        )
    except Exception as exc:
        blocking.append(f"governance_gate_error:{type(exc).__name__}")
        return

    if not getattr(decision, "approved", False):
        blocking.append(f"governance_gate_rejected:{decision.reason}")
    else:
        warnings.append("governance_gate_approved_dry_run_candidate")


def _operator_approval_valid(approval: Mapping[str, Any]) -> bool:
    if not _bool(approval.get("approved")):
        return False
    role = str(
        approval.get("approver_role")
        or approval.get("role")
        or ""
    ).strip().upper()
    if role not in OPERATOR_APPROVAL_ROLES:
        return False
    if not str(approval.get("approval_id") or "").strip():
        return False
    expires_at = approval.get("expires_utc")
    if expires_at:
        try:
            expiry = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
            if expiry <= datetime.now(timezone.utc):
                return False
        except ValueError:
            return False
    return True


def _audit_payload(
    *,
    broker: str,
    mode: str,
    asset_class: str,
    status: str,
    blocking_reasons: list[str],
    warnings: list[str],
    order: Mapping[str, Any],
    session: Mapping[str, Any],
    approval: Mapping[str, Any],
) -> dict[str, Any]:
    return _json_safe(
        {
            "payload_version": LIVE_READINESS_PAYLOAD_VERSION,
            "event_type": "broker_live_readiness_certification_attempt",
            "broker": broker,
            "broker_mode": mode,
            "asset_class": asset_class,
            "status": status,
            "blocking_reasons": list(blocking_reasons),
            "warnings": list(warnings),
            "dry_run_only": True,
            "operator_approval_required": True,
            "session_user_id": session.get("user_id", "UNKNOWN"),
            "session_role": session.get("role", "UNKNOWN"),
            "approval_id": approval.get("approval_id", ""),
            "approver_role": approval.get("approver_role", approval.get("role", "")),
            "order": {
                "broker": order.get("broker"),
                "symbol": order.get("symbol"),
                "asset_class": order.get("asset_class"),
                "side": order.get("side"),
                "quantity": order.get("quantity"),
                "order_type": order.get("order_type"),
                "dry_run": order.get("dry_run"),
                "submitted_to_broker": order.get("submitted_to_broker"),
                "would_place_live_order": order.get("would_place_live_order"),
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


def _normalize_broker(value: Any) -> str:
    text = str(value or "").strip().lower()
    return "" if text in {"", "none", "no_broker_selected"} else text


def _normalize_mode(value: Any) -> str:
    return "live" if str(value or "").strip().lower() == "live" else "paper"


def _normalize_asset(value: Any) -> str:
    asset = str(value or "").strip().lower()
    aliases = {
        "currency": "fx",
        "currencies": "fx",
        "forex": "fx",
        "stock": "equities",
        "stocks": "equities",
        "equity": "equities",
    }
    return aliases.get(asset, asset)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


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
    if isinstance(value, Path):
        return str(value)
    return value


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def fresh_session(
    *,
    user_id: str = "certifier",
    role: str = "SUPER_USER",
) -> dict[str, Any]:
    return {"user_id": user_id, "role": role, "created": time.time()}


__all__ = [
    "LIVE_READINESS_FAIL",
    "LIVE_READINESS_PASS",
    "LIVE_READINESS_PAYLOAD_VERSION",
    "LiveReadinessCertificationResult",
    "append_live_readiness_certification_log",
    "certify_live_readiness",
    "fresh_session",
]
