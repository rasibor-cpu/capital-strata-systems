"""DIP-003 WP-1 — Canonical Close Event contract.

Authoritative execution facts only. No market lookups, no invented values.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Optional

from backend.intelligence.trade_dna.hashing import compute_content_hash, verify_content_hash


CLOSE_EVENT_VERSION = "css.canonical_close_event.v1"


class CanonicalCloseEventError(ValueError):
    """Raised when a canonical close event cannot be built or validated."""

    def __init__(self, code: str, detail: Optional[str] = None) -> None:
        self.code = code
        self.detail = detail
        super().__init__(code if detail is None else f"{code}:{detail}")


def _require_positive(value: Any, *, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise CanonicalCloseEventError("invalid_numeric", field) from exc
    if number != number or number in (float("inf"), float("-inf")):
        raise CanonicalCloseEventError("invalid_numeric", field)
    if number <= 0:
        raise CanonicalCloseEventError("non_positive_value", field)
    return number


def _require_finite(value: Any, *, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise CanonicalCloseEventError("invalid_numeric", field) from exc
    if number != number or number in (float("inf"), float("-inf")):
        raise CanonicalCloseEventError("invalid_numeric", field)
    return number


def _optional_positive(value: Any, *, field: str) -> Optional[float]:
    if value is None or value == "":
        return None
    return _require_positive(value, field=field)


def _optional_non_negative(value: Any, *, field: str) -> Optional[float]:
    if value is None or value == "":
        return None
    number = _require_finite(value, field=field)
    if number < 0:
        raise CanonicalCloseEventError("negative_value", field)
    return number


def _optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    upper = text.upper()
    # Bare UNKNOWN / UNAVAILABLE are not observed market truth.
    if upper in {"UNKNOWN", "UNAVAILABLE"}:
        return None
    if upper == "OBSERVED_UNKNOWN":
        return "OBSERVED_UNKNOWN"
    return text


def deterministic_close_event_id(trade_id: str, closed_at: str) -> str:
    digest = hashlib.sha256(
        f"{CLOSE_EVENT_VERSION}|{trade_id}|{closed_at}".encode("utf-8")
    ).hexdigest()[:24]
    return f"cce-{digest}"


@dataclass(frozen=True)
class CanonicalCloseEvent:
    """Single deterministic close event for one completed trade."""

    trade_id: str
    symbol: str
    side: str
    broker_name: str
    broker_mode: str
    entry_price: float
    exit_price: float
    quantity: float
    filled_quantity: float
    opened_at: str
    closed_at: str
    realized_pnl: float
    event_version: str = CLOSE_EVENT_VERSION
    event_id: str = ""
    session_id: Optional[str] = None
    order_type: Optional[str] = None
    asset_class: Optional[str] = None
    strategy_id: Optional[str] = None
    market_regime: Optional[str] = None
    exit_reason: Optional[str] = None
    scaled_notional: Optional[float] = None
    requested_notional: Optional[float] = None
    fees: Optional[float] = None
    fill_kind: Optional[str] = None
    quantity_contract: Optional[str] = None
    notional_contract: Optional[str] = None
    gate_final: Optional[str] = None
    gate_reason: Optional[str] = None
    executed_at: Optional[str] = None
    source_event_ids: tuple[str, ...] = ()
    content_hash: str = ""
    extensions: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["source_event_ids"] = list(self.source_event_ids)
        return payload

    def with_content_hash(self) -> "CanonicalCloseEvent":
        payload = self.to_dict()
        payload["content_hash"] = ""
        digest = compute_content_hash(payload)
        return CanonicalCloseEvent(**{**payload, "source_event_ids": tuple(payload["source_event_ids"]), "content_hash": digest})


def validate_canonical_close_event(event: CanonicalCloseEvent | Mapping[str, Any]) -> CanonicalCloseEvent:
    if isinstance(event, Mapping):
        event = canonical_close_event_from_dict(event)

    if event.event_version != CLOSE_EVENT_VERSION:
        raise CanonicalCloseEventError("unsupported_close_event_version", event.event_version)
    if not event.trade_id:
        raise CanonicalCloseEventError("missing_required_field", "trade_id")
    if not event.symbol:
        raise CanonicalCloseEventError("missing_required_field", "symbol")
    if not event.side:
        raise CanonicalCloseEventError("missing_required_field", "side")
    if not event.broker_name:
        raise CanonicalCloseEventError("missing_required_field", "broker_name")
    if not event.broker_mode:
        raise CanonicalCloseEventError("missing_required_field", "broker_mode")
    if not event.opened_at or not event.closed_at:
        raise CanonicalCloseEventError("missing_required_field", "timestamps")
    if not event.event_id:
        raise CanonicalCloseEventError("missing_required_field", "event_id")

    _require_positive(event.entry_price, field="entry_price")
    _require_positive(event.exit_price, field="exit_price")
    _require_positive(event.quantity, field="quantity")
    filled = _require_finite(event.filled_quantity, field="filled_quantity")
    if filled < 0:
        raise CanonicalCloseEventError("negative_value", "filled_quantity")
    _require_finite(event.realized_pnl, field="realized_pnl")

    expected_id = deterministic_close_event_id(event.trade_id, event.closed_at)
    if event.event_id != expected_id:
        raise CanonicalCloseEventError("event_id_mismatch", event.event_id)

    if not event.content_hash or not verify_content_hash(event.to_dict()):
        raise CanonicalCloseEventError("content_hash_mismatch")

    return event


def canonical_close_event_from_dict(payload: Mapping[str, Any]) -> CanonicalCloseEvent:
    raw_ids = payload.get("source_event_ids") or ()
    if isinstance(raw_ids, list):
        source_ids = tuple(str(x) for x in raw_ids)
    else:
        source_ids = tuple(str(x) for x in raw_ids)
    return CanonicalCloseEvent(
        trade_id=str(payload.get("trade_id") or ""),
        symbol=str(payload.get("symbol") or ""),
        side=str(payload.get("side") or ""),
        broker_name=str(payload.get("broker_name") or ""),
        broker_mode=str(payload.get("broker_mode") or ""),
        entry_price=float(payload["entry_price"]) if payload.get("entry_price") is not None else 0.0,
        exit_price=float(payload["exit_price"]) if payload.get("exit_price") is not None else 0.0,
        quantity=float(payload["quantity"]) if payload.get("quantity") is not None else 0.0,
        filled_quantity=float(payload["filled_quantity"]) if payload.get("filled_quantity") is not None else 0.0,
        opened_at=str(payload.get("opened_at") or ""),
        closed_at=str(payload.get("closed_at") or ""),
        realized_pnl=float(payload["realized_pnl"]) if payload.get("realized_pnl") is not None else 0.0,
        event_version=str(payload.get("event_version") or CLOSE_EVENT_VERSION),
        event_id=str(payload.get("event_id") or ""),
        session_id=_optional_str(payload.get("session_id")),
        order_type=_optional_str(payload.get("order_type")),
        asset_class=_optional_str(payload.get("asset_class")),
        strategy_id=_optional_str(payload.get("strategy_id")),
        market_regime=_optional_str(payload.get("market_regime")),
        exit_reason=_optional_str(payload.get("exit_reason")),
        scaled_notional=_optional_positive(payload.get("scaled_notional"), field="scaled_notional")
        if payload.get("scaled_notional") is not None
        else None,
        requested_notional=_optional_positive(payload.get("requested_notional"), field="requested_notional")
        if payload.get("requested_notional") is not None
        else None,
        fees=_optional_non_negative(payload.get("fees"), field="fees"),
        fill_kind=_optional_str(payload.get("fill_kind")),
        quantity_contract=_optional_str(payload.get("quantity_contract")),
        notional_contract=_optional_str(payload.get("notional_contract")),
        gate_final=_optional_str(payload.get("gate_final")),
        gate_reason=_optional_str(payload.get("gate_reason")),
        executed_at=_optional_str(payload.get("executed_at")),
        source_event_ids=source_ids,
        content_hash=str(payload.get("content_hash") or ""),
        extensions=dict(payload.get("extensions") or {}),
    )


def build_canonical_close_event(
    *,
    trade_id: str,
    symbol: str,
    side: str,
    broker_name: str,
    broker_mode: str,
    entry_price: Any,
    exit_price: Any,
    quantity: Any,
    filled_quantity: Any,
    opened_at: str,
    closed_at: str,
    realized_pnl: Any,
    session_id: Optional[str] = None,
    order_type: Optional[str] = None,
    asset_class: Optional[str] = None,
    strategy_id: Optional[str] = None,
    market_regime: Optional[str] = None,
    exit_reason: Optional[str] = None,
    scaled_notional: Any = None,
    requested_notional: Any = None,
    fees: Any = None,
    fill_kind: Optional[str] = None,
    quantity_contract: Optional[str] = None,
    notional_contract: Optional[str] = None,
    gate_final: Optional[str] = None,
    gate_reason: Optional[str] = None,
    executed_at: Optional[str] = None,
    source_event_ids: tuple[str, ...] | list[str] = (),
    extensions: Optional[Mapping[str, Any]] = None,
) -> CanonicalCloseEvent:
    """Build and seal a canonical close event from authoritative inputs only."""
    event = CanonicalCloseEvent(
        trade_id=str(trade_id).strip(),
        symbol=str(symbol).strip(),
        side=str(side).strip(),
        broker_name=str(broker_name).strip(),
        broker_mode=str(broker_mode).strip(),
        entry_price=_require_positive(entry_price, field="entry_price"),
        exit_price=_require_positive(exit_price, field="exit_price"),
        quantity=_require_positive(quantity, field="quantity"),
        filled_quantity=_require_finite(filled_quantity, field="filled_quantity"),
        opened_at=str(opened_at).strip(),
        closed_at=str(closed_at).strip(),
        realized_pnl=_require_finite(realized_pnl, field="realized_pnl"),
        event_id=deterministic_close_event_id(str(trade_id).strip(), str(closed_at).strip()),
        session_id=_optional_str(session_id),
        order_type=_optional_str(order_type),
        asset_class=_optional_str(asset_class),
        strategy_id=_optional_str(strategy_id),
        market_regime=_optional_str(market_regime),
        exit_reason=_optional_str(exit_reason),
        scaled_notional=_optional_positive(scaled_notional, field="scaled_notional")
        if scaled_notional is not None
        else None,
        requested_notional=_optional_positive(requested_notional, field="requested_notional")
        if requested_notional is not None
        else None,
        fees=_optional_non_negative(fees, field="fees"),
        fill_kind=_optional_str(fill_kind),
        quantity_contract=_optional_str(quantity_contract),
        notional_contract=_optional_str(notional_contract),
        gate_final=_optional_str(gate_final),
        gate_reason=_optional_str(gate_reason),
        executed_at=_optional_str(executed_at),
        source_event_ids=tuple(str(x) for x in source_event_ids),
        extensions=dict(extensions or {}),
    ).with_content_hash()
    return validate_canonical_close_event(event)


def build_canonical_close_event_from_trade_record(
    trade_record: Mapping[str, Any],
    *,
    exit_price: Any,
    realized_pnl: Any,
    closed_at: str,
) -> CanonicalCloseEvent:
    """Project an operational trades row + close contract into a close event.

    Reads sealed open economics from raw_payload_json when present.
    Does not invent missing regime/strategy/fees.
    """
    raw_payload: dict[str, Any] = {}
    raw_payload_json = trade_record.get("raw_payload_json")
    if isinstance(raw_payload_json, str) and raw_payload_json:
        try:
            parsed = json.loads(raw_payload_json)
            if isinstance(parsed, dict):
                raw_payload = parsed
        except Exception:
            raw_payload = {}

    economics = raw_payload.get("execution_economics")
    if not isinstance(economics, Mapping):
        economics = {}
    gate = raw_payload.get("execution_gate_summary")
    if not isinstance(gate, Mapping):
        gate = {}

    trade_id = str(trade_record.get("trade_id") or "").strip()
    opened_at = str(trade_record.get("opened_at") or "").strip()
    if not opened_at:
        raise CanonicalCloseEventError("missing_required_field", "opened_at")

    source_ids = [f"trade:{trade_id}", f"close:{closed_at}"]
    if economics.get("schema_version"):
        source_ids.append(f"economics:{economics.get('schema_version')}")

    return build_canonical_close_event(
        trade_id=trade_id,
        symbol=str(trade_record.get("symbol") or ""),
        side=str(trade_record.get("direction") or trade_record.get("side") or ""),
        broker_name=str(trade_record.get("broker_name") or ""),
        broker_mode=str(trade_record.get("broker_mode") or ""),
        entry_price=trade_record.get("entry_price"),
        exit_price=exit_price,
        quantity=trade_record.get("quantity"),
        filled_quantity=trade_record.get("filled_quantity", trade_record.get("quantity")),
        opened_at=opened_at,
        closed_at=closed_at,
        realized_pnl=realized_pnl,
        session_id=_optional_str(trade_record.get("session_id")),
        order_type=_optional_str(trade_record.get("order_type")),
        asset_class=_optional_str(raw_payload.get("asset_class") or raw_payload.get("asset")),
        strategy_id=_optional_str(raw_payload.get("strategy_id") or raw_payload.get("strategy")),
        market_regime=_optional_str(raw_payload.get("market_regime") or raw_payload.get("regime")),
        exit_reason=_optional_str(raw_payload.get("exit_reason")),
        scaled_notional=economics.get("scaled_notional"),
        requested_notional=economics.get("requested_notional"),
        fees=economics.get("fees"),
        fill_kind=_optional_str(economics.get("fill_kind")),
        quantity_contract=_optional_str(economics.get("quantity_contract")),
        notional_contract=_optional_str(economics.get("notional_contract")),
        gate_final=_optional_str(gate.get("final") or economics.get("gate_final")),
        gate_reason=_optional_str(gate.get("reason") or economics.get("gate_reason")),
        executed_at=_optional_str(economics.get("executed_at")),
        source_event_ids=tuple(source_ids),
    )


def serialize_canonical_close_event(event: CanonicalCloseEvent) -> str:
    validated = validate_canonical_close_event(event)
    return json.dumps(validated.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def deserialize_canonical_close_event(text: str | Mapping[str, Any]) -> CanonicalCloseEvent:
    payload = json.loads(text) if isinstance(text, str) else dict(text)
    return validate_canonical_close_event(payload)
