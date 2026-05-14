from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from dashboard.runtime.micro_live_pilot_readiness import (
    APPROVED_ASSET_CLASSES,
    APPROVED_BROKER_KEYS,
    APPROVED_BROKER_TARGETS,
    APPROVED_ORDER_TYPES,
    APPROVED_SYMBOLS,
    MAX_PILOT_CAPITAL_AMOUNT,
    MAX_PILOT_CAPITAL_CURRENCY,
    MAX_SLIPPAGE_PCT,
)


MICRO_LIVE_PILOT_ORDER_INTENT_PAYLOAD_VERSION = (
    "css.micro_live_pilot_order_intent.v1"
)

CANONICAL_BROKER = "Coinbase Advanced"
CANONICAL_BROKER_KEY = "coinbase"
CANONICAL_SYMBOL = "BTC-USD"
CANONICAL_ASSET_CLASS = "crypto"
CANONICAL_ORDER_TYPE = "limit"

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
class MicroLivePilotOrderIntent:
    intent_id: str
    generated_at_utc: str
    broker: str
    broker_key: str
    symbol: str
    asset_class: str
    order_type: str
    side: str
    side_review_only: bool
    max_pilot_capital_cad: str
    max_slippage_pct: str
    max_live_orders: int
    execution_allowed: bool
    requires_operator_confirmation: bool
    requires_broker_dry_run_certification: bool
    requires_kill_switch_verification: bool
    requires_pcnrass_release_check: bool
    requires_post_trade_pause: bool
    requires_mandatory_logging: bool
    blockers: list[str]
    warnings: list[str]
    required_approvals: list[str]
    requested_order: dict[str, Any]
    audit_payload: dict[str, Any]
    source_metadata: dict[str, Any]
    payload_version: str = MICRO_LIVE_PILOT_ORDER_INTENT_PAYLOAD_VERSION

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_micro_live_pilot_order_intent_payload(
    requested_order: Mapping[str, Any] | None = None,
    *,
    side: str = "REVIEW_ONLY",
    generated_at_utc: str = "",
) -> dict[str, Any]:
    """
    Build a non-executing pilot order-intent evidence package.

    The returned package cannot be used to place an order. It is deliberately
    review-only and keeps execution_allowed false regardless of inputs.
    """

    requested = dict(requested_order or {})
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat()
    sanitized_requested = _json_safe(requested)
    blockers = _blockers(requested)
    warnings = _warnings(requested)
    intent_id = _intent_id(
        {
            "generated_at_utc": generated,
            "requested_order": sanitized_requested,
            "side": side,
        }
    )
    audit_payload = _audit_payload(
        intent_id=intent_id,
        generated_at_utc=generated,
        requested_order=sanitized_requested,
        blockers=blockers,
    )

    intent = MicroLivePilotOrderIntent(
        intent_id=intent_id,
        generated_at_utc=generated,
        broker=CANONICAL_BROKER,
        broker_key=CANONICAL_BROKER_KEY,
        symbol=CANONICAL_SYMBOL,
        asset_class=CANONICAL_ASSET_CLASS,
        order_type=CANONICAL_ORDER_TYPE,
        side=_side(side),
        side_review_only=True,
        max_pilot_capital_cad=format(MAX_PILOT_CAPITAL_AMOUNT, "f"),
        max_slippage_pct=format(MAX_SLIPPAGE_PCT, "f"),
        max_live_orders=1,
        execution_allowed=False,
        requires_operator_confirmation=True,
        requires_broker_dry_run_certification=True,
        requires_kill_switch_verification=True,
        requires_pcnrass_release_check=True,
        requires_post_trade_pause=True,
        requires_mandatory_logging=True,
        blockers=blockers,
        warnings=warnings,
        required_approvals=_required_approvals(),
        requested_order=sanitized_requested,
        audit_payload=audit_payload,
        source_metadata={
            "source": "dashboard.runtime.micro_live_pilot_order_intent",
            "read_only": True,
            "review_only": True,
            "no_broker_calls": True,
            "no_order_placement": True,
            "no_account_mutation": True,
            "frontend_safe": True,
            "secrets_redacted": True,
        },
    )
    return _json_safe(intent.as_dict())


