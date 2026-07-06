from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.app.accounting.real_balance_engine import RealBalanceEngine
from backend.runtime.broker_operational_status import (
    CANONICAL_BROKER_OPERATIONAL_STATUS_FIELDS,
    build_broker_operational_status,
)
from backend.runtime.coinbase_live_adapter import CoinbaseLiveReadOnlyAdapter
from backend.runtime.coinbase_live_read_only_operational_validation import (
    validate_coinbase_live_read_only_operational,
)
from backend.runtime.oanda_live_read_only_adapter import OandaLiveReadOnlyAdapter
from backend.runtime.oanda_live_read_only_operational_validation import (
    validate_oanda_live_read_only_operational,
)
from dashboard.runtime.api_bridge import create_app
from dashboard.runtime.dashboard_hydration_coordinator import DashboardHydrationCoordinator
from dashboard.runtime.frontend_contract import build_frontend_payload


class _FakeCoinbaseClient:
    def get_time(self):
        return {"iso": "2026-07-06T01:00:00Z"}

    def get_accounts(self):
        return {"accounts": [{"available_balance": {"value": "100.0", "currency": "USD"}}]}

    def get_portfolios(self):
        return {"portfolios": [{"uuid": "p1"}]}

    def get_products(self):
        return {"products": [{"product_id": "BTC-USD"}]}

    def get_product_ticker(self, product_id: str):
        return {"product_id": product_id, "price": "100000.0"}


class _FakeOandaClient:
    def get_server_status(self):
        return {"time": "2026-07-06T01:00:00Z", "ok": True}

    def heartbeat(self):
        return {"ok": True}

    def get_account_metadata(self):
        return {"account_id": "A1"}

    def get_account_summary(self):
        return {"ok": True, "status": 200, "data": {"account": {"balance": "100.0", "NAV": "100.0"}}}

    def get_margin(self):
        return {"margin_used": 10.0, "margin_available": 90.0}

    def get_instruments(self):
        return {"instruments": [{"name": "EUR_USD"}]}

    def get_pricing(self):
        return {"prices": [{"instrument": "EUR_USD", "closeoutBid": "1.1"}]}

    def get_candles(self, instrument: str = "EUR_USD"):
        return {"candles": [{"time": "2026-07-06T01:00:00Z"}]}


def _coinbase_adapter() -> CoinbaseLiveReadOnlyAdapter:
    return CoinbaseLiveReadOnlyAdapter(
        env={
            "COINBASE_CDP_KEY_NAME": "org/key",
            "COINBASE_CDP_PRIVATE_KEY": "private",
        },
        read_client=_FakeCoinbaseClient(),
        now=lambda: datetime(2026, 7, 6, 1, tzinfo=timezone.utc),
    )


def _oanda_adapter() -> OandaLiveReadOnlyAdapter:
    return OandaLiveReadOnlyAdapter(
        env={
            "OANDA_API_KEY": "key",
            "OANDA_ACCOUNT_ID": "A1",
            "OANDA_BASE_URL": "https://api-fxtrade.oanda.com",
        },
        read_client=_FakeOandaClient(),
        now=lambda: datetime(2026, 7, 6, 1, tzinfo=timezone.utc),
    )


def test_phase155c_canonical_status_fields_exist_for_coinbase_and_oanda() -> None:
    coinbase = validate_coinbase_live_read_only_operational(adapter_factory=_coinbase_adapter)
    oanda = validate_oanda_live_read_only_operational(adapter_factory=_oanda_adapter)

    coinbase_status = coinbase["broker_operational_status"]
    oanda_status = oanda["broker_operational_status"]

    assert set(CANONICAL_BROKER_OPERATIONAL_STATUS_FIELDS) <= set(coinbase_status)
    assert set(CANONICAL_BROKER_OPERATIONAL_STATUS_FIELDS) <= set(oanda_status)


def test_phase155c_endpoint_isolation_coinbase_vs_oanda() -> None:
    coinbase = validate_coinbase_live_read_only_operational(adapter_factory=_coinbase_adapter)
    oanda = validate_oanda_live_read_only_operational(adapter_factory=_oanda_adapter)

    assert coinbase["broker_operational_status"]["endpoint"] == "https://api.coinbase.com"
    assert "oanda" not in coinbase["broker_operational_status"]["endpoint"].lower()

    assert oanda["broker_operational_status"]["endpoint"] == "https://api-fxtrade.oanda.com"
    assert "coinbase" not in oanda["broker_operational_status"]["endpoint"].lower()


def test_phase155c_missing_broker_balance_reports_unknown_drawdown() -> None:
    balance = RealBalanceEngine("COINBASE", None).get_balance()

    assert balance["balance"] is None
    assert balance["equity"] is None
    assert balance["drawdown_status"] == "UNKNOWN"
    assert "unavailable" in str(balance["drawdown_reason"]).lower()


def test_phase155c_live_read_only_margin_status_not_simulated() -> None:
    pending = build_broker_operational_status(
        {
            "broker": "COINBASE",
            "account_sync_status": "PENDING",
            "margin_status": "SIMULATED",
        }
    )
    unavailable = build_broker_operational_status(
        {
            "broker": "OANDA",
            "account_sync_status": "OK",
            "margin_status": "SIMULATED",
        }
    )

    assert pending["margin_status"] == "READ_ONLY_PENDING_ACCOUNT"
    assert unavailable["margin_status"] == "BROKER_UNAVAILABLE"


def test_phase155c_frontend_and_api_expose_broker_operational_status() -> None:
    state = DashboardHydrationCoordinator().hydrate(
        broker_payload={
            "selected_broker": "COINBASE",
            "coinbase_live_validation": {
                "broker_validation": {
                    "validation_status": "PASS",
                    "api_reachable": True,
                    "authentication": True,
                    "account_loaded": True,
                    "balances_loaded": True,
                    "products_loaded": 1,
                    "market_data_loaded": True,
                    "broker_operational_status": {
                        "broker": "COINBASE",
                        "broker_type": "CRYPTO",
                        "mode": "LIVE_READ_ONLY",
                        "endpoint": "https://api.coinbase.com",
                        "api_version": "v3",
                        "server_time": "2026-07-06T01:00:00Z",
                        "latency_ms": None,
                        "rate_limit_status": "UNKNOWN",
                        "last_successful_sync": "2026-07-06T01:00:00+00:00",
                        "last_failed_sync": "NOT_AVAILABLE",
                        "account_sync_status": "OK",
                        "product_count": 1,
                        "market_data_status": "OK",
                        "balance_status": "AVAILABLE",
                        "margin_status": "BROKER_UNAVAILABLE",
                        "operational_state": "OPERATIONAL",
                        "failure_reason": "NONE",
                    },
                },
                "broker_health": {},
                "broker_market_snapshot": {},
            },
            "oanda_live_validation": {
                "broker_validation": {
                    "validation_status": "FAIL_CLOSED",
                    "broker_operational_status": build_broker_operational_status({"broker": "OANDA"}),
                },
                "broker_health": {},
                "broker_market_snapshot": {},
            },
        }
    )

    frontend = build_frontend_payload(state)
    section = frontend["sections"]["broker_operational_status"]

    assert section["selected_broker"] == "COINBASE"
    assert section["selected"]["endpoint"] == "https://api.coinbase.com"
    assert section["coinbase"]["broker"] == "COINBASE"
    assert section["oanda"]["broker"] == "OANDA"

    app = create_app(lambda: state)
    response = TestClient(app).get("/api/v1/broker-operational-status")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["selected_broker"] == "COINBASE"
    assert data["coinbase"]["endpoint"] == "https://api.coinbase.com"
