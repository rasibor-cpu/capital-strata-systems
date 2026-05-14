from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from dashboard.runtime.micro_live_pilot_order_intent import (
    CANONICAL_BROKER,
    CANONICAL_SYMBOL,
    build_micro_live_pilot_order_intent_payload,
)
from dashboard.runtime.micro_live_pilot_readiness import (
    APPROVED_ASSET_CLASSES,
    APPROVED_BROKER_KEYS,
    APPROVED_ORDER_TYPES,
    APPROVED_SYMBOLS,
    MAX_PILOT_CAPITAL_AMOUNT,
    MAX_SLIPPAGE_PCT,
)


COINBASE_MICRO_LIVE_DRY_RUN_PROBE_PAYLOAD_VERSION = (
    "css.coinbase_micro_live_dry_run_probe.v1"
)

PROBE_PASS = "PASS"
PROBE_FAIL = "FAIL"
PROBE_REVIEW_REQUIRED = "REVIEW_REQUIRED"
PROBE_MODE = "non_executing"

_REQUIRED_APPROVAL_PARTS = (
    "operator confirmation",
    "dry-run certification",
    "kill-switch verification",
    "PCNRASS release check",
)
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
_PUBLIC_SAFETY_KEYS = {
    "credential_secret_exposed",
}


@dataclass(frozen=True)
class CoinbaseDryRunProbeCheck:
    check_id: str
    label: str
    passed: bool
    severity: str
    message: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CoinbaseMicroLiveDryRunProbe:
    probe_id: str
    generated_at_utc: str
    broker: str
    symbol: str
    order_type: str
    max_pilot_capital_cad: str
    max_slippage_pct: str
    max_live_orders: int
    order_submit_allowed: bool
    broker_mutation_allowed: bool
    credential_secret_exposed: bool
    probe_mode: str
    validation_status: str
    passed_checks: list[dict[str, Any]]
    failed_checks: list[dict[str, Any]]
    blockers: list[str]
    warnings: list[str]
    audit_payload: dict[str, Any]
    order_intent_summary: dict[str, Any]
    source_metadata: dict[str, Any]
    payload_version: str = COINBASE_MICRO_LIVE_DRY_RUN_PROBE_PAYLOAD_VERSION

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_coinbase_micro_live_dry_run_probe_payload(
    order_intent: Mapping[str, Any] | None = None,
    *,
    generated_at_utc: str = "",
) -> dict[str, Any]:
    """
    Validate the Phase 24 intent as non-executing Coinbase dry-run evidence.

    This function does not call Coinbase, does not submit an order, and does
    not mutate any broker/account state.
    """

    intent = _mapping(order_intent) or build_micro_live_pilot_order_intent_payload()
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat()
    checks = _probe_checks(intent)
    failed = [check for check in checks if not check.passed]
    passed = [check for check in checks if check.passed]
    blockers = [
        f"{check.check_id}:{check.message}"
        for check in failed
        if check.severity == "BLOCKER"
    ]
    warnings = _warnings(failed)
    status = _validation_status(failed)
    probe_id = _probe_id(
        {
            "generated_at_utc": generated,
            "intent_id": intent.get("intent_id"),
            "status": status,
            "failed_checks": [check.check_id for check in failed],
        }
    )
    credential_secret_exposed = _contains_secret_values(intent)

    probe = CoinbaseMicroLiveDryRunProbe(
        probe_id=probe_id,
        generated_at_utc=generated,
        broker=CANONICAL_BROKER,
        symbol=CANONICAL_SYMBOL,
        order_type="limit",
        max_pilot_capital_cad=format(MAX_PILOT_CAPITAL_AMOUNT, "f"),
        max_slippage_pct=format(MAX_SLIPPAGE_PCT, "f"),
        max_live_orders=1,
        order_submit_allowed=False,
        broker_mutation_allowed=False,
        credential_secret_exposed=credential_secret_exposed,
        probe_mode=PROBE_MODE,
        validation_status=status,
        passed_checks=[check.as_dict() for check in passed],
        failed_checks=[check.as_dict() for check in failed],
        blockers=blockers,
        warnings=warnings,
        audit_payload=_audit_payload(
            probe_id=probe_id,
            generated_at_utc=generated,
            validation_status=status,
            blockers=blockers,
            order_intent=intent,
        ),
        order_intent_summary=_order_intent_summary(intent),
        source_metadata={
            "source": "dashboard.runtime.coinbase_micro_live_dry_run_probe",
            "read_only": True,
            "evidence_only": True,
            "no_broker_calls": True,
            "no_order_submit_endpoint": True,
            "no_order_placement": True,
            "no_broker_mutation": True,
            "frontend_safe": True,
            "secrets_redacted": True,
        },
    )
    return _json_safe(probe.as_dict())


