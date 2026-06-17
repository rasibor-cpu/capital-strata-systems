from engine.risk.oanda_margin_adapter import OandaMarginAdapter, LegacyCompatibleMarginSnapshot
from engine.risk.margin_snapshot import MarginSnapshot
from engine.risk.margin_state import MarginState

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
    assert isinstance(snapshot, MarginSnapshot)
    assert snapshot.broker == "OANDA"
    assert snapshot.margin_state == MarginState.NORMAL
    assert snapshot.equity == 10000.0
    assert snapshot.margin_used == 2000.0
    assert snapshot.margin_available == 8000.0
    assert snapshot.buying_power == 8000.0
    assert snapshot.margin_ratio == 0.2

def test_oanda_margin_adapter_custom_values():
    adapter = OandaMarginAdapter(
        available_margin=25000.0,
        required_margin=17500.0,
    )
    snapshot = adapter.get_margin_snapshot()
    assert snapshot.equity == 25000.0
    assert snapshot.margin_used == 17500.0
    assert snapshot.margin_available == 7500.0
    assert snapshot.buying_power == 7500.0
    assert snapshot.margin_ratio == 0.7
    assert snapshot.margin_state == MarginState.RESTRICTED

def test_oanda_margin_adapter_account_id():
    adapter = OandaMarginAdapter(account_id="TEST-ACCOUNT")
    snapshot = adapter.get_margin_snapshot()
    assert snapshot.account_id == "TEST-ACCOUNT"

def test_oanda_margin_adapter_live_mode_success_path_returns_canonical_snapshot():
    adapter = OandaMarginAdapter(
        mode="LIVE",
        adapter_factory=FakeLiveOandaAdapter,
    )
    snapshot = adapter.get_margin_snapshot()
    assert isinstance(snapshot, MarginSnapshot)
    assert snapshot.broker == "OANDA"
    assert snapshot.account_id == "LIVE-ACCOUNT"
    assert snapshot.margin_used == 1251.00
    assert snapshot.equity == 10000.00
    assert snapshot.margin_available == 8749.00
    assert snapshot.margin_ratio == 0.1251
    assert adapter.last_note == "LIVE_MARGIN_SNAPSHOT_OK"
    assert snapshot.margin_state == MarginState.NORMAL

def test_oanda_margin_adapter_live_mode_fallback_path_returns_simulated_snapshot():
    adapter = OandaMarginAdapter(
        mode="LIVE",
        available_margin=5000.0,
        required_margin=4500.0,
        adapter_factory=FakeUnavailableOandaAdapter,
    )
    snapshot = adapter.get_margin_snapshot()
    assert isinstance(snapshot, MarginSnapshot)
    assert snapshot.account_id == "SIMULATED-OANDA"
    assert snapshot.equity == 5000.0
    assert snapshot.margin_used == 4500.0
    assert snapshot.margin_available == 500.0
    assert snapshot.margin_ratio == 0.9
    assert snapshot.margin_state == MarginState.CRITICAL
    assert adapter.last_note == "LIVE_FALLBACK_ACCOUNT_SUMMARY_UNAVAILABLE"

def test_oanda_margin_adapter_invalid_live_mode_payload_falls_back_gracefully():
    adapter = OandaMarginAdapter(
        mode="LIVE",
        adapter_factory=lambda: None,
    )
    snapshot = adapter.get_margin_snapshot()
    assert isinstance(snapshot, MarginSnapshot)
    assert adapter.last_note == "LIVE_FALLBACK_NO_OANDA_ADAPTER"

def test_oanda_margin_adapter_liquidation_risk_classification():
    adapter = OandaMarginAdapter(
        available_margin=1000.0,
        required_margin=1500.0,
    )
    snapshot = adapter.get_margin_snapshot()
    assert snapshot.margin_ratio == 1.5
    assert snapshot.margin_state == MarginState.LIQUIDATION_RISK

def test_oanda_margin_adapter_zero_equity():
    adapter = OandaMarginAdapter(
        available_margin=0.0,
        required_margin=1500.0,
    )
    snapshot = adapter.get_margin_snapshot()
    assert snapshot.margin_ratio == 0.0
    assert snapshot.margin_state == MarginState.NORMAL
