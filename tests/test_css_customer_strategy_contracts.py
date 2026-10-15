from datetime import datetime, timedelta, timezone

import pytest

from backend.runtime.css_customer_strategy_contracts import (
    CopyMandate, CustomerPreference, PROFILES, Trader, TradingMode,
    may_submit_live_order,
)


def mandate(trader=Trader.BALANCED, **overrides):
    now = datetime(2026, 10, 15, tzinfo=timezone.utc)
    data = dict(customer_id="customer", brokerage_account_id="broker",
                trader=trader, strategy_id=PROFILES[trader].strategy_id,
                authorized_at=now, expires_at=now + timedelta(days=1),
                allocated_capital=100.0, max_loss_fraction=0.1,
                allowed_instruments=("equity",), mfa_verified=True)
    data.update(overrides)
    return CopyMandate(**data), now


def test_all_five_strategies_have_distinct_strategy_and_signal_families():
    assert len(PROFILES) == 5
    assert len({p.strategy_id for p in PROFILES.values()}) == 5
    assert len({p.entry_family for p in PROFILES.values()}) == 5


def test_copy_mandate_permits_only_within_explicit_window():
    m, now = mandate()
    assert m.permits_new_trade(now, instrument="equity")
    assert not m.permits_new_trade(m.expires_at, instrument="equity")
    assert not m.permits_new_trade(now, instrument="options")


@pytest.mark.parametrize("changes", [
    {"revoked": True}, {"mfa_verified": False}, {"strategy_id": "different"},
    {"allocated_capital": 0}, {"max_loss_fraction": 1.5},
    {"expires_at": datetime(2026, 11, 15, tzinfo=timezone.utc)},
])
def test_copy_mandate_fails_closed(changes):
    m, now = mandate(**changes)
    assert not m.permits_new_trade(now, instrument="equity")


def test_copy_requires_trader_but_simulation_does_not():
    with pytest.raises(ValueError):
        CustomerPreference(TradingMode.COPY)
    assert CustomerPreference(TradingMode.SIMULATED).selected_trader is None


def test_live_execution_never_enabled_by_foundation():
    assert may_submit_live_order() is False
