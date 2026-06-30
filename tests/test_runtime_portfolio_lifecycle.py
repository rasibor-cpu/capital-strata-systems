from __future__ import annotations

from pathlib import Path

from backend.runtime.runtime_portfolio_lifecycle import RuntimePortfolioLifecycle


def test_runtime_portfolio_lifecycle_handles_zero_positions_without_broken_status(tmp_path: Path) -> None:
    state = {
        "status": "OK",
        "portfolio_state": "NO_PORTFOLIO",
        "account": {"cash": 100000.0, "equity": 100000.0},
        "positions": [],
        "asset_allocations": {},
        "strategy_metrics": {},
        "market_data": {"market_regime": "RANGING"},
        "staleness": {},
        "reasons": ["no_current_exposure"],
        "advisory_only": True,
        "execution_allowed": False,
    }

    result = RuntimePortfolioLifecycle(tmp_path).refresh(runtime_state=state, persist=False)

    assert result["status"] == "OK"
    assert result["portfolio_state"] == "NO_PORTFOLIO"
    assert result["lifecycle_status"] == "CONNECTED"
    assert result["open_position_count"] == 0
    assert result["execution_allowed"] is False
    assert not (tmp_path / "portfolio" / "runtime_portfolio_lifecycle.json").exists()


def test_runtime_portfolio_lifecycle_publishes_active_snapshot_when_persisting(tmp_path: Path) -> None:
    state = {
        "status": "OK",
        "portfolio_state": "ACTIVE_PORTFOLIO",
        "account": {"cash": 50000.0, "equity": 100000.0, "open_pnl": 100.0, "realized_pnl": 25.0},
        "positions": [{"symbol": "SPY", "asset_class": "EQUITIES", "market_value": 60000.0}],
        "asset_allocations": {"EQUITIES": 100.0},
        "strategy_metrics": {"TREND": {"trade_count": 2, "total_pnl": 25.0}},
        "market_data": {"market_regime": "TRENDING_UP"},
        "staleness": {},
        "reasons": [],
        "advisory_only": True,
        "execution_allowed": False,
    }

    result = RuntimePortfolioLifecycle(tmp_path).refresh(
        runtime_state=state,
        portfolio_decision={"overall_status": "GREEN"},
        validation_summary={"readiness_status": "READY"},
        persist=True,
    )

    assert result["portfolio_state"] == "ACTIVE_PORTFOLIO"
    assert result["open_position_count"] == 1
    assert result["exposure"]["asset_class_exposure"] == {"EQUITIES": 100.0}
    assert (tmp_path / "portfolio" / "runtime_portfolio_lifecycle.json").exists()
    assert (tmp_path / "runtime_portfolio_state.json").exists()
    assert (tmp_path / "portfolio_snapshot.json").exists()


def test_runtime_portfolio_lifecycle_marks_missing_runtime_state_broken(tmp_path: Path) -> None:
    result = RuntimePortfolioLifecycle(tmp_path).refresh(
        runtime_state={"status": "DATA UNAVAILABLE", "reasons": ["account_state_unavailable"], "positions": []},
        persist=False,
    )

    assert result["status"] == "DATA UNAVAILABLE"
    assert result["portfolio_state"] == "BROKEN_PIPELINE"
