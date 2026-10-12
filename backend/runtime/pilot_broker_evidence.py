"""Strict non-executing broker evidence boundary for CSS pilot.

Consumes broker-adapter evidence; does NOT fetch market data, authorize orders,
or trust caller-supplied "verified" booleans as proof of provenance. External
broker adapter authentication, entitlement and signature checks still required.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from backend.runtime.pilot_currency_conversion import (
    PilotCurrencyError, VerifiedRateInput, _code, _number,
)


@dataclass(frozen=True)
class BrokerInstrumentEvidence:
    broker_id: str
    account_id: str
    instrument_id: str
    asset_class: str
    quote_currency: str
    contract_multiplier: Decimal
    observed_at: datetime
    evidence_id: str

    def validate(self, *, now: datetime) -> None:
        for value in (self.broker_id, self.account_id, self.instrument_id, self.evidence_id):
            if type(value) is not str or not value.strip():
                raise PilotCurrencyError("missing broker identity")
        if self.asset_class not in ("CRYPTO", "FX", "FUTURES", "OPTIONS"):
            raise PilotCurrencyError("unsupported asset class")
        _code(self.quote_currency)
        if type(self.contract_multiplier) is not Decimal:
            raise PilotCurrencyError("invalid multiplier type")
        _number(self.contract_multiplier)
        _check_time(self.observed_at, now)


def _check_time(observed_at: datetime, now: datetime) -> None:
    if (not isinstance(observed_at, datetime) or observed_at.tzinfo is None
            or not isinstance(now, datetime) or now.tzinfo is None):
        raise PilotCurrencyError("aware timestamps required")
    age = now.astimezone(timezone.utc) - observed_at.astimezone(timezone.utc)
    if not timedelta(0) <= age <= timedelta(seconds=30):
        raise PilotCurrencyError("stale or future evidence")


def validate_broker_preflight_evidence(
    *,
    instrument: BrokerInstrumentEvidence,
    rate: VerifiedRateInput | None,
    budget_currency: str,
    expected_broker_id: str,
    expected_account_id: str,
    expected_instrument_id: str,
    trusted_evidence_ids: frozenset[str],
    now: datetime,
) -> bool:
    """Enforce evidence binding/freshness. No verification of provider signatures.

    Return False if any identity, currency pair, freshness, or evidence source
    is not independently allow-listed by the caller.
    """
    try:
        instrument.validate(now=now)
        _code(budget_currency)
        if any(type(x) is not str or not x.strip() for x in
               (expected_broker_id, expected_account_id, expected_instrument_id)):
            return False
        if (instrument.broker_id != expected_broker_id
                or instrument.account_id != expected_account_id
                or instrument.instrument_id != expected_instrument_id):
            return False
        if type(trusted_evidence_ids) is not frozenset or instrument.evidence_id not in trusted_evidence_ids:
            return False
        if instrument.quote_currency == budget_currency:
            return rate is None
        if type(rate) is not VerifiedRateInput:
            return False
        if rate.base_currency != instrument.quote_currency or rate.quote_currency != budget_currency:
            return False
        if rate.source_id not in trusted_evidence_ids:
            return False
        _check_time(rate.observed_at, now)
        return True
    except (PilotCurrencyError, ValueError, TypeError, ArithmeticError):
        return False