def _probe_checks(intent: Mapping[str, Any]) -> list[CoinbaseDryRunProbeCheck]:
    approvals = [str(item) for item in intent.get("required_approvals") or []]
    return [
        _check(
            "broker_is_coinbase_advanced",
            "Broker is Coinbase Advanced",
            _normalize_broker(intent.get("broker_key") or intent.get("broker"))
            in APPROVED_BROKER_KEYS,
            "BLOCKER",
            "Probe is restricted to Coinbase Advanced.",
        ),
        _check(
            "symbol_is_btc_usd",
            "Symbol is BTC-USD",
            str(intent.get("symbol") or "").strip().upper() in APPROVED_SYMBOLS,
            "BLOCKER",
            "Probe is restricted to BTC-USD.",
        ),
        _check(
            "order_type_is_limit",
            "Order type is limit",
            str(intent.get("order_type") or "").strip().lower()
            in APPROVED_ORDER_TYPES,
            "BLOCKER",
            "Probe is restricted to limit-order intent.",
        ),
        _check(
            "execution_allowed_false",
            "Intent execution_allowed is false",
            intent.get("execution_allowed") is False,
            "BLOCKER",
            "Order intent must not allow execution.",
        ),
        _check(
            "capital_cap_cad_15",
            "Max capital is CAD 15 or less",
            _decimal(intent.get("max_pilot_capital_cad"))
            <= MAX_PILOT_CAPITAL_AMOUNT,
            "BLOCKER",
            "Pilot capital cap must not exceed CAD 15.",
        ),
        _check(
            "slippage_cap_0_35",
            "Max slippage is 0.35% or less",
            _decimal(intent.get("max_slippage_pct")) <= MAX_SLIPPAGE_PCT,
            "BLOCKER",
            "Pilot slippage cap must not exceed 0.35%.",
        ),
        _check(
            "max_live_orders_one",
            "Max live orders is one or less",
            _safe_int(intent.get("max_live_orders")) <= 1,
            "BLOCKER",
            "Pilot cannot exceed one live order.",
        ),
        _check(
            "required_approvals_present",
            "Required approvals are present",
            _approvals_present(approvals),
            "REVIEW",
            "Intent must list operator, dry-run, kill-switch, and PCNRASS approvals.",
        ),
        _check(
            "kill_switch_verification_required",
            "Kill-switch verification is required",
            intent.get("requires_kill_switch_verification") is True,
            "REVIEW",
            "Intent must require kill-switch verification.",
        ),
        _check(
            "pcnrass_release_check_required",
            "PCNRASS release check is required",
            intent.get("requires_pcnrass_release_check") is True,
            "REVIEW",
            "Intent must require PCNRASS release check.",
        ),
        _check(
            "no_order_submit_path_invoked",
            "No order-submit path invoked",
            intent.get("source_metadata", {}).get("no_order_placement") is True,
            "BLOCKER",
            "Intent source must prove no order-placement path was invoked.",
        ),
        _check(
            "no_broker_mutation_invoked",
            "No broker mutation invoked",
            intent.get("source_metadata", {}).get("no_account_mutation") is True,
            "BLOCKER",
            "Intent source must prove no broker/account mutation was invoked.",
        ),
        _check(
            "credential_secret_not_exposed",
            "No credential secret exposed",
            not _contains_secret_values(intent),
            "BLOCKER",
            "Probe payload must not expose credential-shaped values.",
        ),
    ]


def _check(
    check_id: str,
    label: str,
    passed: bool,
    severity: str,
    message: str,
) -> CoinbaseDryRunProbeCheck:
    return CoinbaseDryRunProbeCheck(
        check_id=check_id,
        label=label,
        passed=bool(passed),
        severity=severity,
        message=message,
    )


