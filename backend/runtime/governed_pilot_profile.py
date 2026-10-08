"""Governed, configurable pilot exposure preflight. No execution/arming side effects.

This component is a *necessary* prospective order gate, never sufficient
authorization. Callers must additionally pass the existing R7, AntiBleed,
broker reconciliation, RBAC and kill-switch controls. No trading path is
wired to this module until integration tests certify all entry points.

Hardening (PR #104):
- every construction path (``__init__``, ``dataclasses.replace``,
  ``from_mapping``) runs the same fail-closed validation;
- unknown/unapproved configuration fields are rejected;
- the profile is bound to the exact release/candidate commit SHA and requires
  dual-control approval (see ``pilot_dual_control``): two independently
  attributable HMAC approvals over the canonical profile digest, re-verified on
  every evaluation, so in-memory tampering fails closed;
- the effective ceiling is ``min(profile ceiling, canonical order-limit cap)``
  so a profile can never raise the existing CAD 20 governance cap;
- any unexpected exception during evaluation returns a blocked decision.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, fields
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from backend.config.order_limit_config import DEFAULT_ORDER_LIMIT_CONFIG


PILOT_SCOPE = "PILOT_PREFLIGHT_ONE_ORDER"
PILOT_SCOPE_MICRO = "PILOT_PREFLIGHT_MICRO_ENVELOPE"
PILOT_SCOPES = frozenset({PILOT_SCOPE, PILOT_SCOPE_MICRO})
PILOT_CURRENCIES = frozenset({"CAD"})
# Cash, unlevered, non-derivative only. Options/futures/margin products are excluded.
PILOT_ASSET_CLASSES = frozenset({"EQUITY", "ETF", "FX_SPOT", "CRYPTO_SPOT"})
MAX_APPROVAL_WINDOW = timedelta(hours=24)
MAX_RECONCILIATION_AGE_SECONDS = 30
_IDENTIFIER = re.compile(r"^[A-Za-z0-9._:\-]{1,64}$")
_CENT = Decimal("0.01")
_COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")


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


def _identifier(raw: Any, name: str) -> str:
    if not isinstance(raw, str) or not _IDENTIFIER.fullmatch(raw.strip()):
        raise PilotConfigurationError(f"{name}: invalid identifier")
    return raw.strip()


def _timestamp(raw: Any, name: str) -> datetime:
    if isinstance(raw, datetime):
        value = raw
    else:
        try:
            value = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except (ValueError, TypeError) as exc:
            raise PilotConfigurationError(f"{name}: invalid timestamp") from exc
    if value.tzinfo is None:
        raise PilotConfigurationError(f"{name}: timezone required")
    return value.astimezone(timezone.utc)


def canonical_exposure_cap_cad() -> Decimal:
    """The pre-existing governance cap; a pilot profile can only narrow it."""
    cfg = DEFAULT_ORDER_LIMIT_CONFIG
    return min(cfg.live_pilot_max_total_cad, cfg.live_pilot_max_position_cad)


@dataclass(frozen=True)
class GovernedPilotProfile:
    """The monetary ceiling is an operator-approved *value*, not a code constant."""

    approval_id: str
    sponsor_id: str
    release_approver_id: str
    release_sha: str
    scope: str
    broker_id: str
    account_id: str
    asset_class: str
    instrument: str
    currency: str
    max_aggregate_exposure: Decimal
    issued_at: datetime
    expires_at: datetime
    session_id: str
    max_order_count: int = 1
    allow_margin: bool = False

    def __post_init__(self) -> None:
        # Runs for direct construction and dataclasses.replace(), not only from_mapping().
        for name in ("approval_id", "sponsor_id", "release_approver_id", "broker_id", "account_id", "instrument", "session_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or value != value.strip() or not _IDENTIFIER.fullmatch(value):
                raise PilotConfigurationError(f"{name}: invalid identifier")
        if self.sponsor_id == self.release_approver_id:
            raise PilotConfigurationError("dual control requires two distinct approvers")
        if not isinstance(self.release_sha, str) or not _COMMIT_SHA.fullmatch(self.release_sha):
            raise PilotConfigurationError("release_sha must be an exact 40-hex commit")
        if self.instrument != self.instrument.upper():
            raise PilotConfigurationError("instrument must be normalized upper-case")
        if self.scope not in PILOT_SCOPES:
            raise PilotConfigurationError("unapproved authorization scope")
        if self.asset_class not in PILOT_ASSET_CLASSES:
            raise PilotConfigurationError("asset class not approved for pilot")
        if self.currency not in PILOT_CURRENCIES:
            raise PilotConfigurationError("CAD-only pilot until currency conversion certified")
        if type(self.max_aggregate_exposure) is not Decimal or not self.max_aggregate_exposure.is_finite():
            raise PilotConfigurationError("max_aggregate_exposure must be a finite Decimal")
        if self.max_aggregate_exposure <= 0:
            raise PilotConfigurationError("pilot exposure ceiling must be positive")
        if self.max_aggregate_exposure != self.max_aggregate_exposure.quantize(_CENT):
            raise PilotConfigurationError("pilot exposure ceiling must be whole cents")
        for name in ("issued_at", "expires_at"):
            value = getattr(self, name)
            if not isinstance(value, datetime) or value.tzinfo is None:
                raise PilotConfigurationError(f"{name}: timezone-aware datetime required")
        if not self.issued_at < self.expires_at <= self.issued_at + MAX_APPROVAL_WINDOW:
            raise PilotConfigurationError("approval window invalid or exceeds 24h")
        if type(self.max_order_count) is not int or self.max_order_count < 1:
            raise PilotConfigurationError("max_order_count must be a positive integer")
        if self.scope == PILOT_SCOPE and self.max_order_count != 1:
            raise PilotConfigurationError("one-order pilot scope requires max_order_count=1")
        if self.scope == PILOT_SCOPE_MICRO:
            canonical_max_orders = DEFAULT_ORDER_LIMIT_CONFIG.live_pilot_max_orders_per_session
            if self.max_order_count > canonical_max_orders:
                raise PilotConfigurationError(
                    f"micro-envelope order count exceeds canonical ceiling {canonical_max_orders}"
                )
        if self.allow_margin is not False:
            raise PilotConfigurationError("margin is prohibited")

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "GovernedPilotProfile":
        if not isinstance(values, Mapping):
            raise PilotConfigurationError("approved profile required")
        allowed = {f.name for f in fields(cls)}
        unknown = set(values) - allowed
        if unknown:
            raise PilotConfigurationError(f"unapproved configuration fields: {sorted(map(str, unknown))}")
        required = allowed - {"max_order_count", "allow_margin"}
        if any(values.get(key) is None or str(values.get(key)).strip() == "" for key in required):
            raise PilotConfigurationError("missing required approval fields")
        return cls(
            approval_id=_identifier(values["approval_id"], "approval_id"),
            sponsor_id=_identifier(values["sponsor_id"], "sponsor_id"),
            release_approver_id=_identifier(values["release_approver_id"], "release_approver_id"),
            release_sha=str(values["release_sha"]).strip(),
            scope=str(values["scope"]).strip(),
            broker_id=_identifier(values["broker_id"], "broker_id"),
            account_id=_identifier(values["account_id"], "account_id"),
            asset_class=str(values["asset_class"]).strip().upper(),
            instrument=_identifier(values["instrument"], "instrument").upper(),
            currency=str(values["currency"]).strip().upper(),
            max_aggregate_exposure=_money(values["max_aggregate_exposure"], "max_aggregate_exposure"),
            issued_at=_timestamp(values["issued_at"], "issued_at"),
            expires_at=_timestamp(values["expires_at"], "expires_at"),
            session_id=_identifier(values["session_id"], "session_id"),
            max_order_count=values.get("max_order_count", 1),
            allow_margin=values.get("allow_margin", False),
        )

    def canonical_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for f in fields(self):
            value = getattr(self, f.name)
            if isinstance(value, datetime):
                value = value.astimezone(timezone.utc).isoformat()
            elif isinstance(value, Decimal):
                value = str(value)
            payload[f.name] = value
        return payload

    def digest(self) -> str:
        encoded = json.dumps(self.canonical_payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def effective_ceiling_cad(self) -> Decimal:
        return min(self.max_aggregate_exposure, canonical_exposure_cap_cad())


@dataclass(frozen=True)
class PilotPreflightDecision:
    approved: bool
    reason: str
    projected_exposure_cad: Decimal
    profile_digest: str = ""


def evaluate_pilot_preflight(
    profile: GovernedPilotProfile | None,
    *,
    approvals: Any,
    key_registry: Any,
    running_release_sha: str,
    broker_id: str,
    account_id: str,
    asset_class: str,
    instrument: str,
    currency: str,
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

    Never places orders, writes authorization, consumes the approval, or
    overrides AntiBleed. Uncertified FX conversions must be rejected upstream
    rather than inferred.
    """
    try:
        return _evaluate(**locals())
    except Exception:
        return PilotPreflightDecision(False, "PILOT_BLOCKED_EVALUATION_ERROR", Decimal("0"))


