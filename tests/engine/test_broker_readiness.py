from __future__ import annotations

from engine.brokers.broker_readiness import (
    BROKER_BLOCKED,
    BROKER_DEGRADED,
    BROKER_READY,
    certify_broker_readiness,
)


def test_broker_readiness_ready_when_connected_and_safe() -> None:
    report = certify_broker_readiness(
        selected_broker="IBKR",
        broker_mode="paper",
        connected=True,
        live_trading_enabled=False,
        api_health="OK",
        account_readiness="PAPER_READY",
    )

    assert report.status == BROKER_READY
    assert report.reasons == ()
    assert report.as_dict()["status"] == BROKER_READY


def test_broker_readiness_blocks_missing_credentials() -> None:
    report = certify_broker_readiness(
        selected_broker="IBKR",
        broker_mode="live",
        connected=True,
        live_trading_enabled=True,
        missing_credentials=True,
        api_health="OK",
        account_readiness="LIVE_READY",
    )

    assert report.status == BROKER_BLOCKED
    assert "missing_credentials" in report.reasons


def test_broker_readiness_blocks_live_without_live_trading_gate() -> None:
    report = certify_broker_readiness(
        selected_broker="IBKR",
        broker_mode="live",
        connected=True,
        live_trading_enabled=False,
        api_health="OK",
        account_readiness="LIVE_READY",
    )

    assert report.status == BROKER_BLOCKED
    assert "live_trading_not_enabled" in report.reasons


def test_broker_readiness_degrades_connection_or_health_issues() -> None:
    report = certify_broker_readiness(
        selected_broker="IBKR",
        broker_mode="paper",
        connected=False,
        live_trading_enabled=False,
        api_health="DEGRADED",
        account_readiness="PAPER_READY",
    )

    assert report.status == BROKER_DEGRADED
    assert "broker_not_connected" in report.reasons
    assert "api_health_degraded" in report.reasons
