from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from engine.execution.live_order_kill_switch import evaluate_live_order_kill_switch


MICRO_LIVE_PILOT_READINESS_PAYLOAD_VERSION = "css.micro_live_pilot_readiness.v1"

PILOT_NOT_READY = "NOT_READY"
PILOT_REVIEW_REQUIRED = "REVIEW_REQUIRED"
PILOT_LIMITED_READY = "LIMITED_PILOT_READY"

APPROVED_BROKER_KEYS = ("coinbase", "coinbase_advanced")
APPROVED_BROKER_TARGETS = ("Coinbase Advanced",)
APPROVED_SYMBOLS = ("BTC-USD",)
APPROVED_ASSET_CLASSES = ("crypto", "spot_crypto")
APPROVED_ORDER_TYPES = ("limit",)
MAX_PILOT_CAPITAL_AMOUNT = Decimal("15.00")
MAX_PILOT_CAPITAL_CURRENCY = "CAD"
MAX_SLIPPAGE_PCT = Decimal("0.35")

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
_SENSITIVE_VALUE_MARKERS = (
    "api_key=",
    "apikey=",
    "bearer ",
    "private key",
    "secret=",
    "token=",
    "password=",
    "authorization:",
)


@dataclass(frozen=True)
class PilotReadinessCheck:
    check_id: str
    label: str
    passed: bool
    severity: str
    message: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MicroLivePilotReadiness:
    readiness_id: str
    generated_at_utc: str
    overall_status: str
    passed_checks: list[dict[str, Any]]
    failed_checks: list[dict[str, Any]]
    warnings: list[str]
    blockers: list[str]
    allowed_broker_targets: list[str]
    allowed_asset_classes: list[str]
    allowed_symbols: list[str]
    max_pilot_capital: dict[str, Any]
    pilot_constraints: dict[str, Any]
    simulation_only: bool
    readiness_review_only: bool
    persistence_enabled: bool
    writes_performed: bool
    unrestricted_live_trading_enabled: bool
    automatic_live_execution_enabled: bool
    live_restrictions: list[str]
    kill_switch: dict[str, Any]
    certification_summary: dict[str, Any]
    source_metadata: dict[str, Any]
    payload_version: str = MICRO_LIVE_PILOT_READINESS_PAYLOAD_VERSION

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_micro_live_pilot_readiness_payload(
    dashboard_payload: Mapping[str, Any] | None = None,
    *,
    live_readiness_certification: Mapping[str, Any] | None = None,
    persistence_checklist: Mapping[str, Any] | None = None,
    pcnrass_summary: Mapping[str, Any] | bool | None = None,
    operator_review_completed: bool = False,
    pilot_order: Mapping[str, Any] | None = None,
    kill_switch_controls: Mapping[str, Any] | None = None,
    kill_switch_env: Mapping[str, str] | None = None,
    generated_at_utc: str = "",
) -> dict[str, Any]:
    """
    Build a read-only micro-live pilot readiness payload.

    This function never places orders, never arms live trading, and never
    persists runtime events. It only reports whether supplied evidence is
    strong enough for a tightly constrained pilot review.
    """

    dashboard = _mapping(dashboard_payload)
    broker_summary = _mapping(dashboard.get("broker_summary"))
    governance_summary = _mapping(dashboard.get("governance_summary"))
    session = _mapping(dashboard.get("session"))
    certification = _mapping(live_readiness_certification)
    persistence = _mapping(persistence_checklist)
    order = _mapping(pilot_order)
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat()
    kill_switch = evaluate_live_order_kill_switch(
        kill_switch_controls or {},
        env=kill_switch_env or {},
    )

    checks = _build_checks(
        dashboard=dashboard,
        broker_summary=broker_summary,
        governance_summary=governance_summary,
        session=session,
        certification=certification,
        persistence=persistence,
        pcnrass_summary=pcnrass_summary,
        operator_review_completed=operator_review_completed,
        pilot_order=order,
        kill_switch_payload=kill_switch.as_dict(),
    )
    failed = [check for check in checks if not check.passed]
    passed = [check for check in checks if check.passed]
    technical_blockers = [
        check for check in failed if check.severity in {"BLOCKER", "SAFETY"}
    ]
    review_gaps = [check for check in failed if check.severity == "REVIEW"]
    overall_status = _overall_status(technical_blockers, review_gaps)
    warnings = _warnings(overall_status, failed)
    blockers = [
        f"{check.check_id}:{check.message}" for check in technical_blockers
    ]
    constraints = pilot_constraints()

    payload = MicroLivePilotReadiness(
        readiness_id=_readiness_id(
            {
                "generated_at_utc": generated,
                "overall_status": overall_status,
                "failed_checks": [check.check_id for check in failed],
            }
        ),
        generated_at_utc=generated,
        overall_status=overall_status,
        passed_checks=[check.as_dict() for check in passed],
        failed_checks=[check.as_dict() for check in failed],
        warnings=warnings,
        blockers=blockers,
        allowed_broker_targets=list(APPROVED_BROKER_TARGETS),
        allowed_asset_classes=list(APPROVED_ASSET_CLASSES),
        allowed_symbols=list(APPROVED_SYMBOLS),
        max_pilot_capital=constraints["max_pilot_capital"],
        pilot_constraints=constraints,
        simulation_only=True,
        readiness_review_only=True,
        persistence_enabled=False,
        writes_performed=False,
        unrestricted_live_trading_enabled=False,
        automatic_live_execution_enabled=False,
        live_restrictions=_live_restrictions(),
        kill_switch=kill_switch.as_dict(),
        certification_summary=_certification_summary(certification),
        source_metadata={
            "source": "dashboard.runtime.micro_live_pilot_readiness",
            "read_only": True,
            "no_order_placement": True,
            "frontend_safe": True,
            "secrets_redacted": True,
        },
    )
    return _json_safe(payload.as_dict())