def _warnings(failed: list[CoinbaseDryRunProbeCheck]) -> list[str]:
    warnings = [
        "NO_ORDER_WAS_SUBMITTED",
        "NO_BROKER_MUTATION_PERFORMED",
        "PROBE_EVIDENCE_ONLY",
        "UNRESTRICTED_LIVE_TRADING_REMAINS_DISABLED",
        "OPERATOR_APPROVAL_STILL_REQUIRED_BEFORE_ANY_PILOT",
    ]
    if any(check.severity == "REVIEW" for check in failed):
        warnings.append("REVIEW_ITEMS_REMAIN")
    if any(check.severity == "BLOCKER" for check in failed):
        warnings.append("PROBE_BLOCKERS_REMAIN")
    return list(dict.fromkeys(warnings))


def _validation_status(failed: list[CoinbaseDryRunProbeCheck]) -> str:
    if any(check.severity == "BLOCKER" for check in failed):
        return PROBE_FAIL
    if failed:
        return PROBE_REVIEW_REQUIRED
    return PROBE_PASS


def _approvals_present(approvals: list[str]) -> bool:
    normalized = " | ".join(approvals).lower()
    return all(part.lower() in normalized for part in _REQUIRED_APPROVAL_PARTS)


def _order_intent_summary(intent: Mapping[str, Any]) -> dict[str, Any]:
    return _json_safe(
        {
            "intent_id": intent.get("intent_id", ""),
            "broker": intent.get("broker", ""),
            "broker_key": intent.get("broker_key", ""),
            "symbol": intent.get("symbol", ""),
            "order_type": intent.get("order_type", ""),
            "side": intent.get("side", ""),
            "execution_allowed": bool(intent.get("execution_allowed")),
            "max_pilot_capital_cad": intent.get("max_pilot_capital_cad", ""),
            "max_slippage_pct": intent.get("max_slippage_pct", ""),
            "max_live_orders": _safe_int(intent.get("max_live_orders")),
        }
    )


def _audit_payload(
    *,
    probe_id: str,
    generated_at_utc: str,
    validation_status: str,
    blockers: list[str],
    order_intent: Mapping[str, Any],
) -> dict[str, Any]:
    return _json_safe(
        {
            "event_type": "coinbase_micro_live_dry_run_probe_created",
            "probe_id": probe_id,
            "generated_at_utc": generated_at_utc,
            "broker": CANONICAL_BROKER,
            "symbol": CANONICAL_SYMBOL,
            "order_type": "limit",
            "probe_mode": PROBE_MODE,
            "validation_status": validation_status,
            "order_submit_allowed": False,
            "broker_mutation_allowed": False,
            "order_submitted": False,
            "broker_mutated": False,
            "blockers": blockers,
            "order_intent_summary": _order_intent_summary(order_intent),
        }
    )


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _normalize_broker(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if text in {"coinbaseadvanced", "coinbase_advanced", "coinbase_advanced_trade"}:
        return "coinbase_advanced"
    return text


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
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
    if isinstance(value, (datetime, Path)):
        return str(value)
    if isinstance(value, str) and _contains_sensitive_marker(value):
        return "REDACTED"
    return value


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    if lowered in _PUBLIC_SAFETY_KEYS:
        return False
    return any(part in lowered for part in _SENSITIVE_KEY_PARTS)


def _contains_sensitive_marker(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in _SENSITIVE_VALUE_MARKERS)


def _contains_secret_values(value: Any) -> bool:
    serialized = json.dumps(value, sort_keys=True, default=str).lower()
    return any(marker in serialized for marker in _SENSITIVE_VALUE_MARKERS)


def _probe_id(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:20].upper()
    return f"CBPROBE-{digest}"


__all__ = [
    "COINBASE_MICRO_LIVE_DRY_RUN_PROBE_PAYLOAD_VERSION",
    "PROBE_FAIL",
    "PROBE_MODE",
    "PROBE_PASS",
    "PROBE_REVIEW_REQUIRED",
    "CoinbaseDryRunProbeCheck",
    "CoinbaseMicroLiveDryRunProbe",
    "build_coinbase_micro_live_dry_run_probe_payload",
]
