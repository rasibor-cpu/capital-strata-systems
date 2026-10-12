from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest

from backend.runtime.pilot_currency_conversion import (
    CURRENT_PILOT_BUDGET, PilotCurrencyError, PilotRiskBudget,
    VerifiedRateInput, convert_risk_up,
)


def test_current_budget_is_a_config_value_not_a_trade_currency():
    assert CURRENT_PILOT_BUDGET.currency == "CAD"
    assert CURRENT_PILOT_BUDGET.max_parent == Decimal("20.00")
    assert CURRENT_PILOT_BUDGET.max_aggregate == Decimal("40.00")
    assert PilotRiskBudget("USD", Decimal("5.00"), Decimal("10.00")).currency == "USD"


@pytest.mark.parametrize("currency", ["USD", "EUR", "GBP", "JPY", "NGN"])
def test_supported_iso_style_codes_use_same_conversion_path(currency):
    t = datetime.now(timezone.utc)
    rate = VerifiedRateInput(currency, "CAD", Decimal("1.25"), t, "test-fixture")
    assert convert_risk_up("2.001", source_currency=currency, budget=CURRENT_PILOT_BUDGET,
                           rate=rate, now=t) == Decimal("2.51")


def test_native_budget_currency_has_no_fx_dependency():
    assert convert_risk_up("0.001", source_currency="CAD", budget=CURRENT_PILOT_BUDGET) == Decimal("0.01")


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-1", True])
def test_bad_amount_rejected(bad):
    with pytest.raises(PilotCurrencyError):
        convert_risk_up(bad, source_currency="CAD", budget=CURRENT_PILOT_BUDGET)


def test_stale_future_inverted_and_missing_rates_rejected():
    now = datetime.now(timezone.utc)
    old = VerifiedRateInput("USD", "CAD", Decimal("1.3"), now-timedelta(minutes=1), "test")
    future = VerifiedRateInput("USD", "CAD", Decimal("1.3"), now+timedelta(seconds=1), "test")
    inverted = VerifiedRateInput("CAD", "USD", Decimal("0.8"), now, "test")
    for bad in [old, future, inverted, None]:
        with pytest.raises(PilotCurrencyError):
            convert_risk_up("10", source_currency="USD", budget=CURRENT_PILOT_BUDGET, rate=bad, now=now)


def test_same_currency_rate_rejected():
    t = datetime.now(timezone.utc)
    with pytest.raises(PilotCurrencyError):
        convert_risk_up("5", source_currency="CAD", budget=CURRENT_PILOT_BUDGET,
                        rate=VerifiedRateInput("USD", "CAD", Decimal("1.3"), t, "test"))


def test_unverified_currency_code_or_budget_fails_closed():
    with pytest.raises(PilotCurrencyError):
        PilotRiskBudget("USDT", Decimal("20.00"), Decimal("40.00"))
    with pytest.raises(PilotCurrencyError):
        PilotRiskBudget("USD", Decimal("20.00"), Decimal("10.00"))
