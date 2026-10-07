"""Governed, configurable pilot exposure preflight. No execution/arming side effects.

This component is a *necessary* prospective order gate, never sufficient
authorization. Callers must additionally pass the existing R7, AntiBleed,
broker reconciliation, RBAC and kill-switch controls. No trading path is
wired to this module until integration tests certify all entry points.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping


class PilotConfigurationError(ValueError):
    """An invalid or incomplete pilot approval must fail closed."""


def _money(raw: Any, name: str) -> Decimal:
    if isinstance(raw, bool):
        raise PilotConfigurationError(f"{name}: boolean not permitted")
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise PilotConfigurationError(f"{name}: invalid decimal") from exc
    if not value.is_finite() or value < 0:
        raise PilotConfigurationError(f"{name}: must be finite and nonnegative")
    return value


@dataclass(frozen=True)
class GovernedPilotProfile:
    """The monetary ceiling is an operator-approved *value*, not a code constant."""

    approval_id: str
    broker_id: str
    account_id: str
    instrument: str
    currency: str
    max_aggregate_exposure: Decimal
    expires_at: datetime
    session_id: str
    max_order_count: int = 1
    allow_margin: bool = False

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "GovernedPilotProfile":
        if not isinstance(values, Mapping):
            raise PilotConfigurationError("approved profile required")
        required = ("approval_id", "broker_id", "account_id", "instrument",
                    "currency", "expires_at", "session_id", "max_aggregate_exposure")
        if any(not str(values.get(key) or "").strip() for key in required):
            raise PilotConfigurationError("missing required approval fields")
        try:
            expiry = datetime.fromisoformat(str(values["expires_at"]).replace("Z", "+00:00"))
        except (ValueError, TypeError) as exc:
            raise PilotConfigurationError("invalid expiry") from exc
        if expiry.tzinfo is None:
            raise PilotConfigurationError("expiry timezone required")
        if not isinstance(values.get("max_order_count", 1), int) or isinstance(values.get("max_order_count", 1), bool):
            raise PilotConfigurationError("max_order_count must be integer")
        if values.get("max_order_count", 1) != 1:
            raise PilotConfigurationError("pilot is restricted to one order")
        if values.get("allow_margin", False) is not False:
            raise PilotConfigurationError("margin is prohibited")
        currency = str(values["currency"]).strip().upper()
        if currency != "CAD":
            raise PilotConfigurationError("CAD-only pilot until currency conversion certified")
        ceiling = _money(values["max_aggregate_exposure"], "max_aggregate_exposure")
        if ceiling <= 0:
            raise PilotConfigurationError("pilot exposure ceiling must be positive")
        return cls(
            approval_id=str(values["approval_id"]).strip(),
            broker_id=str(values["broker_id"]).strip(),
            account_id=str(values["account_id"]).strip(),
            instrument=str(values["instrument"]).strip().upper(),
            currency=currency,
            max_aggregate_exposure=ceiling,
            expires_at=expiry,
            session_id=str(values["session_id"]).strip(),
        )


@dataclass(frozen=True)
class PilotPreflightDecision:
    approved: bool
    reason: str
    projected_exposure_cad: Decimal


def evaluate_pilot_preflight(
    profile: GovernedPilotProfile | None,
    *,
    broker_id: str,
    account_id: str,
    instrument: str,
    session_id: str,
    current_exposure_cad: Any,
    pending_orders_cad: Any,
    proposed_order_cad: Any,
    estimated_fees_cad: Any,
    reconciled: bool,
    reconciled_at: datetime | None,
    expected_net_edge_bps: Any,
    required_net_edge_bps: Any,
    orders_already_submitted: int,
    margin_requested: bool,
    now: datetime | None = None,
) -> PilotPreflightDecision:
    """Fail closed; include existing positions, orders and fees in the budget.

    Never places orders, writes authorization, or overrides AntiBleed.
    Uncertified FX conversions must be rejected upstream rather than inferred.
    """
    rejected = PilotPreflightDecision(False, "PILOT_BLOCKED", Decimal("0"))
    if not isinstance(profile, GovernedPilotProfile):
        return rejected
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now >= profile.expires_at:
        return PilotPreflightDecision(False, "PILOT_EXPIRED_OR_CLOCK_INVALID", Decimal("0"))
    if (broker_id != profile.broker_id or account_id != profile.account_id
            or instrument.strip().upper() != profile.instrument or session_id != profile.session_id):
        return PilotPreflightDecision(False, "PILOT_SCOPE_MISMATCH", Decimal("0"))
    if margin_requested or not reconciled or reconciled_at is None or reconciled_at.tzinfo is None:
        return PilotPreflightDecision(False, "MARGIN_OR_RECONCILIATION_BLOCK", Decimal("0"))
    age = (now - reconciled_at).total_seconds()
    if age < 0 or age > 30:
        return PilotPreflightDecision(False, "RECONCILIATION_STALE", Decimal("0"))
    if isinstance(orders_already_submitted, bool) or not isinstance(orders_already_submitted, int) or orders_already_submitted != 0:
        return PilotPreflightDecision(False, "PILOT_ORDER_ALREADY_USED", Decimal("0"))
    try:
        current = _money(current_exposure_cad, "current_exposure")
        pending = _money(pending_orders_cad, "pending_orders")
        proposed = _money(proposed_order_cad, "proposed_order")
        fees = _money(estimated_fees_cad, "estimated_fees")
        edge = _money(expected_net_edge_bps, "expected_net_edge")
        minimum = _money(required_net_edge_bps, "required_net_edge")
    except PilotConfigurationError:
        return PilotPreflightDecision(False, "INVALID_FINANCIAL_EVIDENCE", Decimal("0"))
    projected = current + pending + proposed + fees
    if proposed <= 0 or projected > profile.max_aggregate_exposure:
        return PilotPreflightDecision(False, "PILOT_EXPOSURE_CEILING", projected)
    if edge < minimum:
        return PilotPreflightDecision(False, "ANTI_BLEED_NET_EDGE_TOO_LOW", projected)
    return PilotPreflightDecision(True, "PREFLIGHT_ONLY_EXISTING_GATES_REQUIRED", projected)
