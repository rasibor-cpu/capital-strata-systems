from __future__ import annotations

import json

from backend.runtime.live_connectivity_certifier import (
    AMBER,
    GREEN,
    PASS,
    RED,
    ConnectivityLatencyThresholds,
    LiveConnectivityCertificationEngine,
    certify_live_connectivity,
    live_connectivity_certification_json,
    write_live_connectivity_certification_report,
)


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


def _phase156a_red(_broker: str, **_kwargs):
    return {
        "overall": RED,
        "credentials": "FAIL",
        "bootstrap": "FAIL",
        "execution_firewall": PASS,
        "advisory_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "blocker_reasons": ["credentials:MISSING_CREDENTIALS"],
    }


class _BlockedAuthority:
    def as_dict(self):
        return {
            "execution_authority": False,
            "can_live_execute": False,
            "live_authority_state": "BLOCKED",
        }


class _AuthorizedAuthority:
    def as_dict(self):
        return {
            "execution_authority": True,
            "can_live_execute": True,
            "live_authority_state": "AUTHORIZED",
        }


def _blocked_authority(_evidence):
    return _BlockedAuthority()


def _authorized_authority(_evidence):
    return _AuthorizedAuthority()


class _ForbiddenExecutionMixin:
    execution_calls = 0

    def place_order(self, *_args, **_kwargs):
        self.execution_calls += 1
        raise AssertionError("certifier must never submit orders")

    def cancel_order(self, *_args, **_kwargs):
        self.execution_calls += 1
        raise AssertionError("certifier must never cancel orders")

    def close_position(self, *_args, **_kwargs):
        self.execution_calls += 1
        raise AssertionError("certifier must never modify broker state")


class _OandaAdapter(_ForbiddenExecutionMixin):
    def authenticate(self):
        return {"ok": True, "status": 200}

    def get_account_summary(self):
        return {
            "ok": True,
            "status": 200,
            "data": {
                "account": {
                    "id": "OANDA-001",
                    "alias": "primary-fx",
                    "currency": "USD",
                    "balance": "1000.00",
                    "NAV": "1004.25",
                    "marginAvailable": "920.00",
                }
            },
        }

    def get_quote(self, symbol):
        if symbol not in {"EUR_USD", "USD_JPY"}:
            return {"ok": False, "error": "unsupported_symbol"}
        return {
            "ok": True,
            "status": 200,
            "instrument": symbol,
            "bid": "1.1000",
            "ask": "1.1001",
            "timestamp": "2026-07-08T12:00:00Z",
        }


class _CoinbaseAdapter(_ForbiddenExecutionMixin):
    def authenticate(self):
        return True

    def get_portfolios(self):
        return [{"uuid": "portfolio-1", "name": "default", "total_value": "1500.00"}]

    def get_accounts(self):
        return [{"uuid": "wallet-1", "currency": "BTC"}, {"uuid": "wallet-2", "currency": "ETH"}]

    def get_balances(self):
        return {"BTC": {"available": "0.1"}, "ETH": {"available": "1.5"}}

    def get_ticker(self, symbol):
        if symbol not in {"BTC-USD", "ETH-USD"}:
            return {"ok": False, "error": "unsupported_symbol"}
        return {
            "product_id": symbol,
            "price": "65000.00",
            "timestamp": "2026-07-08T12:00:00Z",
        }


def _init_oanda(_broker, _mode):
    return _OandaAdapter()


def _init_coinbase(_broker, _mode):
    return _CoinbaseAdapter()


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


def test_phase156b_missing_credentials_fails_closed_at_phase156a() -> None:
    bootstrap_called = False

    def init(_broker, _mode):
        nonlocal bootstrap_called
        bootstrap_called = True
        return _OandaAdapter()

    report = certify_live_connectivity(
        "oanda",
        phase156a_fn=_phase156a_red,
        initialize_broker_fn=init,
        authority_fn=_blocked_authority,
    )

    assert report["certification"] == RED
    assert report["phase156a"] == RED
    assert report["connectivity_score"] == 0.0
    assert report["execution_allowed"] is False
    assert bootstrap_called is False


def test_phase156b_bootstrap_failure_fails_closed() -> None:
    def init(_broker, _mode):
        raise RuntimeError("bootstrap unavailable")

    report = certify_live_connectivity(
        "oanda",
        phase156a_fn=_phase156a_green,
        initialize_broker_fn=init,
        authority_fn=_blocked_authority,
    )

    assert report["certification"] == RED
    assert "bootstrap:BROKER_UNAVAILABLE" in report["blocker_reasons"]
    assert report["live_trading_blocked"] is True


def test_phase156b_authentication_failure_is_blocked() -> None:
    class AuthFail(_OandaAdapter):
        def authenticate(self):
            return {"ok": False, "error": "auth_failed"}
        def get_account_summary(self):
            return {"ok": False, "error": "auth_failed"}
        def get_account_details(self):
            return {"ok": False, "error": "auth_failed"}

    report = certify_live_connectivity(
        "oanda",
        phase156a_fn=_phase156a_green,
        initialize_broker_fn=lambda _broker, _mode: AuthFail(),
        authority_fn=_blocked_authority,
    )

    assert report["certification"] == RED
    assert report["authentication"] == "FAIL"
    assert "authentication:auth_failed" in report["blocker_reasons"]


