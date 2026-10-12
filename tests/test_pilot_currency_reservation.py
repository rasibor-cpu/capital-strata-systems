from datetime import datetime, timedelta, timezone
from decimal import Decimal
from backend.runtime.pilot_currency_conversion import VerifiedRateInput
from backend.runtime.pilot_currency_reservation import reserve_converted_pilot_exposure
from backend.runtime.pilot_exposure_reservation import PilotExposureReservationLedger


def test_two_currency_parents_account_for_fees_and_cap(tmp_path):
    ledger = PilotExposureReservationLedger(tmp_path / "reservations.sqlite3")
    now = datetime.now(timezone.utc)
    eur = VerifiedRateInput("EUR", "CAD", Decimal("1.5"), now, "synthetic-eur")
    usd = VerifiedRateInput("USD", "CAD", Decimal("1.25"), now, "synthetic-usd")

    def submit(parent, child, src, amount, rate):
        return reserve_converted_pilot_exposure(
            ledger, parent_id=parent, child_id=child,
            source_currency=src, gross_notional=amount,
            cash_commitment=amount, maximum_loss=amount,
            fees="0.10", risk_bounded=True, instrument_verified=True,
            rate_provenance_verified=True, rate=rate, now=now)

    first = submit("A", "1", "EUR", "10", eur)
    second = submit("B", "2", "USD", "10", usd)
    assert first.decision and first.decision.approved
    assert second.decision and second.decision.approved
    assert first.risk_amount_budget_currency == Decimal("15.15")
    assert second.risk_amount_budget_currency == Decimal("12.63")
    assert len(ledger.snapshot()) == 2
    assert not submit("C", "3", "USD", "1", usd).decision.approved


def test_stale_rate_does_not_reserve(tmp_path):
    ledger = PilotExposureReservationLedger(tmp_path / "reservations.sqlite3")
    now = datetime.now(timezone.utc)
    stale = VerifiedRateInput("USD", "CAD", Decimal("1.25"), now - timedelta(minutes=3), "synthetic")
    result = reserve_converted_pilot_exposure(
        ledger, parent_id="A", child_id="1", source_currency="USD",
        gross_notional="3", cash_commitment="3", maximum_loss="3", fees="0",
        rate=stale, now=now, risk_bounded=True, instrument_verified=True,
        rate_provenance_verified=True)
    assert result.decision is None and ledger.snapshot() == []


def test_missing_independent_verification_fails_closed(tmp_path):
    ledger = PilotExposureReservationLedger(tmp_path / "reservations.sqlite3")
    result = reserve_converted_pilot_exposure(
        ledger, parent_id="A", child_id="1", source_currency="CAD",
        gross_notional="3", cash_commitment="3", maximum_loss="3", fees="0",
        risk_bounded=True, instrument_verified=True,
        rate_provenance_verified=False)
    assert result.decision is None and ledger.snapshot() == []


def test_duplicate_order_rejected(tmp_path):
    ledger = PilotExposureReservationLedger(tmp_path / "reservations.sqlite3")
    def submit():
        return reserve_converted_pilot_exposure(
            ledger, parent_id="A", child_id="1", source_currency="CAD",
            gross_notional="5", cash_commitment="5", maximum_loss="5", fees="0",
            risk_bounded=True, instrument_verified=True, rate_provenance_verified=True)
    assert submit().decision.approved
    assert not submit().decision.approved
