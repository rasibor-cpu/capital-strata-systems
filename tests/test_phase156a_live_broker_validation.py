from __future__ import annotations

import json

from backend.runtime.live_broker_validation import (
    GREEN,
    PASS,
    RED,
    LiveBrokerValidationEngine,
    live_broker_validation_json,
    validate_live_broker,
    write_live_broker_validation_report,
)


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


def _missing_credentials(broker: str, **_kwargs):
    return {
        "broker": broker,
        "broker_name": broker.upper(),
        "credentials_present": False,
        "canonical_failure_reason": "MISSING_CREDENTIALS",
        "failure_reason": "MISSING_CREDENTIALS",
        "readiness_status": "BLOCKED",
        "missing_credential_fields": ["TOKEN"],
        "redacted": True,
        "advisory_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
    }


def _invalid_credentials(broker: str, **_kwargs):
    return {
        "broker": broker,
        "broker_name": broker.upper(),
        "credentials_present": True,
        "canonical_failure_reason": "TOKEN_INVALID",
        "failure_reason": "TOKEN_INVALID",
        "readiness_status": "BLOCKED",
        "redacted": True,
        "advisory_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
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


class _ExecutionForbiddenMixin:
    def place_order(self, *_args, **_kwargs):
        raise AssertionError("validator must never submit orders")

    def cancel_order(self, *_args, **_kwargs):
        raise AssertionError("validator must never cancel orders")

    def close_position(self, *_args, **_kwargs):
        raise AssertionError("validator must never mutate broker state")


class _GoodOandaAdapter(_ExecutionForbiddenMixin):
    def authenticate(self):
        return {"ok": True, "status": 200}

    def get_account_summary(self):
        return {
            "ok": True,
            "status": 200,
            "data": {
                "account": {
                    "balance": "1000.00",
                    "NAV": "1005.00",
                    "marginAvailable": "900.00",
                }
            },
        }

    def get_quote(self, instrument):
        assert instrument == "EUR_USD"
        return {"ok": True, "status": 200, "prices": [{"instrument": instrument}]}


class _GoodCoinbaseAdapter(_ExecutionForbiddenMixin):
    def authenticate(self):
        return True

    def get_accounts(self):
        return [{"uuid": "account-1"}]

    def get_balances(self):
        return {"BTC": {"available": "0.1"}}

    def get_portfolios(self):
        return [{"name": "default"}]

    def get_ticker(self, product_id):
        assert product_id == "BTC-USD"
        return {"price": "65000.00", "product_id": product_id}


def _init_oanda(_broker, _mode):
    return _GoodOandaAdapter()


def _init_coinbase(_broker, _mode):
    return _GoodCoinbaseAdapter()


def test_phase156a_missing_credentials_fails_closed_without_bootstrap() -> None:
    bootstrap_called = False

    def init(_broker, _mode):
        nonlocal bootstrap_called
        bootstrap_called = True
        return _GoodOandaAdapter()

    report = validate_live_broker(
        "oanda",
        credential_diagnostics_fn=_missing_credentials,
        initialize_broker_fn=init,
        authority_fn=_blocked_authority,
    )

    assert report["overall"] == RED
    assert report["credentials"] == "FAIL"
    assert report["bootstrap"] == "FAIL"
    assert report["execution_allowed"] is False
    assert report["live_trading_blocked"] is True
    assert bootstrap_called is False


def test_phase156a_invalid_credentials_fail_before_broker_contact() -> None:
    report = validate_live_broker(
        "oanda",
        credential_diagnostics_fn=_invalid_credentials,
        initialize_broker_fn=lambda _broker, _mode: (_ for _ in ()).throw(AssertionError("must not bootstrap")),
        authority_fn=_blocked_authority,
    )

    assert report["overall"] == RED
    assert report["credentials"] == "FAIL"
    assert "credentials:TOKEN_INVALID" in report["blocker_reasons"]


def test_phase156a_authentication_failure_is_reported() -> None:
    class AuthFailOanda(_GoodOandaAdapter):
        def authenticate(self):
            return {"ok": False, "error": "auth_failed"}

    report = validate_live_broker(
        "oanda",
        credential_diagnostics_fn=_credential_pass,
        initialize_broker_fn=lambda _broker, _mode: AuthFailOanda(),
        authority_fn=_blocked_authority,
    )

    assert report["overall"] == RED
    assert report["bootstrap"] == PASS
    assert report["authentication"] == "FAIL"
    assert "authentication:auth_failed" in report["blocker_reasons"]


def test_phase156a_broker_unavailable_fails_closed() -> None:
    def unavailable(_broker, _mode):
        raise RuntimeError("broker unavailable")

    report = validate_live_broker(
        "coinbase",
        credential_diagnostics_fn=_credential_pass,
        initialize_broker_fn=unavailable,
        authority_fn=_blocked_authority,
    )

    assert report["overall"] == RED
    assert report["bootstrap"] == "FAIL"
    assert "bootstrap:BROKER_UNAVAILABLE" in report["blocker_reasons"]


def test_phase156a_timeout_fails_closed() -> None:
    class TimeoutOanda(_GoodOandaAdapter):
        def get_quote(self, instrument):
            raise TimeoutError("market data timed out")

    report = validate_live_broker(
        "oanda",
        credential_diagnostics_fn=_credential_pass,
        initialize_broker_fn=lambda _broker, _mode: TimeoutOanda(),
        authority_fn=_blocked_authority,
    )

    assert report["overall"] == RED
    assert report["market_data"] == "FAIL"
    assert "market_data:TIMEOUT" in report["blocker_reasons"]


def test_phase156a_successful_oanda_validation_is_green_but_advisory_only() -> None:
    report = validate_live_broker(
        "OANDA",
        credential_diagnostics_fn=_credential_pass,
        initialize_broker_fn=_init_oanda,
        authority_fn=_blocked_authority,
    )

    assert report["broker"] == "OANDA"
    assert report["overall"] == GREEN
    assert report["credentials"] == PASS
    assert report["bootstrap"] == PASS
    assert report["authentication"] == PASS
    assert report["account"] == PASS
    assert report["market_data"] == PASS
    assert report["execution_firewall"] == PASS
    assert report["advisory_only"] is True
    assert report["execution_allowed"] is False
    assert report["live_trading_blocked"] is True
    assert report["stage_results"]["account"]["details"]["balance_present"] is True
    assert report["stage_results"]["account"]["details"]["nav_present"] is True
    assert report["stage_results"]["account"]["details"]["margin_available_present"] is True


def test_phase156a_successful_coinbase_validation_is_green() -> None:
    report = validate_live_broker(
        "coinbase",
        credential_diagnostics_fn=_credential_pass,
        initialize_broker_fn=_init_coinbase,
        authority_fn=_blocked_authority,
    )

    assert report["broker"] == "COINBASE"
    assert report["overall"] == GREEN
    assert report["account"] == PASS
    assert report["market_data"] == PASS
    assert report["stage_results"]["account"]["details"]["accounts_present"] is True
    assert report["stage_results"]["account"]["details"]["balances_present"] is True
    assert report["stage_results"]["account"]["details"]["portfolio_present"] is True
    assert report["stage_results"]["market_data"]["details"]["instrument"] == "BTC-USD"


def test_phase156a_execution_firewall_validation_blocks_authority() -> None:
    report = validate_live_broker(
        "oanda",
        credential_diagnostics_fn=_credential_pass,
        initialize_broker_fn=_init_oanda,
        authority_fn=_authorized_authority,
    )

    assert report["overall"] == RED
    assert report["execution_firewall"] == "FAIL"
    assert "execution_firewall:execution_firewall_not_blocked" in report["blocker_reasons"]


def test_phase156a_advisory_only_enforcement_on_green_report() -> None:
    report = validate_live_broker(
        "coinbase",
        credential_diagnostics_fn=_credential_pass,
        initialize_broker_fn=_init_coinbase,
        authority_fn=_blocked_authority,
    )

    assert report["overall"] == GREEN
    assert report["advisory_only"] is True
    assert report["execution_allowed"] is False
    assert report["live_trading_blocked"] is True


def test_phase156a_json_report_generation(tmp_path) -> None:
    report = validate_live_broker(
        "oanda",
        credential_diagnostics_fn=_credential_pass,
        initialize_broker_fn=_init_oanda,
        authority_fn=_blocked_authority,
    )
    encoded = live_broker_validation_json(report)
    target = tmp_path / "phase156a_report.json"

    write_live_broker_validation_report(report, target)

    assert json.loads(encoded)["overall"] == GREEN
    assert json.loads(target.read_text(encoding="utf-8"))["execution_allowed"] is False


def test_phase156a_engine_write_json_report(tmp_path) -> None:
    engine = LiveBrokerValidationEngine(
        "coinbase",
        credential_diagnostics_fn=_credential_pass,
        initialize_broker_fn=_init_coinbase,
        authority_fn=_blocked_authority,
    )
    target = tmp_path / "engine-report.json"

    report = engine.write_json_report(target)

    assert report["overall"] == GREEN
    assert json.loads(target.read_text(encoding="utf-8"))["broker"] == "COINBASE"


def test_phase156a_diagnostic_exception_fails_closed() -> None:
    def diagnostic_error(_broker, **_kwargs):
        raise RuntimeError("diagnostic failure")

    report = validate_live_broker(
        "oanda",
        credential_diagnostics_fn=diagnostic_error,
        initialize_broker_fn=lambda _broker, _mode: (_ for _ in ()).throw(AssertionError("must not bootstrap")),
        authority_fn=_blocked_authority,
    )

    assert report["overall"] == RED
    assert report["credentials"] == "FAIL"
    assert report["bootstrap"] == "FAIL"
    assert report["advisory_only"] is True
    assert report["execution_allowed"] is False
