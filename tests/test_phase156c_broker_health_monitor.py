from __future__ import annotations

import json
from datetime import datetime, timezone

from backend.runtime.broker_health_monitor import (
    AMBER,
    DEGRADING,
    GREEN,
    IMPROVING,
    PASS,
    RED,
    STABLE,
    BrokerHealthMonitor,
    BrokerHealthThresholds,
    broker_health_json,
    monitor_broker_health,
    write_broker_health_report,
)


FIXED_NOW = datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc).timestamp()
FRESH_TS = "2026-07-08T12:00:00Z"
STALE_TS = "2026-07-08T11:40:00Z"


def _credential_pass(broker: str, **_kwargs):
    return {
        "broker": broker,
        "broker_name": broker.upper(),
        "credentials_present": True,
        "readiness_status": "READY",
        "failure_reason": "NONE",
        "canonical_failure_reason": "NONE",
        "advisory_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
    }


def _credential_missing(broker: str, **_kwargs):
    return {
        "broker": broker,
        "broker_name": broker.upper(),
        "credentials_present": False,
        "readiness_status": "BLOCKED",
        "failure_reason": "MISSING_CREDENTIALS",
        "canonical_failure_reason": "MISSING_CREDENTIALS",
        "advisory_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
    }


def _connectivity_green(
    broker: str,
    *,
    latency: dict | None = None,
    timestamp: str = FRESH_TS,
    execution_allowed: bool = False,
    live_trading_blocked: bool = True,
    broker_execution_armed: bool = False,
):
    broker_name = broker.upper()
    return {
        "broker": broker_name,
        "phase156a": GREEN,
        "authentication": PASS,
        "account": PASS,
        "market_data": PASS,
        "latency": latency
        or {
            "authentication_ms": 44,
            "account_ms": 58,
            "market_data_ms": 41,
            "overall_ms": 156,
        },
        "connectivity_score": 100.0,
        "execution_allowed": execution_allowed,
        "live_trading_blocked": live_trading_blocked,
        "broker_execution_armed": broker_execution_armed,
        "certification": GREEN,
        "advisory_only": True,
        "blocker_reasons": [],
        "stage_results": {
            "market_data": {
                "status": PASS,
                "details": {
                    "symbols": ["EUR_USD", "USD_JPY"] if broker.lower() == "oanda" else ["BTC-USD", "ETH-USD"],
                    "missing_symbols": [],
                    "timestamp": timestamp,
                },
            },
            "execution_firewall": {
                "status": PASS,
                "details": {
                    "execution_allowed": False,
                    "live_trading_blocked": True,
                    "broker_execution_armed": False,
                },
            },
        },
    }


def _connectivity_red(reason: str):
    return {
        "broker": "OANDA",
        "phase156a": GREEN,
        "authentication": "FAIL",
        "account": "FAIL",
        "market_data": "FAIL",
        "latency": {
            "authentication_ms": None,
            "account_ms": None,
            "market_data_ms": None,
            "overall_ms": 100,
        },
        "connectivity_score": 0.0,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "certification": RED,
        "advisory_only": True,
        "blocker_reasons": [f"authentication:{reason}"],
        "stage_results": {
            "market_data": {
                "status": "FAIL",
                "details": {
                    "missing_symbols": ["EUR_USD"],
                    "timestamp": FRESH_TS,
                },
            }
        },
    }


def _monitor(connectivity_fn, credential_fn=_credential_pass):
    return BrokerHealthMonitor(
        credential_diagnostics_fn=credential_fn,
        connectivity_certifier_fn=connectivity_fn,
        clock=lambda: FIXED_NOW,
    )


def test_phase156c_healthy_broker() -> None:
    report = _monitor(lambda broker, **_kwargs: _connectivity_green(broker)).evaluate_broker("oanda")

    assert report["broker"] == "OANDA"
    assert report["health"] == GREEN
    assert report["overall_score"] >= 98.0
    assert report["availability"] == 100.0
    assert report["reliability"] == 100.0
    assert report["trend"] == STABLE
    assert report["firewall"] == PASS
    assert report["execution_allowed"] is False
    assert report["live_trading_blocked"] is True
    assert report["broker_execution_armed"] is False


def test_phase156c_authentication_failure() -> None:
    report = _monitor(lambda _broker, **_kwargs: _connectivity_red("AUTH_FAILED")).evaluate_broker("oanda")

    assert report["health"] == RED
    assert report["authentication_status"] == "FAIL"
    assert "AUTH_FAILED" in report["api_health"]["failure_reasons"]


def test_phase156c_timeout() -> None:
    report = _monitor(lambda _broker, **_kwargs: _connectivity_red("TIMEOUT")).evaluate_broker("oanda")

    assert report["health"] == RED
    assert "TIMEOUT" in report["api_health"]["failure_reasons"]


def test_phase156c_network_failure() -> None:
    report = _monitor(lambda _broker, **_kwargs: _connectivity_red("NETWORK_ERROR")).evaluate_broker("oanda")

    assert report["health"] == RED
    assert "NETWORK_ERROR" in report["api_health"]["failure_reasons"]


def test_phase156c_dns_failure() -> None:
    report = _monitor(lambda _broker, **_kwargs: _connectivity_red("DNS_ERROR")).evaluate_broker("oanda")

    assert report["health"] == RED
    assert "DNS_ERROR" in report["api_health"]["failure_reasons"]