def _evaluate(
    profile, approvals, key_registry, running_release_sha, broker_id, account_id, asset_class, instrument, currency,
    session_id, current_exposure_cad, pending_orders_cad, proposed_order_cad, estimated_fees_cad,
    reconciled, reconciled_at, expected_net_edge_bps, required_net_edge_bps,
    orders_already_submitted, margin_requested, now,
) -> PilotPreflightDecision:
    zero = Decimal("0")
    if type(profile) is not GovernedPilotProfile:
        return PilotPreflightDecision(False, "PILOT_BLOCKED", zero)
    from backend.runtime.pilot_dual_control import keys_currently_usable, verify_dual_control

    if not verify_dual_control(profile, approvals, registry=key_registry):
        return PilotPreflightDecision(False, "PILOT_DUAL_CONTROL_INVALID", zero)
    digest = profile.digest()
    now = now or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or now < profile.issued_at or now >= profile.expires_at:
        return PilotPreflightDecision(False, "PILOT_EXPIRED_OR_CLOCK_INVALID", zero, digest)
    if not keys_currently_usable(approvals, key_registry, now):
        return PilotPreflightDecision(False, "PILOT_APPROVAL_KEY_REVOKED_OR_RETIRED", zero, digest)
    if running_release_sha != profile.release_sha:
        return PilotPreflightDecision(False, "PILOT_RELEASE_MISMATCH", zero, digest)
    if (broker_id != profile.broker_id or account_id != profile.account_id
            or str(asset_class).strip().upper() != profile.asset_class
            or str(instrument).strip().upper() != profile.instrument
            or str(currency).strip().upper() != profile.currency
            or session_id != profile.session_id):
        return PilotPreflightDecision(False, "PILOT_SCOPE_MISMATCH", zero, digest)
    if margin_requested is not False or reconciled is not True:
        return PilotPreflightDecision(False, "MARGIN_OR_RECONCILIATION_BLOCK", zero, digest)
    if not isinstance(reconciled_at, datetime) or reconciled_at.tzinfo is None:
        return PilotPreflightDecision(False, "MARGIN_OR_RECONCILIATION_BLOCK", zero, digest)
    age = (now - reconciled_at).total_seconds()
    if age < 0 or age > MAX_RECONCILIATION_AGE_SECONDS:
        return PilotPreflightDecision(False, "RECONCILIATION_STALE", zero, digest)
    if type(orders_already_submitted) is not int or orders_already_submitted < 0:
        return PilotPreflightDecision(False, "PILOT_ORDER_COUNT_INVALID", zero, digest)
    if orders_already_submitted >= profile.max_order_count:
        return PilotPreflightDecision(False, "PILOT_ORDER_BUDGET_EXHAUSTED", zero, digest)
    try:
        current = _money(current_exposure_cad, "current_exposure")
        pending = _money(pending_orders_cad, "pending_orders")
        proposed = _money(proposed_order_cad, "proposed_order")
        fees = _money(estimated_fees_cad, "estimated_fees")
        edge = _money(expected_net_edge_bps, "expected_net_edge")
        minimum = _money(required_net_edge_bps, "required_net_edge")
    except PilotConfigurationError:
        return PilotPreflightDecision(False, "INVALID_FINANCIAL_EVIDENCE", zero, digest)
    projected = current + pending + proposed + fees
    if proposed <= 0 or projected > profile.effective_ceiling_cad():
        return PilotPreflightDecision(False, "PILOT_EXPOSURE_CEILING", projected, digest)
    if edge < minimum:
        return PilotPreflightDecision(False, "ANTI_BLEED_NET_EDGE_TOO_LOW", projected, digest)
    return PilotPreflightDecision(True, "PREFLIGHT_ONLY_EXISTING_GATES_REQUIRED", projected, digest)