def test_phase156b_broker_unavailable_fails_closed() -> None:
    class Unavailable(_OandaAdapter):
        def authenticate(self):
            raise RuntimeError("broker unavailable")
        def get_account_summary(self):
            raise RuntimeError("broker unavailable")
        def get_account_details(self):
            raise RuntimeError("broker unavailable")

    report = certify_live_connectivity(
        "oanda",
        phase156a_fn=_phase156a_green,
        initialize_broker_fn=lambda _broker, _mode: Unavailable(),
        authority_fn=_blocked_authority,
    )

    assert report["certification"] == RED
    assert "authentication:BROKER_UNAVAILABLE" in report["blocker_reasons"]


def test_phase156b_timeout_fails_closed() -> None:
    class TimeoutMarket(_OandaAdapter):
        def get_quote(self, symbol):
            if symbol == "USD_JPY":
                raise TimeoutError("broker timed out")
            return super().get_quote(symbol)

    report = certify_live_connectivity(
        "oanda",
        phase156a_fn=_phase156a_green,
        initialize_broker_fn=lambda _broker, _mode: TimeoutMarket(),
        authority_fn=_blocked_authority,
    )

    assert report["certification"] == RED
    assert report["market_data"] == "FAIL"
    assert "market_data:TIMEOUT" in report["blocker_reasons"]


def test_phase156b_slow_broker_latency_is_amber() -> None:
    clock = _Clock([0.0, 0.0, 0.30, 0.30, 0.65, 0.65, 0.95, 0.95])
    engine = LiveConnectivityCertificationEngine(
        "oanda",
        phase156a_fn=_phase156a_green,
        initialize_broker_fn=_init_oanda,
        authority_fn=_blocked_authority,
        thresholds=ConnectivityLatencyThresholds(
            stage_green_ms=250,
            stage_amber_ms=1000,
            overall_green_ms=750,
            overall_amber_ms=2500,
        ),
        clock=clock,
    )

    report = engine.certify()

    assert report["certification"] == AMBER
    assert report["latency_status"] == AMBER
    assert report["latency"]["authentication_ms"] == 300
    assert report["latency"]["overall_ms"] == 950


def test_phase156b_missing_market_data_is_red() -> None:
    class MissingEth(_CoinbaseAdapter):
        def get_ticker(self, symbol):
            if symbol == "ETH-USD":
                return {"ok": False, "error": "missing_market_data"}
            return super().get_ticker(symbol)

    report = certify_live_connectivity(
        "coinbase",
        phase156a_fn=_phase156a_green,
        initialize_broker_fn=lambda _broker, _mode: MissingEth(),
        authority_fn=_blocked_authority,
    )

    assert report["certification"] == RED
    assert report["market_data"] == "FAIL"
    assert report["stage_results"]["market_data"]["details"]["missing_symbols"] == ["ETH-USD"]


def test_phase156b_missing_balances_is_red() -> None:
    class MissingBalances(_CoinbaseAdapter):
        def get_balances(self):
            return {}

    report = certify_live_connectivity(
        "coinbase",
        phase156a_fn=_phase156a_green,
        initialize_broker_fn=lambda _broker, _mode: MissingBalances(),
        authority_fn=_blocked_authority,
    )

    assert report["certification"] == RED
    assert report["account"] == "FAIL"
    assert "asset_balances" in report["stage_results"]["account"]["details"]["missing_fields"]


def test_phase156b_successful_oanda_certification() -> None:
    report = certify_live_connectivity(
        "OANDA",
        phase156a_fn=_phase156a_green,
        initialize_broker_fn=_init_oanda,
        authority_fn=_blocked_authority,
    )

    assert report["broker"] == "OANDA"
    assert report["phase156a"] == GREEN
    assert report["authentication"] == PASS
    assert report["account"] == PASS
    assert report["market_data"] == PASS
    assert report["certification"] == GREEN
    assert report["connectivity_score"] == 100.0
    assert report["execution_allowed"] is False
    assert report["broker_execution_armed"] is False
    assert report["stage_results"]["market_data"]["details"]["symbols"] == ["EUR_USD", "USD_JPY"]


def test_phase156b_successful_coinbase_certification() -> None:
    report = certify_live_connectivity(
        "coinbase",
        phase156a_fn=_phase156a_green,
        initialize_broker_fn=_init_coinbase,
        authority_fn=_blocked_authority,
    )

    assert report["broker"] == "COINBASE"
    assert report["certification"] == GREEN
    assert report["account"] == PASS
    assert report["market_data"] == PASS
    assert report["stage_results"]["account"]["details"]["portfolio_value_present"] is True
    assert report["stage_results"]["market_data"]["details"]["symbols"] == ["BTC-USD", "ETH-USD"]


