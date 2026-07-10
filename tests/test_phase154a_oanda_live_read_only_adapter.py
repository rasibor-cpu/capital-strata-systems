from __future__ import annotations

from datetime import datetime, timezone

from backend.runtime.oanda_live_read_only_adapter import OandaLiveReadOnlyAdapter


class FakeOandaReadClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_account_summary(self):
        self.calls.append("get_account_summary")
        return {
            "ok": True,
            "account": {
                "balance": "100.00",
                "NAV": "105.00",
                "marginAvailable": "90.00",
                "marginUsed": "15.00",
            },
        }

    def get_open_positions(self):
        self.calls.append("get_open_positions")
        return {"positions": []}

    def get_open_trades(self):
        self.calls.append("get_open_trades")
        return {"trades": []}

    def get_instruments(self):
        self.calls.append("get_instruments")
        return {"instruments": [{"name": "EUR_USD"}, {"name": "USD_CAD"}]}

    def get_pricing(self):
        self.calls.append("get_pricing")
        return {"prices": [{"instrument": "EUR_USD", "closeoutBid": "1.1"}]}

    def heartbeat(self):
        self.calls.append("heartbeat")
        return {"ok": True}

    def get_account_metadata(self):
        self.calls.append("get_account_metadata")
        return {"account_id": "redacted-test-account", "currency": "CAD"}

    def submit_order(self):
        raise AssertionError("read-only adapter must never call submit_order")


def _env() -> dict[str, str]:
    return {
        "OANDA_API_KEY": "secret-token",
        "OANDA_ACCOUNT_ID": "secret-account",
        "OANDA_BASE_URL": "https://api-fxtrade.oanda.com",
    }


def test_phase154a_oanda_missing_credentials_fail_safely_and_redacted() -> None:
    status = OandaLiveReadOnlyAdapter(env={}).sync()

    assert status["broker"] == "OANDA"
    assert status["credential_status"] == "MISSING"
    assert status["connected"] is False
    assert status["authenticated"] is False
    assert status["execution_enabled"] is False
    assert status["can_live_execute"] is False
    assert status["credential_diagnostics"]["redacted"] is True


def test_phase154a_oanda_read_only_sync_publishes_framework_payload() -> None:
    client = FakeOandaReadClient()
    status = OandaLiveReadOnlyAdapter(
        env=_env(),
        read_client=client,
        now=lambda: datetime(2026, 7, 4, 12, tzinfo=timezone.utc),
    ).sync()

    assert status["selected_broker"] == "OANDA"
    assert status["broker_connected"] is True
    assert status["broker_authenticated"] is True
    assert status["broker_health"] == "GREEN"
    assert status["account_equity"] == 105.0
    assert status["cash"] == 100.0
    assert status["buying_power"] == 90.0
    assert status["products_loaded"] == 2
    assert status["market_data_status"] == "OK"
    assert status["broker_readiness"]["broker_name"] == "OANDA"
    assert status["broker_readiness"]["broker_type"] == "FX"
    assert status["broker_readiness"]["broker_ready"] is True
    assert status["broker_readiness"]["credentials_health"] == "READY"
    assert status["broker_readiness"]["authentication_health"] == "AUTHENTICATED"
    assert status["broker_readiness"]["connection_health"] == "CONNECTED"
    assert status["broker_readiness"]["market_data_health"] == "READY"
    assert status["broker_readiness"]["account_data_health"] == "READY"
    assert status["broker_readiness"]["execution_enabled"] is False
    assert status["execution_allowed"] is False
    assert "submit_order" not in client.calls


def test_phase154a_oanda_adapter_exposes_no_write_methods() -> None:
    public_methods = {
        name
        for name in dir(OandaLiveReadOnlyAdapter)
        if not name.startswith("_") and callable(getattr(OandaLiveReadOnlyAdapter, name))
    }
    forbidden_fragments = ("submit", "modify", "close", "cancel", "market_order", "limit_order", "stop_order", "place")

    assert {"authenticate", "get_account_summary", "get_nav", "get_balance", "get_margin", "get_positions", "get_open_trades", "get_pricing", "get_instruments", "get_server_status", "heartbeat", "get_account_metadata", "connection_status", "sync"} <= public_methods
    assert not any(fragment in method for method in public_methods for fragment in forbidden_fragments)