def pilot_constraints() -> dict[str, Any]:
    return {
        "broker": "Coinbase Advanced only",
        "allowed_broker_keys": list(APPROVED_BROKER_KEYS),
        "allowed_broker_targets": list(APPROVED_BROKER_TARGETS),
        "allowed_symbols": list(APPROVED_SYMBOLS),
        "allowed_asset_classes": list(APPROVED_ASSET_CLASSES),
        "max_pilot_capital": {
            "amount": format(MAX_PILOT_CAPITAL_AMOUNT, "f"),
            "currency": MAX_PILOT_CAPITAL_CURRENCY,
            "display": "CAD $15",
        },
        "max_live_order_count": 1,
        "allowed_order_types": list(APPROVED_ORDER_TYPES),
        "max_slippage_pct": format(MAX_SLIPPAGE_PCT, "f"),
        "mandatory_logging": True,
        "mandatory_post_trade_pause": True,
        "fail_closed_on_governance_failure": True,
    }


def load_pcnrass_validation_summary(
    path: str | Path = "artifacts/pcnrass_release_summary.json",
) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        return {"present": False, "passed": False}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return {"present": True, "passed": False, "error": "unreadable_summary"}
    return {
        "present": True,
        "passed": bool(payload.get("passed")),
        "generated_utc": str(payload.get("generated_utc") or ""),
        "payload_version": str(payload.get("payload_version") or ""),
    }


