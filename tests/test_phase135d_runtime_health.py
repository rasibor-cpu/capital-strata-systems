from __future__ import annotations

from backend.monitoring.runtime_health_aggregator import RuntimeHealthAggregator


def test_phase135d_runtime_health_green_when_pipeline_connected_and_ledger_idle() -> None:
    result = RuntimeHealthAggregator().aggregate(
        performance={"overall_status": "GREEN"},
        session_validation={"session_status": "GREEN"},
        supervisor_status={"status": "RUNNING"},
        portfolio_decision={"overall_status": "GREEN"},
        runtime_portfolio_state={"status": "OK", "portfolio_state": "NO_PORTFOLIO"},
        artifact_freshness={
            "freshness_status": "GREEN",
            "warnings": ["no_recent_closed_trades"],
            "stale_artifacts": [],
            "refreshed_artifacts": [],
            "artifacts": {
                "closed_trade_ledger": {"freshness": "NO_RECENT_TRADES"},
                "account_state": {"freshness": "FRESH"},
            },
        },
    )

    assert result["runtime_health"] == "GREEN"
    assert result["ledger_freshness"] == "NO_RECENT_TRADES"
    assert "no_recent_closed_trades" in result["warnings"]


def test_phase135d_runtime_health_stale_account_is_amber_not_red() -> None:
    result = RuntimeHealthAggregator().aggregate(
        performance={"overall_status": "GREEN"},
        session_validation={"session_status": "GREEN"},
        supervisor_status={"status": "RUNNING"},
        portfolio_decision={"overall_status": "GREEN"},
        runtime_portfolio_state={"status": "OK", "portfolio_state": "NO_PORTFOLIO"},
        artifact_freshness={
            "freshness_status": "AMBER",
            "warnings": ["stale_account_state"],
            "stale_artifacts": ["account_state"],
            "refreshed_artifacts": [],
            "artifacts": {"account_state": {"freshness": "STALE"}},
        },
    )

    assert result["runtime_health"] == "AMBER"
    assert result["account_state_freshness"] == "STALE"
    assert "stale_account_state" in result["warnings"]
