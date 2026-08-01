"""MW-004 — paper execution economics for ledger fidelity.

ExecutionGate is notional-based and does not emit an approved quantity.
This module records requested quantity distinctly from scaled notional and
requires a validated positive execution/entry price for filled opens.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Optional

from engine.risk.canonical_volatility_price import coerce_finite_positive_price


SCHEMA_VERSION = "css.paper.execution_economics.v1"
QUANTITY_CONTRACT = "requested_quantity_authoritative"
NOTIONAL_CONTRACT = "scaled_notional_authoritative_for_risk"
FILL_KIND_SYNTHETIC_FULL = "paper_synthetic_full_request_qty"
FILL_KIND_NONE = "none"


class PaperExecutionEconomicsError(ValueError):
    """Raised when paper execution economics cannot be formed safely."""


def _as_decimal(value: Any, *, field: str) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PaperExecutionEconomicsError(f"invalid_{field}") from exc
    if not number.is_finite():
        raise PaperExecutionEconomicsError(f"invalid_{field}")
    return number


def require_positive_execution_price(value: Any) -> Decimal:
    parsed = coerce_finite_positive_price(value)
    if parsed is None:
        raise PaperExecutionEconomicsError("execution_price_invalid")
    return Decimal(str(parsed))


def build_paper_execution_economics(
    *,
    ticket: Mapping[str, Any],
    gate_decision: Mapping[str, Any],
    canonical_price: Any,
    price_source: Optional[str] = None,
    executed_at: Optional[str] = None,
) -> dict[str, Any]:
    """
    Build an explicit paper fill/economics structure after gate ALLOW.

    Quantity policy:
    - requested_quantity remains authoritative for units
    - scaled_notional remains authoritative for risk sizing
    - no silent qty = scaled_notional / price inference
    """
    debug = gate_decision.get("debug") if isinstance(gate_decision.get("debug"), Mapping) else {}
    decision = gate_decision.get("decision") if isinstance(gate_decision.get("decision"), Mapping) else {}
    final = str(decision.get("final") or "").upper()

    entry_price = require_positive_execution_price(
        canonical_price if canonical_price is not None else debug.get("canonical_price")
    )
    requested_quantity = _as_decimal(ticket.get("qty"), field="requested_quantity")
    if requested_quantity <= 0:
        raise PaperExecutionEconomicsError("requested_quantity_invalid")

    requested_notional = _as_decimal(ticket.get("amount"), field="requested_notional")
    if requested_notional <= 0:
        raise PaperExecutionEconomicsError("requested_notional_invalid")

    scaled_raw = debug.get("scaled_notional", debug.get("vol_scaled_notional", requested_notional))
    scaled_notional = _as_decimal(scaled_raw, field="scaled_notional")
    if scaled_notional <= 0:
        raise PaperExecutionEconomicsError("scaled_notional_invalid")

    ts = executed_at or datetime.now(timezone.utc).isoformat()
    price_src = str(price_source or debug.get("canonical_price_source") or "canonical_price")

    if final != "ALLOW":
        # Explicit non-filled record — never invent a completed fill.
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "pending",
            "fill_kind": FILL_KIND_NONE,
            "requested_quantity": str(requested_quantity),
            "filled_quantity": "0",
            "requested_notional": str(requested_notional),
            "scaled_notional": str(scaled_notional),
            "entry_price": str(entry_price),
            "price_source": price_src,
            "quantity_contract": QUANTITY_CONTRACT,
            "notional_contract": NOTIONAL_CONTRACT,
            "executed_at": ts,
            "gate_final": final or "BLOCK",
            "gate_reason": str(gate_decision.get("reason") or "not_allowed"),
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "open",
        "fill_kind": FILL_KIND_SYNTHETIC_FULL,
        "requested_quantity": str(requested_quantity),
        "filled_quantity": str(requested_quantity),
        "requested_notional": str(requested_notional),
        "scaled_notional": str(scaled_notional),
        "entry_price": str(entry_price),
        "price_source": price_src,
        "quantity_contract": QUANTITY_CONTRACT,
        "notional_contract": NOTIONAL_CONTRACT,
        "executed_at": ts,
        "gate_final": "ALLOW",
        "gate_reason": str(gate_decision.get("reason") or "approved"),
    }


def merge_ticket_payload_with_economics(
    ticket: Mapping[str, Any],
    economics: Mapping[str, Any],
    *,
    gate_decision: Mapping[str, Any] | None = None,
) -> str:
    payload = dict(ticket)
    payload["execution_economics"] = dict(economics)
    if gate_decision is not None:
        debug = gate_decision.get("debug") if isinstance(gate_decision.get("debug"), Mapping) else {}
        payload["execution_gate_summary"] = {
            "final": (gate_decision.get("decision") or {}).get("final")
            if isinstance(gate_decision.get("decision"), Mapping)
            else None,
            "reason": gate_decision.get("reason"),
            "scaled_notional": debug.get("scaled_notional"),
            "base_notional": debug.get("base_notional"),
            "canonical_price": debug.get("canonical_price"),
            "canonical_price_source": debug.get("canonical_price_source"),
        }
    return json.dumps(payload, sort_keys=True, default=str)


def amount_traded(*, entry_price: Any, quantity: Any) -> Decimal:
    price = require_positive_execution_price(entry_price)
    qty = _as_decimal(quantity, field="quantity")
    if qty < 0:
        raise PaperExecutionEconomicsError("quantity_invalid")
    return (price * qty).quantize(Decimal("0.00000001"))


__all__ = [
    "FILL_KIND_NONE",
    "FILL_KIND_SYNTHETIC_FULL",
    "NOTIONAL_CONTRACT",
    "PaperExecutionEconomicsError",
    "QUANTITY_CONTRACT",
    "SCHEMA_VERSION",
    "amount_traded",
    "build_paper_execution_economics",
    "merge_ticket_payload_with_economics",
    "require_positive_execution_price",
]