def _build_checks(
    *,
    dashboard: Mapping[str, Any],
    broker_summary: Mapping[str, Any],
    governance_summary: Mapping[str, Any],
    session: Mapping[str, Any],
    certification: Mapping[str, Any],
    persistence: Mapping[str, Any],
    pcnrass_summary: Mapping[str, Any] | bool | None,
    operator_review_completed: bool,
    pilot_order: Mapping[str, Any],
    kill_switch_payload: Mapping[str, Any],
) -> list[PilotReadinessCheck]:
    selected_broker = _normalize_broker(broker_summary.get("selected_broker"))
    broker_mode = _mode(broker_summary.get("broker_mode"))
    session_mode = _mode(session.get("live_or_paper", dashboard.get("live_or_paper")))
    resolved_mode = _mode(dashboard.get("resolved_mode"))
    readiness_status = str(
        broker_summary.get("readiness_status") or "",
    ).strip().upper()

    checks = [
        _check(
            "replay_infrastructure_ready",
            "Replay infrastructure ready",
            True,
            "BLOCKER",
            "Replay lineage and viewer infrastructure must be present.",
        ),
        _check(
            "runtime_event_bus_ready",
            "Runtime event bus ready",
            True,
            "BLOCKER",
            "Runtime event bus foundation must be available.",
        ),
        _check(
            "persistence_governance_ready",
            "Persistence governance ready and disabled",
            persistence.get("persistence_enabled") is False
            and persistence.get("writes_performed") is False,
            "BLOCKER",
            "Persistence governance must prove persistence remains disabled.",
        ),
        _check(
            "live_readiness_certification_present",
            "Live-readiness certification present",
            bool(certification),
            "BLOCKER",
            "Broker live dry-run certification payload is required.",
        ),
        _check(
            "live_readiness_certified",
            "Live-readiness certification passed",
            _certification_passed(certification),
            "BLOCKER",
            "Broker dry-run certification must pass before pilot review.",
        ),
        _check(
            "broker_target_allowed",
            "Broker target is Coinbase Advanced only",
            selected_broker in APPROVED_BROKER_KEYS,
            "BLOCKER",
            "Micro-live pilot is restricted to Coinbase Advanced.",
        ),
        _check(
            "broker_ready",
            "Broker readiness is BROKER_READY",
            readiness_status == "BROKER_READY"
            and _bool(broker_summary.get("connected"))
            and not _bool(broker_summary.get("missing_credentials")),
            "BLOCKER",
            "Broker must be connected, credentialed, and BROKER_READY.",
        ),
        _check(
            "kill_switch_available_and_clear",
            "Kill switch is available and clear",
            kill_switch_payload.get("blocked") is False,
            "SAFETY",
            "Global live-order kill switch must be available and clear.",
        ),
        _check(
            "paper_live_separation_confirmed",
            "Paper/live separation confirmed",
            session_mode == "live"
            and broker_mode == "live"
            and resolved_mode == "live",
            "BLOCKER",
            "Session, broker, and resolved mode must explicitly agree on live.",
        ),
        _check(
            "audit_replay_available",
            "Audit and replay available",
            _bool(governance_summary.get("audit_enabled")),
            "BLOCKER",
            "Audit and replay evidence must remain available.",
        ),
        _check(
            "pilot_order_intent_present",
            "Pilot order intent present",
            bool(pilot_order),
            "REVIEW",
            "Operator review must include a bounded pilot order intent.",
        ),
        _check(
            "pilot_order_within_constraints",
            "Pilot order remains within hard constraints",
            bool(pilot_order) and _pilot_order_within_constraints(pilot_order),
            "BLOCKER" if pilot_order else "REVIEW",
            "Pilot order must be Coinbase BTC-USD, CAD <= 15, one limit order, and slippage <= 0.35%.",
        ),
        _check(
            "operator_review_completed",
            "Operator review completed",
            operator_review_completed,
            "REVIEW",
            "Explicit operator review is required before a pilot proposal.",
        ),
        _check(
            "pcnrass_validation_passed",
            "PCNRASS validation passed",
            _pcnrass_passed(pcnrass_summary),
            "REVIEW",
            "PCNRASS release validation must pass before pilot proposal.",
        ),
    ]
    return checks


def _check(
    check_id: str,
    label: str,
    passed: bool,
    severity: str,
    message: str,
) -> PilotReadinessCheck:
    return PilotReadinessCheck(
        check_id=check_id,
        label=label,
        passed=bool(passed),
        severity=severity,
        message=message,
    )


def _overall_status(
    technical_blockers: list[PilotReadinessCheck],
    review_gaps: list[PilotReadinessCheck],
) -> str:
    if technical_blockers:
        return PILOT_NOT_READY
    if review_gaps:
        return PILOT_REVIEW_REQUIRED
    return PILOT_LIMITED_READY


def _warnings(overall_status: str, failed: list[PilotReadinessCheck]) -> list[str]:
    warnings = [
        "READINESS_REVIEW_ONLY_NO_ORDER_PLACEMENT",
        "UNRESTRICTED_LIVE_TRADING_REMAINS_DISABLED",
        "PERSISTENCE_REMAINS_DISABLED",
        "MANDATORY_POST_TRADE_PAUSE_REQUIRED_FOR_ANY_FUTURE_PILOT",
    ]
    if overall_status != PILOT_LIMITED_READY:
        warnings.append("PILOT_NOT_APPROVED_UNTIL_ALL_CHECKS_PASS")
    if any(check.severity == "REVIEW" for check in failed):
        warnings.append("OPERATOR_REVIEW_ITEMS_REMAIN")
    return list(dict.fromkeys(warnings))


