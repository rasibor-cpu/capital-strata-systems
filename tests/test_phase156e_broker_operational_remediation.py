from __future__ import annotations

import json
from pathlib import Path

from backend.runtime.broker_operational_remediation import (
    GREEN,
    PASS,
    RED,
    build_operational_readiness_summary,
    classify_oanda_http_401,
    collect_read_only_authentication_evidence,
    discover_css_health_endpoint,
    write_operational_readiness_summary,
)
from backend.runtime.live_connectivity_certifier import certify_live_connectivity


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
        "broker_execution_armed": False,
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


class _CoinbaseReadOnlyAdapter:
    def get_accounts(self):
        return [{"uuid": "wallet-1", "currency": "BTC"}, {"uuid": "wallet-2", "currency": "ETH"}]

    def get_account_balance(self):
        return {"balance": "1500.00", "equity": "1500.00", "account_count": 2}

    def get_balance(self):
        return self.get_account_balance()

    def get_account(self):
        return self.get_account_balance()

    def get_candles(self, product_id, granularity_name, limit=200):
        assert product_id in {"BTC-USD", "ETH-USD"}
        assert granularity_name == "ONE_MINUTE"
        assert limit == 1
        return [{"ts": 1783512000, "close": "65000.00"}]

    def place_order(self, *_args, **_kwargs):
        raise AssertionError("no execution authority")

    def cancel_order(self, *_args, **_kwargs):
        raise AssertionError("no execution authority")


class _BadHeaderOanda:
    api_key = "redacted"
    account_id = "redacted"
    base_url = "https://api-fxpractice.oanda.com"
    env = "practice"

    def _headers(self):
        return {"Authorization": "redacted"}


def test_phase156e_oanda_401_classifies_practice_live_endpoint_mismatch() -> None:
    report = classify_oanda_http_401(
        env={
            "OANDA_ENV": "practice",
            "OANDA_BASE_URL": "https://api-fxtrade.oanda.com",
            "OANDA_API_KEY": "redacted",
            "OANDA_ACCOUNT_ID": "redacted",
        }
    )

    assert report["status"] == RED
    assert "PRACTICE_ENV_WITH_LIVE_BASE_URL" in report["blockers"]
    assert report["checks"]["endpoint_alignment"] == "MISMATCH"
    assert report["execution_allowed"] is False


def test_phase156e_oanda_401_classifies_account_mismatch_from_response() -> None:
    report = classify_oanda_http_401(
        env={
            "OANDA_ENV": "practice",
            "OANDA_BASE_URL": "https://api-fxpractice.oanda.com",
            "OANDA_API_KEY": "redacted",
            "OANDA_ACCOUNT_ID": "redacted",
        },
        response_payload={"errorMessage": "The specified account is invalid or unauthorized"},
    )

    assert "ACCOUNT_ID_OR_ACCOUNT_PERMISSION_MISMATCH" in report["blockers"]
    assert report["secrets_redacted"] is True


def test_phase156e_oanda_401_classifies_base_url_and_header_format() -> None:
    report = classify_oanda_http_401(adapter=_BadHeaderOanda())

    assert report["checks"]["base_url_present"] is True
    assert "AUTHORIZATION_HEADER_FORMAT_INVALID" in report["blockers"]
    assert report["checks"]["authorization_header_format"] == "INVALID"


def test_phase156e_coinbase_authentication_reuses_read_only_account_evidence() -> None:
    evidence = collect_read_only_authentication_evidence(
        _CoinbaseReadOnlyAdapter(),
        broker="coinbase",
    )

    assert evidence["success"] is True
    assert evidence["source"] == "get_accounts"
    assert evidence["advisory_only"] is True
    assert evidence["broker_execution_armed"] is False


def test_phase156e_phase156b_coinbase_authentication_uses_reused_evidence() -> None:
    report = certify_live_connectivity(
        "coinbase",
        phase156a_fn=_phase156a_green,
        initialize_broker_fn=lambda _broker, _mode: _CoinbaseReadOnlyAdapter(),
        authority_fn=_blocked_authority,
    )

    assert report["authentication"] == PASS
    assert report["account"] == PASS
    assert report["market_data"] == PASS
    assert report["stage_results"]["authentication"]["details"]["source"] == "get_accounts"
    assert report["execution_allowed"] is False
    assert report["live_trading_blocked"] is True
    assert report["broker_execution_armed"] is False


def test_phase156e_health_endpoint_discovery_returns_response_time_and_state() -> None:
    class Response:
        status = 200

    seen = []

    def opener(request, timeout):
        seen.append(request.full_url)
        if request.full_url != "http://127.0.0.1:7777/health":
            raise TimeoutError("not selected")
        return Response()

    report = discover_css_health_endpoint(
        env={"CSS_HEALTH_URL": "http://127.0.0.1:7777/health"},
        timeout_seconds=0.1,
        opener=opener,
    )

    assert seen[0] == "http://127.0.0.1:7777/health"
    assert report["selected_endpoint"] == "http://127.0.0.1:7777/health"
    assert isinstance(report["response_time_ms"], int)
    assert report["health_state"] == GREEN
    assert report["execution_allowed"] is False


def test_phase156e_operational_summary_generation(tmp_path: Path) -> None:
    reports = {
        "oanda_phase156a": {
            "credentials": PASS,
            "bootstrap": PASS,
            "authentication": "FAIL",
            "account": "FAIL",
            "market_data": "FAIL",
            "blocker_reasons": ["account:http_401"],
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
            "advisory_only": True,
        },
        "oanda_phase156b": {
            "authentication": "FAIL",
            "account": "FAIL",
            "market_data": "FAIL",
            "latency": {"overall_ms": 10},
            "blocker_reasons": ["market_data:http_401"],
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
            "advisory_only": True,
        },
        "oanda_phase156c": {
            "health": RED,
            "blocker_reasons": ["connectivity_certification_red"],
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
            "advisory_only": True,
        },
        "coinbase_phase156a": {
            "credentials": PASS,
            "bootstrap": PASS,
            "authentication": PASS,
            "account": PASS,
            "market_data": PASS,
            "blocker_reasons": [],
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
            "advisory_only": True,
        },
        "coinbase_phase156b": {
            "authentication": PASS,
            "account": PASS,
            "market_data": PASS,
            "latency": {"overall_ms": 5},
            "blocker_reasons": [],
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
            "advisory_only": True,
        },
        "coinbase_phase156c": {
            "health": GREEN,
            "blocker_reasons": [],
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
            "advisory_only": True,
        },
    }
    summary = write_operational_readiness_summary(
        broker_reports=reports,
        report_dir=tmp_path,
        health_endpoint={"health_state": GREEN, "selected_endpoint": "http://127.0.0.1:8000/health", "response_time_ms": 1},
    )

    assert summary["recommendation"] == "NO_GO"
    assert summary["brokers"]["OANDA"]["remediation"]["status"] == RED
    assert (tmp_path / "operational_readiness_summary.json").exists()
    assert (tmp_path / "operational_readiness_summary.md").exists()
    saved = json.loads((tmp_path / "operational_readiness_summary.json").read_text(encoding="utf-8"))
    assert saved["execution_allowed"] is False
    assert saved["broker_execution_armed"] is False


def test_phase156e_summary_preserves_advisory_flags() -> None:
    summary = build_operational_readiness_summary(
        broker_reports={},
        health_endpoint={"health_state": RED},
    )

    assert summary["advisory_only"] is True
    assert summary["execution_allowed"] is False
    assert summary["live_trading_blocked"] is True
    assert summary["broker_execution_armed"] is False
