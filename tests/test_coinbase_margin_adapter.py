from engine.risk.broker_margin_contract import BrokerMarginSnapshot
from engine.risk.coinbase_margin_adapter import CoinbaseMarginAdapter


class FakeCoinbaseMarginAdapter:
    account_id = "LIVE-COINBASE"

    def get_margin_summary(self):
        return {
            "account": {
                "required_margin": "2500.00",
                "available_margin": "10000.00",
                "free_margin": "7500.00",
            }
        }


class FakeCoinbaseSpotAdapter:
    account_id = "SPOT-COINBASE"

    def get_account_balance(self):
        return {
            "mode": "live",
            "balance": 12500.0,
            "equity": 12500.0,
            "source": "COINBASE",
        }


class FakeCoinbaseUnavailableAdapter:
    account_id = "BROKEN-COINBASE"

    def get_account_balance(self):
        raise RuntimeError("network unavailable")


def test_coinbase_margin_adapter_simulated_mode_defaults():
    adapter = CoinbaseMarginAdapter()

    snapshot = adapter.get_margin_snapshot()

    assert isinstance(snapshot, BrokerMarginSnapshot)
    assert adapter.mode == "SIMULATED"
    assert snapshot.broker_name == "COINBASE"
    assert snapshot.account_id == "SIMULATED-COINBASE"
    assert snapshot.available_margin == 10000.0
    assert snapshot.required_margin == 0.0
    assert snapshot.free_margin == 10000.0
    assert snapshot.margin_utilization_pct == 0.0
    assert snapshot.margin_source == "SIMULATED"


def test_coinbase_margin_adapter_custom_simulated_values():
    adapter = CoinbaseMarginAdapter(
        account_id="CUSTOM-COINBASE",
        available_margin=20000.0,
        required_margin=5000.0,
    )

    snapshot = adapter.get_margin_snapshot()

    assert snapshot.account_id == "CUSTOM-COINBASE"
    assert snapshot.available_margin == 20000.0
    assert snapshot.required_margin == 5000.0
    assert snapshot.free_margin == 15000.0
    assert snapshot.margin_utilization_pct == 25.0


def test_coinbase_margin_adapter_live_mode_success_path_with_margin_data():
    adapter = CoinbaseMarginAdapter(
        mode="LIVE",
        adapter_factory=FakeCoinbaseMarginAdapter,
    )

    snapshot = adapter.get_margin_snapshot()

    assert isinstance(snapshot, BrokerMarginSnapshot)
    assert snapshot.broker_name == "COINBASE"
    assert snapshot.account_id == "LIVE-COINBASE"
    assert snapshot.margin_source == "LIVE"
    assert snapshot.required_margin == 2500.0
    assert snapshot.available_margin == 10000.0
    assert snapshot.free_margin == 7500.0
    assert snapshot.margin_utilization_pct == 25.0
    assert adapter.last_note == "LIVE_MARGIN_SNAPSHOT_OK"


def test_coinbase_margin_adapter_live_mode_fallback_path():
    adapter = CoinbaseMarginAdapter(
        mode="LIVE",
        adapter_factory=FakeCoinbaseUnavailableAdapter,
    )

    snapshot = adapter.get_margin_snapshot()

    assert isinstance(snapshot, BrokerMarginSnapshot)
    assert snapshot.margin_source == "SIMULATED"
    assert snapshot.account_id == "SIMULATED-COINBASE"
    assert snapshot.available_margin == 10000.0
    assert snapshot.required_margin == 0.0
    assert snapshot.free_margin == 10000.0
    assert snapshot.margin_utilization_pct == 0.0
    assert adapter.last_note.startswith("LIVE_FALLBACK_ERROR_")


def test_coinbase_margin_adapter_returns_canonical_snapshot_in_live_spot_mode():
    adapter = CoinbaseMarginAdapter(
        mode="LIVE",
        adapter_factory=FakeCoinbaseSpotAdapter,
    )

    snapshot = adapter.get_margin_snapshot()

    assert isinstance(snapshot, BrokerMarginSnapshot)
    assert snapshot.margin_source == "LIVE"


def test_coinbase_margin_adapter_margin_utilization_calculation():
    adapter = CoinbaseMarginAdapter(
        available_margin=8000.0,
        required_margin=1000.0,
    )

    snapshot = adapter.get_margin_snapshot()

    assert snapshot.margin_utilization_pct == 12.5


def test_coinbase_spot_defaults_to_non_margin_without_clear_margin_data():
    adapter = CoinbaseMarginAdapter(
        mode="LIVE",
        adapter_factory=FakeCoinbaseSpotAdapter,
    )

    snapshot = adapter.get_margin_snapshot()

    assert snapshot.account_id == "SPOT-COINBASE"
    assert snapshot.available_margin == 12500.0
    assert snapshot.required_margin == 0.0
    assert snapshot.free_margin == 12500.0
    assert snapshot.margin_utilization_pct == 0.0
    assert adapter.last_note == "LIVE_MARGIN_SNAPSHOT_OK"