def test_phase156c_tls_failure() -> None:
    report = _monitor(lambda _broker, **_kwargs: _connectivity_red("TLS_ERROR")).evaluate_broker("oanda")

    assert report["health"] == RED
    assert "TLS_ERROR" in report["api_health"]["failure_reasons"]


def test_phase156c_rate_limit() -> None:
    report = _monitor(lambda _broker, **_kwargs: _connectivity_red("RATE_LIMIT")).evaluate_broker("oanda")

    assert report["health"] == RED
    assert "RATE_LIMIT" in report["api_health"]["failure_reasons"]


def test_phase156c_broker_unavailable() -> None:
    report = _monitor(lambda _broker, **_kwargs: _connectivity_red("BROKER_UNAVAILABLE")).evaluate_broker("oanda")

    assert report["health"] == RED
    assert "BROKER_UNAVAILABLE" in report["api_health"]["failure_reasons"]


def test_phase156c_stale_market_data() -> None:
    report = _monitor(lambda broker, **_kwargs: _connectivity_green(broker, timestamp=STALE_TS)).evaluate_broker("oanda")

    assert report["health"] == RED
    assert report["market_data_freshness"]["status"] == RED
    assert report["market_data_freshness"]["reason"] == "stale_quotes"


def test_phase156c_high_latency_is_amber() -> None:
    report = _monitor(
        lambda broker, **_kwargs: _connectivity_green(
            broker,
            latency={
                "authentication_ms": 700,
                "account_ms": 650,
                "market_data_ms": 680,
                "overall_ms": 2030,
            },
        )
    ).evaluate_broker("oanda")

    assert report["health"] == AMBER
    assert report["latency_health"] == AMBER
    assert report["overall_score"] < 100.0


def test_phase156c_degrading_trend() -> None:
    reports = [_connectivity_green("oanda"), _connectivity_red("TIMEOUT")]

    def certifier(_broker, **_kwargs):
        return reports.pop(0)

    monitor = _monitor(certifier)
    first = monitor.evaluate_broker("oanda")
    second = monitor.evaluate_broker("oanda")

    assert first["health"] == GREEN
    assert second["trend"] == DEGRADING
    assert second["health"] == RED


def test_phase156c_improving_trend_and_reconnect_count() -> None:
    reports = [_connectivity_red("TIMEOUT"), _connectivity_green("oanda")]

    def certifier(_broker, **_kwargs):
        return reports.pop(0)

    monitor = _monitor(certifier)
    first = monitor.evaluate_broker("oanda")
    second = monitor.evaluate_broker("oanda")

    assert first["health"] == RED
    assert second["health"] == GREEN
    assert second["trend"] == IMPROVING
    assert second["reconnect_count"] == 1


def test_phase156c_firewall_verification() -> None:
    report = _monitor(
        lambda broker, **_kwargs: _connectivity_green(
            broker,
            execution_allowed=True,
            live_trading_blocked=False,
            broker_execution_armed=True,
        )
    ).evaluate_broker("oanda")

    assert report["health"] == RED
    assert report["firewall"] == "FAIL"
    assert "firewall_integrity_failed" in report["blocker_reasons"]
    assert report["execution_allowed"] is False
    assert report["live_trading_blocked"] is True
    assert report["broker_execution_armed"] is False


def test_phase156c_json_schema_validation_and_report_write(tmp_path) -> None:
    report = _monitor(lambda broker, **_kwargs: _connectivity_green(broker)).evaluate_broker("coinbase")
    required = {
        "broker",
        "health",
        "overall_score",
        "latency",
        "availability",
        "reliability",
        "trend",
        "firewall",
        "execution_allowed",
        "live_trading_blocked",
        "broker_execution_armed",
        "advisory_only",
        "integration_payloads",
    }
    target = tmp_path / "broker-health.json"

    encoded = broker_health_json(report)
    write_broker_health_report(report, target)

    decoded = json.loads(encoded)
    assert required <= decoded.keys()
    assert decoded["broker"] == "COINBASE"
    assert json.loads(target.read_text(encoding="utf-8"))["advisory_only"] is True


def test_phase156c_advisory_only_enforcement_and_integration_payloads() -> None:
    report = _monitor(lambda broker, **_kwargs: _connectivity_green(broker)).evaluate_broker("oanda")

    assert report["advisory_only"] is True
    assert report["execution_allowed"] is False
    assert report["live_trading_blocked"] is True
    assert report["broker_execution_armed"] is False
    for payload in report["integration_payloads"].values():
        assert payload["advisory_only"] is True
        assert payload["execution_allowed"] is False


def test_phase156c_fail_closed_behaviour_for_missing_credentials_and_exceptions() -> None:
    def certifier_error(_broker, **_kwargs):
        raise RuntimeError("network failure")

    report = monitor_broker_health(
        "oanda",
        credential_diagnostics_fn=_credential_missing,
        connectivity_certifier_fn=certifier_error,
        thresholds=BrokerHealthThresholds(),
    )

    assert report["health"] == RED
    assert report["credential_status"] == "BLOCKED"
    assert report["execution_allowed"] is False
    assert "credentials_unavailable" in report["blocker_reasons"]
