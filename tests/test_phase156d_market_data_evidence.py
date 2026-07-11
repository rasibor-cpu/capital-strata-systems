from __future__ import annotations

import pytest

from backend.runtime.broker_market_data_evidence import (
    PASS,
    collect_market_data_evidence,
    collect_market_data_evidence_for_symbols,
    discover_server_health_endpoints,
)
from backend.runtime.live_broker_validation import GREEN, validate_live_broker
from backend.runtime.live_connectivity_certifier import certify_live_connectivity


def _credential_pass(broker: str, **_kwargs):
    return {
        "broker": broker,
        "broker_name": broker.upper(),
        "credentials_present": True,
        "canonical_failure_reason": "NONE",
        "failure_reason": "NONE",
        "readiness_status": "READY",
        "redacted": True,
        "advisory_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
    }


def _phase156a_green(broker: str, **_kwargs):
    return {
        "broker": broker.upper(),
        "overall": GREEN,
        "credentials": PASS,
        "bootstrap": PASS,
        "authentication": PASS,
        "account": PASS,
        "market_data": PASS,
        "execution_firewall": PASS,
        "advisory_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "blocker_reasons": [],
    }


class _BlockedAuthority:
    def as_dict(self):
        return {
            "execution_authority": False,
            "can_live_execute": False,
            "live_authority_state": "BLOCKED",
        }


def _blocked_authority(_evidence):
    return _BlockedAuthority()


class _ForbiddenExecutionMixin:
    def place_order(self, *_args, **_kwargs):
        raise AssertionError("market-data evidence must never submit orders")

    def cancel_order(self, *_args, **_kwargs):
        raise AssertionError("market-data evidence must never cancel orders")

    def close_position(self, *_args, **_kwargs):
        raise AssertionError("market-data evidence must never mutate broker state")


class _OandaRequestJsonOnly(_ForbiddenExecutionMixin):
    account_id = "redacted-account"

    def authenticate(self):
        return {"ok": True, "status": 200}

    def get_account_summary(self):
        return {
            "ok": True,
            "status": 200,
            "data": {
                "account": {
                    "id": "redacted-account",
                    "alias": "primary",
                    "currency": "USD",
                    "balance": "1000.00",
                    "NAV": "1001.00",
                    "marginAvailable": "900.00",
                }
            },
        }

    def _request_json(self, method, path, payload=None):
        assert payload is None
        assert method == "GET"
        instrument = path.split("instruments=", 1)[1]
        return {
            "ok": True,
            "status": 200,
            "data": {
                "prices": [
                    {
                        "instrument": instrument,
                        "time": "2026-07-08T12:00:00Z",
                        "bids": [{"price": "1.1000"}],
                        "asks": [{"price": "1.1001"}],
                    }
                ]
            },
        }


class _CoinbaseCandlesOnly(_ForbiddenExecutionMixin):
    def authenticate(self):
        return True

    def get_accounts(self):
        return [{"uuid": "wallet-1", "currency": "BTC"}, {"uuid": "wallet-2", "currency": "ETH"}]

    def get_balances(self):
        return {"BTC": {"available": "0.1"}, "ETH": {"available": "1.5"}}

    def get_portfolios(self):
        return [{"uuid": "portfolio-1", "total_value": "1500.00"}]

    def get_candles(self, product_id, granularity_name, limit=200):
        assert product_id in {"BTC-USD", "ETH-USD"}
        assert granularity_name == "ONE_MINUTE"
        assert limit == 1
        return [{"start": 1783512000, "open": "65000.00", "close": "65010.00"}]


class _Clock:
    def __init__(self, values):
        self.values = list(values)
        self.index = 0

    def __call__(self):
        if self.index >= len(self.values):
            return self.values[-1]
        value = self.values[self.index]
        self.index += 1
        return value


@pytest.mark.parametrize(
    ("method_name", "expected_source"),
    [
        ("get_quote", "get_quote"),
        ("get_ticker", "get_ticker"),
        ("get_market_data", "get_market_data"),
        ("get_product", "get_product"),
    ],
)
def test_phase156d_normalizes_public_market_data_methods(method_name: str, expected_source: str) -> None:
    class Adapter:
        def read(self, instrument):
            return {"product_id": instrument, "timestamp": "2026-07-08T12:00:00Z", "price": "100.00"}

    setattr(Adapter, method_name, Adapter.read)

    evidence = collect_market_data_evidence(Adapter(), broker="coinbase", instrument="BTC-USD")

    assert evidence["success"] is True
    assert evidence["source"] == expected_source
    assert evidence["broker"] == "coinbase"
    assert evidence["instrument"] == "BTC-USD"
    assert evidence["advisory_only"] is True
    assert evidence["execution_allowed"] is False
    assert evidence["live_trading_blocked"] is True
    assert evidence["broker_execution_armed"] is False


def test_phase156d_oanda_request_json_pricing_fallback_is_read_only() -> None:
    evidence = collect_market_data_evidence(_OandaRequestJsonOnly(), broker="oanda", instrument="EUR_USD")

    assert evidence["success"] is True
    assert evidence["source"] == "oanda_request_json_pricing"
    assert evidence["timestamp"] == "2026-07-08T12:00:00Z"
    assert evidence["execution_allowed"] is False


def test_phase156d_coinbase_get_candles_is_valid_market_data_evidence() -> None:
    evidence = collect_market_data_evidence(_CoinbaseCandlesOnly(), broker="coinbase", instrument="BTC-USD")

    assert evidence["success"] is True
    assert evidence["source"] == "get_candles"
    assert evidence["timestamp"].endswith("Z")
    assert evidence["advisory_only"] is True


