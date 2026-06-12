from engine.risk.broker_margin_contract import BrokerMarginSnapshot
from engine.risk.oanda_margin_adapter import OandaMarginAdapter


class FakeLiveOandaAdapter:
    account_id = "LIVE-ACCOUNT"

    def is_configured(self):
        return True

    def get_account_summary(self):
        return {
            "ok": True,
            "data": {
                "account": {
                    "marginUsed": "1251.00",
                    "NAV": "10000.00",
                    "marginAvailable": "8749.00",
                }
            },
        }


class FakeUnavailableOandaAdapter:
    account_id = "BROKEN-ACCOUNT"

    def is_configured(self):
        return True

    def get_account_summary(self):
        return {
            "ok": False,
            "status": 503,
            "data": None,
            "error": "network_failure",
        }


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


def test_oanda_margin_adapter_simulated_mode_is_default():
    adapter = OandaMarginAdapter()

    snapshot = adapter.get_margin_snapshot()

    assert isinstance(snapshot, BrokerMarginSnapshot)
    assert adapter.mode == "SIMULATED"
    assert snapshot.margin_source == "SIMULATED"


def test_oanda_margin_adapter_live_mode_success_path_returns_canonical_snapshot():
    adapter = OandaMarginAdapter(
        mode="LIVE",
        adapter_factory=FakeLiveOandaAdapter,
    )

    snapshot = adapter.get_margin_snapshot()

    assert isinstance(snapshot, BrokerMarginSnapshot)
    assert snapshot.broker_name == "OANDA"
    assert snapshot.account_id == "LIVE-ACCOUNT"
    assert snapshot.margin_source == "LIVE"
    assert snapshot.required_margin == 1251.00
    assert snapshot.available_margin == 10000.00
    assert snapshot.free_margin == 8749.00
    assert snapshot.margin_utilization_pct == 12.51
    assert adapter.last_note == "LIVE_MARGIN_SNAPSHOT_OK"


def test_oanda_margin_adapter_live_mode_fallback_path_returns_simulated_snapshot():
    adapter = OandaMarginAdapter(
        mode="LIVE",
        available_margin=5000.0,
        required_margin=1000.0,
        adapter_factory=FakeUnavailableOandaAdapter,
    )

    snapshot = adapter.get_margin_snapshot()

    assert isinstance(snapshot, BrokerMarginSnapshot)
    assert snapshot.margin_source == "SIMULATED"
    assert snapshot.account_id == "SIMULATED-OANDA"
    assert snapshot.available_margin == 5000.0
    assert snapshot.required_margin == 1000.0
    assert snapshot.free_margin == 4000.0
    assert snapshot.margin_utilization_pct == 20.0
    assert adapter.last_note == "LIVE_FALLBACK_ACCOUNT_SUMMARY_UNAVAILABLE"


def test_oanda_margin_adapter_invalid_live_mode_payload_falls_back_gracefully():
    adapter = OandaMarginAdapter(
        mode="LIVE",
        adapter_factory=lambda: None,
    )

    snapshot = adapter.get_margin_snapshot()

    assert isinstance(snapshot, BrokerMarginSnapshot)
    assert snapshot.margin_source == "SIMULATED"
    assert adapter.last_note == "LIVE_FALLBACK_NO_OANDA_ADAPTER"