def test_phase156b_coinbase_portfolio_value_can_come_from_balances() -> None:
    class PortfolioMetadataOnly(_CoinbaseAdapter):
        def get_portfolios(self):
            return {"portfolios": [{"uuid": "portfolio-1", "name": "default"}]}

        def get_balances(self):
            return {"accounts": [{"currency": "USD", "available_balance": {"value": "1500.00"}}]}

    report = certify_live_connectivity(
        "coinbase",
        phase156a_fn=_phase156a_green,
        initialize_broker_fn=lambda _broker, _mode: PortfolioMetadataOnly(),
        authority_fn=_blocked_authority,
    )

    assert report["account"] == PASS
    assert report["stage_results"]["account"]["details"]["portfolio_value_present"] is True


def test_phase156b_execution_firewall_validation_fails_if_authority_granted() -> None:
    report = certify_live_connectivity(
        "oanda",
        phase156a_fn=_phase156a_green,
        initialize_broker_fn=_init_oanda,
        authority_fn=_authorized_authority,
    )

    assert report["certification"] == RED
    assert report["stage_results"]["execution_firewall"]["status"] == "FAIL"
    assert "execution_firewall:execution_firewall_not_blocked" in report["blocker_reasons"]
    assert report["execution_allowed"] is False
    assert report["broker_execution_armed"] is False


def test_phase156b_phase156a_exception_fails_closed() -> None:
    def phase156a_error(_broker, **_kwargs):
        raise RuntimeError("phase156a failure")

    report = certify_live_connectivity(
        "coinbase",
        phase156a_fn=phase156a_error,
        initialize_broker_fn=lambda _broker, _mode: (_ for _ in ()).throw(AssertionError("must not bootstrap")),
        authority_fn=_blocked_authority,
    )

    assert report["certification"] == RED
    assert report["phase156a"] == RED
    assert report["execution_allowed"] is False
    assert report["live_trading_blocked"] is True


def test_phase156b_json_schema_validation_and_report_write(tmp_path) -> None:
    report = certify_live_connectivity(
        "oanda",
        phase156a_fn=_phase156a_green,
        initialize_broker_fn=_init_oanda,
        authority_fn=_blocked_authority,
    )
    required_keys = {
        "broker",
        "phase156a",
        "authentication",
        "account",
        "market_data",
        "latency",
        "connectivity_score",
        "execution_allowed",
        "live_trading_blocked",
        "broker_execution_armed",
        "certification",
        "advisory_only",
    }
    target = tmp_path / "phase156b.json"

    encoded = live_connectivity_certification_json(report)
    write_live_connectivity_certification_report(report, target)

    decoded = json.loads(encoded)
    assert required_keys <= decoded.keys()
    assert isinstance(decoded["latency"]["overall_ms"], int)
    assert isinstance(decoded["connectivity_score"], float)
    assert json.loads(target.read_text(encoding="utf-8"))["certification"] == GREEN


def test_phase156b_no_execution_authority_or_broker_mutation() -> None:
    adapter = _OandaAdapter()
    report = certify_live_connectivity(
        "oanda",
        phase156a_fn=_phase156a_green,
        initialize_broker_fn=lambda _broker, _mode: adapter,
        authority_fn=_blocked_authority,
    )

    assert report["certification"] == GREEN
    assert report["execution_allowed"] is False
    assert report["live_trading_blocked"] is True
    assert report["broker_execution_armed"] is False
    assert adapter.execution_calls == 0


def test_phase156b_oanda_degraded_operational_latency_is_amber() -> None:
    # Set high latency values exceeding strict GREEN thresholds, but within degraded AMBER limits:
    # account_ms = 1050 ms, market_data_ms = 2050 ms, overall_ms = 5600 ms.
    clock = _Clock([0.0, 0.0, 1.05, 1.05, 3.10, 3.10, 5.60, 5.60])
    engine = LiveConnectivityCertificationEngine(
        "oanda",
        phase156a_fn=_phase156a_green,
        initialize_broker_fn=_init_oanda,
        authority_fn=_blocked_authority,
        thresholds=ConnectivityLatencyThresholds(
            stage_green_ms=250,
            stage_amber_ms=1000,
            overall_green_ms=750,
            overall_amber_ms=2500,
        ),
        clock=clock,
    )

    report = engine.certify()

    assert report["certification"] == AMBER
    assert report["latency_status"] == AMBER
    assert report["connectivity_score"] >= 85.0
    assert "Broker is operational but latency is elevated; continue read-only monitoring before live validation." in report["recommendations"]


def test_phase156b_observed_degraded_live_latency_remains_amber_not_green() -> None:
    clock = _Clock([0.0, 0.0, 2.4, 2.4, 6.2, 6.2, 8.8, 8.8])
    engine = LiveConnectivityCertificationEngine(
        "coinbase",
        phase156a_fn=_phase156a_green,
        initialize_broker_fn=_init_coinbase,
        authority_fn=_blocked_authority,
        clock=clock,
    )

    report = engine.certify()

    assert report["certification"] == AMBER
    assert report["latency_status"] == AMBER
    assert report["latency"]["active_validation_ms"] == 8800
    assert report["latency"]["account_ms"] == 3800
