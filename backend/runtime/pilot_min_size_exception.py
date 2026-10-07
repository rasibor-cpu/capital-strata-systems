"""Governed, single-use exception to AntiBleed's minimum trade-size rule.

DISABLED BY DEFAULT. ``PILOT_MIN_SIZE_EXCEPTION_ENABLED`` is a code constant;
enabling it is a governed source change requiring owner approval, not a
runtime/env toggle.

Owner decision 2026-10-07: design approved, activation NOT approved. It may not
be enabled until CSS-061 regression is reconciled, CSS-062 pilot security review,
CSS-063 broker/account/reconciliation safeguards and CSS-064 governed endurance
have passed, AntiBleed call-site currency semantics are explicit and verified,
exposure reservation is concurrency-safe, dual-control authorization is in place,
live-order wiring is independently reviewed, and a separate owner activation
decision is recorded. See docs/governance/CSS_PROGRAM_REGISTER.md.

Scope (only the ``trade_size_too_small`` rule is affected):
- AntiBleed's expected-move-vs-cost, net-edge and cooldown rules still apply;
- the capability is minted only from a ledger-recorded one-time pilot
  consumption receipt, for exactly one symbol, within a short TTL, and up to the
  pilot's effective ceiling (never above the canonical CAD order-limit cap);
- the capability is MAC'd with a per-process random key, so it cannot be forged
  from data and does not survive a process restart;
- each capability (and each receipt) can be applied at most once per process;
  cross-restart reuse is prevented by the ledger's atomic claim.

Residual blocker: AntiBleed's ``trade_size`` input currency is unspecified at
the ExecutionGate call site; until CAD-denominated sizing is certified end to
end this exception must remain disabled.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from backend.runtime.governed_pilot_profile import canonical_exposure_cap_cad
from backend.runtime.pilot_authorization_ledger import (
    PilotAuthorizationLedger,
    PilotConsumptionReceipt,
)


PILOT_MIN_SIZE_EXCEPTION_ENABLED = False
MAX_EXCEPTION_TTL = timedelta(seconds=120)

_PROCESS_KEY = secrets.token_bytes(32)
_LOCK = threading.Lock()
_USED_EXCEPTIONS: set[str] = set()
_RECEIPTS_WITH_EXCEPTION: set[str] = set()


class PilotMinSizeExceptionError(RuntimeError):
    """The exception cannot be issued; ordinary AntiBleed rules remain in force."""


@dataclass(frozen=True)
class PilotMinSizeException:
    exception_id: str
    receipt_entry_hash: str
    symbol: str
    max_notional_cad: Decimal
    expires_at: datetime
    mac: str


def _mac(exception_id: str, receipt_entry_hash: str, symbol: str, max_notional: Decimal, expires_at: datetime) -> str:
    message = "|".join((exception_id, receipt_entry_hash, symbol, str(max_notional), expires_at.isoformat()))
    return hmac.new(_PROCESS_KEY, message.encode("utf-8"), hashlib.sha256).hexdigest()


def issue_pilot_min_size_exception(
    ledger: PilotAuthorizationLedger,
    receipt: PilotConsumptionReceipt,
    *,
    symbol: str,
    ttl: timedelta = MAX_EXCEPTION_TTL,
    now: datetime | None = None,
) -> PilotMinSizeException:
    if not PILOT_MIN_SIZE_EXCEPTION_ENABLED:
        raise PilotMinSizeExceptionError("pilot minimum-size exception is disabled")
    if not isinstance(ledger, PilotAuthorizationLedger) or not ledger.receipt_is_recorded(receipt):
        raise PilotMinSizeExceptionError("receipt not recorded in intact ledger")
    normalized = str(symbol).strip().upper()
    if normalized != receipt.instrument:
        raise PilotMinSizeExceptionError("symbol outside approved scope")
    if not isinstance(ttl, timedelta) or not timedelta(0) < ttl <= MAX_EXCEPTION_TTL:
        raise PilotMinSizeExceptionError("ttl outside permitted window")
    ceiling = min(Decimal(receipt.effective_ceiling_cad), canonical_exposure_cap_cad())
    if ceiling <= 0:
        raise PilotMinSizeExceptionError("no permitted notional")
    now = now or datetime.now(timezone.utc)
    with _LOCK:
        if receipt.entry_hash in _RECEIPTS_WITH_EXCEPTION:
            raise PilotMinSizeExceptionError("exception already issued for this receipt")
        _RECEIPTS_WITH_EXCEPTION.add(receipt.entry_hash)
    exception_id = secrets.token_hex(16)
    expires_at = now + ttl
    return PilotMinSizeException(
        exception_id=exception_id, receipt_entry_hash=receipt.entry_hash, symbol=normalized,
        max_notional_cad=ceiling, expires_at=expires_at,
        mac=_mac(exception_id, receipt.entry_hash, normalized, ceiling, expires_at),
    )


def apply_pilot_min_size_exception(candidate: Any, *, symbol: Any, trade_size: Any, now: datetime | None = None) -> bool:
    """Return True (and burn the capability) only if every condition holds. Never raises."""
    try:
        if not PILOT_MIN_SIZE_EXCEPTION_ENABLED or type(candidate) is not PilotMinSizeException:
            return False
        expected = _mac(candidate.exception_id, candidate.receipt_entry_hash, candidate.symbol,
                        candidate.max_notional_cad, candidate.expires_at)
        if not hmac.compare_digest(expected, candidate.mac):
            return False
        now = now or datetime.now(timezone.utc)
        if now >= candidate.expires_at:
            return False
        if str(symbol).strip().upper() != candidate.symbol:
            return False
        if isinstance(trade_size, bool):
            return False
        size = Decimal(str(trade_size))
        if not size.is_finite() or size <= 0 or size > candidate.max_notional_cad:
            return False
        if candidate.max_notional_cad > canonical_exposure_cap_cad():
            return False
        with _LOCK:
            if candidate.exception_id in _USED_EXCEPTIONS:
                return False
            _USED_EXCEPTIONS.add(candidate.exception_id)
        return True
    except (InvalidOperation, ValueError, TypeError, AttributeError):
        return False