def _blockers(requested: Mapping[str, Any]) -> list[str]:
    blockers = [
        "OPERATOR_CONFIRMATION_REQUIRED",
        "BROKER_DRY_RUN_CERTIFICATION_REQUIRED",
        "KILL_SWITCH_VERIFICATION_REQUIRED",
        "PCNRASS_RELEASE_CHECK_REQUIRED",
        "LIVE_ORDER_EXECUTION_DISABLED_FROM_INTENT_PACKAGE",
    ]
    if not requested:
        return blockers

    broker = _normalize_broker(requested.get("broker"))
    symbol = str(requested.get("symbol") or "").strip().upper()
    asset_class = str(requested.get("asset_class") or "").strip().lower()
    order_type = str(
        requested.get("order_type") or requested.get("type") or "",
    ).strip().lower()
    currency = str(requested.get("currency") or "").strip().upper()
    capital = _decimal(
        requested.get("capital")
        or requested.get("notional")
        or requested.get("estimated_notional")
        or requested.get("amount"),
    )
    max_live_orders = _safe_int(
        requested.get("max_live_orders")
        or requested.get("live_order_count")
        or requested.get("max_live_order_count")
        or 1,
    )
    slippage = _decimal(
        requested.get("max_slippage_pct")
        or requested.get("slippage_pct")
        or requested.get("max_slippage_percent"),
    )

    if broker and broker not in APPROVED_BROKER_KEYS:
        blockers.append("REQUESTED_BROKER_OUTSIDE_PILOT_SCOPE")
    if symbol and symbol not in APPROVED_SYMBOLS:
        blockers.append("REQUESTED_SYMBOL_OUTSIDE_PILOT_SCOPE")
    if asset_class and asset_class not in APPROVED_ASSET_CLASSES:
        blockers.append("REQUESTED_ASSET_CLASS_OUTSIDE_PILOT_SCOPE")
    if order_type and order_type not in APPROVED_ORDER_TYPES:
        blockers.append("REQUESTED_ORDER_TYPE_NOT_LIMIT")
    if currency and currency != MAX_PILOT_CAPITAL_CURRENCY:
        blockers.append("REQUESTED_CAPITAL_CURRENCY_NOT_CAD")
    if capital is not None and capital > MAX_PILOT_CAPITAL_AMOUNT:
        blockers.append("REQUESTED_CAPITAL_EXCEEDS_CAD_15")
    if max_live_orders > 1:
        blockers.append("REQUESTED_LIVE_ORDER_COUNT_EXCEEDS_ONE")
    if slippage is not None and slippage > MAX_SLIPPAGE_PCT:
        blockers.append("REQUESTED_SLIPPAGE_EXCEEDS_0_35_PCT")
    return list(dict.fromkeys(blockers))


def _warnings(requested: Mapping[str, Any]) -> list[str]:
    warnings = [
        "NO_ORDER_WILL_BE_PLACED_FROM_THIS_PACKAGE",
        "SIDE_IS_REVIEW_ONLY_AND_NOT_EXECUTABLE",
        "UNRESTRICTED_LIVE_TRADING_REMAINS_DISABLED",
        "PERSISTENCE_REMAINS_DISABLED",
        "POST_TRADE_PAUSE_REQUIRED_BEFORE_ANY_FUTURE_PILOT",
    ]
    if not requested:
        warnings.append("OPERATOR_MUST_ATTACH_FINAL_REVIEWED_ORDER_INTENT")
    return warnings


def _required_approvals() -> list[str]:
    return [
        "explicit operator confirmation",
        "Coinbase non-executing dry-run certification",
        "kill-switch verification",
        "PCNRASS release check",
        "broker readiness evidence",
        "post-trade pause acceptance",
    ]


def _audit_payload(
    *,
    intent_id: str,
    generated_at_utc: str,
    requested_order: Mapping[str, Any],
    blockers: list[str],
) -> dict[str, Any]:
    return _json_safe(
        {
            "event_type": "micro_live_pilot_order_intent_created",
            "intent_id": intent_id,
            "generated_at_utc": generated_at_utc,
            "broker": CANONICAL_BROKER,
            "symbol": CANONICAL_SYMBOL,
            "asset_class": CANONICAL_ASSET_CLASS,
            "order_type": CANONICAL_ORDER_TYPE,
            "execution_allowed": False,
            "review_only": True,
            "requested_order": requested_order,
            "blockers": blockers,
        }
    )


def _side(value: Any) -> str:
    text = str(value or "REVIEW_ONLY").strip().upper()
    if text in {"BUY", "SELL", "HOLD", "REVIEW_ONLY"}:
        return text
    return "REVIEW_ONLY"


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


def _intent_id(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:20].upper()
    return f"MLINTENT-{digest}"


__all__ = [
    "CANONICAL_BROKER",
    "CANONICAL_SYMBOL",
    "MICRO_LIVE_PILOT_ORDER_INTENT_PAYLOAD_VERSION",
    "MicroLivePilotOrderIntent",
    "build_micro_live_pilot_order_intent_payload",
]