def test_phase156d_missing_market_data_fails_closed() -> None:
    evidence = collect_market_data_evidence(object(), broker="coinbase", instrument="BTC-USD")

    assert evidence["success"] is False
    assert evidence["reason"] == "read_only_method_unavailable"
    assert evidence["execution_allowed"] is False
    assert evidence["live_trading_blocked"] is True
    assert evidence["broker_execution_armed"] is False


def test_phase156d_latency_is_captured_from_injected_clock() -> None:
    class Adapter:
        def get_quote(self, instrument):
            return {"instrument": instrument, "timestamp": "2026-07-08T12:00:00Z"}

    clock = _Clock([10.0, 10.041])

    evidence = collect_market_data_evidence(Adapter(), broker="oanda", instrument="EUR_USD", clock=clock)

    assert evidence["latency_ms"] == 41


def test_phase156d_rejects_explicit_wrong_symbol_evidence() -> None:
    class Adapter:
        def get_pricing(self):
            return {"prices": [{"instrument": "EUR_USD", "time": "2026-07-08T12:00:00Z"}]}

    evidence = collect_market_data_evidence(Adapter(), broker="oanda", instrument="USD_JPY")

    assert evidence["success"] is False
    assert evidence["reason"] == "instrument_mismatch"


def test_phase156d_multi_symbol_payload_reports_missing_symbols() -> None:
    class Adapter:
        def get_ticker(self, instrument):
            if instrument == "ETH-USD":
                return {"ok": False, "error": "missing_market_data"}
            return {"product_id": instrument, "timestamp": "2026-07-08T12:00:00Z"}

    details = collect_market_data_evidence_for_symbols(
        Adapter(),
        broker="coinbase",
        instruments=("BTC-USD", "ETH-USD"),
    )

    assert details["valid"] is False
    assert details["missing_symbols"] == ["ETH-USD"]
    assert details["quotes"]["BTC-USD"]["status"] == PASS
    assert details["evidence"][0]["source"] == "get_ticker"


def test_phase156d_coinbase_multi_symbol_uses_single_products_read() -> None:
    class Adapter:
        def __init__(self):
            self.calls = 0

        def get_products(self):
            self.calls += 1
            return {
                "products": [
                    {"product_id": "BTC-USD", "price": "65000.00"},
                    {"product_id": "ETH-USD", "price": "3500.00"},
                ]
            }

        def get_product(self, _instrument):
            raise AssertionError("single product fallback should not be used")

    adapter = Adapter()
    details = collect_market_data_evidence_for_symbols(
        adapter,
        broker="coinbase",
        instruments=("BTC-USD", "ETH-USD"),
    )

    assert details["valid"] is True
    assert adapter.calls == 1
    assert details["quotes"]["BTC-USD"]["source"] == "get_products"
    assert details["quotes"]["ETH-USD"]["source"] == "get_products"
    assert details["execution_allowed"] is False


def test_phase156d_health_endpoint_discovery_uses_configured_endpoint_first() -> None:
    seen = []

    class Response:
        status = 200

    def opener(request, timeout):
        seen.append((request.full_url, timeout))
        if request.full_url == "http://127.0.0.1:7001/health":
            return Response()
        raise TimeoutError("unreachable")

    report = discover_server_health_endpoints(
        env={"DASHBOARD_HOST": "127.0.0.1", "DASHBOARD_PORT": "7001"},
        timeout_seconds=0.1,
        opener=opener,
    )

    assert seen[0][0] == "http://127.0.0.1:7001/health"
    assert report["any_healthy"] is True
    assert report["selected_endpoint"]["url"] == "http://127.0.0.1:7001/health"
    assert report["execution_allowed"] is False


def test_phase156d_phase156a_coinbase_accepts_candles_only_adapter() -> None:
    report = validate_live_broker(
        "coinbase",
        credential_diagnostics_fn=_credential_pass,
        initialize_broker_fn=lambda _broker, _mode: _CoinbaseCandlesOnly(),
        authority_fn=_blocked_authority,
    )

    assert report["overall"] == GREEN
    assert report["market_data"] == PASS
    assert report["stage_results"]["market_data"]["details"]["source"] == "get_candles"
    assert report["execution_allowed"] is False


def test_phase156d_phase156b_oanda_accepts_request_json_only_adapter() -> None:
    report = certify_live_connectivity(
        "oanda",
        phase156a_fn=_phase156a_green,
        initialize_broker_fn=lambda _broker, _mode: _OandaRequestJsonOnly(),
        authority_fn=_blocked_authority,
    )

    assert report["market_data"] == PASS
    assert report["stage_results"]["market_data"]["details"]["quotes"]["EUR_USD"]["source"] == "oanda_request_json_pricing"
    assert report["stage_results"]["market_data"]["details"]["quotes"]["USD_JPY"]["source"] == "oanda_request_json_pricing"
    assert report["execution_allowed"] is False
    assert report["live_trading_blocked"] is True
    assert report["broker_execution_armed"] is False


def test_phase156d_phase156b_coinbase_accepts_candles_only_adapter() -> None:
    report = certify_live_connectivity(
        "coinbase",
        phase156a_fn=_phase156a_green,
        initialize_broker_fn=lambda _broker, _mode: _CoinbaseCandlesOnly(),
        authority_fn=_blocked_authority,
    )

    assert report["market_data"] == PASS
    assert report["stage_results"]["market_data"]["details"]["quotes"]["BTC-USD"]["source"] == "get_candles"
    assert report["stage_results"]["market_data"]["details"]["quotes"]["ETH-USD"]["source"] == "get_candles"
    assert report["advisory_only"] is True
    assert report["execution_allowed"] is False
    assert report["live_trading_blocked"] is True
    assert report["broker_execution_armed"] is False
