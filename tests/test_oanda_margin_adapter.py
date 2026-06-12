from engine.risk.oanda_margin_adapter import OandaMarginAdapter


def test_oanda_margin_adapter_returns_snapshot():
    adapter = OandaMarginAdapter()

    snapshot = adapter.get_margin_snapshot()

    assert snapshot.broker_name == "OANDA"
    assert snapshot.margin_source == "SIMULATED"
    assert snapshot.available_margin == 10000.0
    assert snapshot.required_margin == 2000.0
    assert snapshot.free_margin == 8000.0
    assert snapshot.margin_utilization_pct == 20.0


def test_oanda_margin_adapter_custom_values():
    adapter = OandaMarginAdapter(
        available_margin=25000.0,
        required_margin=5000.0,
    )

    snapshot = adapter.get_margin_snapshot()

    assert snapshot.available_margin == 25000.0
    assert snapshot.required_margin == 5000.0
    assert snapshot.free_margin == 20000.0
    assert snapshot.margin_utilization_pct == 20.0


def test_oanda_margin_adapter_account_id():
    adapter = OandaMarginAdapter(account_id="TEST-ACCOUNT")

    snapshot = adapter.get_margin_snapshot()

    assert snapshot.account_id == "TEST-ACCOUNT"