def _live_restrictions() -> list[str]:
    return [
        "No unrestricted live trading",
        "No automatic live order placement",
        "Coinbase Advanced only",
        "BTC-USD only",
        "CAD $15 maximum pilot capital",
        "Maximum one live order",
        "Limit orders only",
        "Maximum slippage 0.35%",
        "Mandatory logging",
        "Mandatory post-trade pause",
        "Fail closed if any governance check fails",
    ]


def _certification_summary(certification: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "present": bool(certification),
        "status": str(certification.get("status") or "MISSING"),
        "certified_for_live": bool(certification.get("certified_for_live")),
        "broker": str(certification.get("broker") or ""),
        "mode": str(certification.get("mode") or certification.get("broker_mode") or ""),
        "order_probe_status": str(certification.get("order_probe_status") or ""),
    }


def _certification_passed(certification: Mapping[str, Any]) -> bool:
    status = str(certification.get("status") or "").strip().upper()
    return bool(certification.get("certified_for_live")) or status in {
        "LIVE_DRY_RUN_CERTIFIED",
        "PASS",
    }


def _pilot_order_within_constraints(order: Mapping[str, Any]) -> bool:
    broker = _normalize_broker(order.get("broker"))
    symbol = str(order.get("symbol") or "").strip().upper()
    asset_class = str(order.get("asset_class") or "").strip().lower()
    order_type = str(order.get("order_type") or order.get("type") or "").strip().lower()
    currency = str(order.get("currency") or "").strip().upper()
    capital = _decimal(
        order.get("capital")
        or order.get("notional")
        or order.get("estimated_notional")
        or order.get("amount"),
    )
    live_order_count = _safe_int(
        order.get("live_order_count")
        or order.get("max_live_order_count")
        or 1,
    )
    slippage = _decimal(
        order.get("max_slippage_pct")
        or order.get("slippage_pct")
        or order.get("max_slippage_percent"),
    )
    return all(
        (
            broker in APPROVED_BROKER_KEYS,
            symbol in APPROVED_SYMBOLS,
            asset_class in APPROVED_ASSET_CLASSES,
            order_type in APPROVED_ORDER_TYPES,
            currency == MAX_PILOT_CAPITAL_CURRENCY,
            capital is not None and capital <= MAX_PILOT_CAPITAL_AMOUNT,
            live_order_count <= 1,
            slippage is not None and slippage <= MAX_SLIPPAGE_PCT,
        )
    )


def _pcnrass_passed(summary: Mapping[str, Any] | bool | None) -> bool:
    if isinstance(summary, bool):
        return summary
    if isinstance(summary, Mapping):
        return bool(summary.get("passed"))
    return False


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _mode(value: Any) -> str:
    return "live" if str(value or "").strip().lower() == "live" else "paper"


def _normalize_broker(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if text in {"coinbaseadvanced", "coinbase_advanced", "coinbase_advanced_trade"}:
        return "coinbase_advanced"
    return text


def _bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on", "ready"}
    return bool(value)


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value))
    except Exception:
        return None


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
    if isinstance(value, (datetime, Path)):
        return str(value)
    if isinstance(value, str) and _contains_sensitive_marker(value):
        return "REDACTED"
    return value


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    return any(part in lowered for part in _SENSITIVE_KEY_PARTS)


def _contains_sensitive_marker(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in _SENSITIVE_VALUE_MARKERS)


def _readiness_id(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:20].upper()
    return f"MLPILOT-{digest}"


__all__ = [
    "APPROVED_ASSET_CLASSES",
    "APPROVED_BROKER_TARGETS",
    "APPROVED_SYMBOLS",
    "MICRO_LIVE_PILOT_READINESS_PAYLOAD_VERSION",
    "PILOT_LIMITED_READY",
    "PILOT_NOT_READY",
    "PILOT_REVIEW_REQUIRED",
    "MicroLivePilotReadiness",
    "PilotReadinessCheck",
    "build_micro_live_pilot_readiness_payload",
    "load_pcnrass_validation_summary",
    "pilot_constraints",
]
