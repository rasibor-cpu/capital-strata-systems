from __future__ import annotations

import json

from backend.portfolio.runtime_portfolio_state_builder import RuntimePortfolioStateBuilder


def _write_runtime_artifacts(tmp_path):
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    account = artifacts / "css_account_state_pcnrass.json"
    session = artifacts / "css_session_state_pcnrass.json"
    supervisor = tmp_path / "supervisor.json"
    trades = artifacts / "trade_outcomes.json"
    account.write_text(
        json.dumps(
            {
                "account_balance": 25000.0,
                "total_equity": 100000.0,
                "positions": [
                    {"symbol": "SPY", "asset_class": "EQUITIES", "market_value": 60000.0},
                    {"symbol": "EUR_USD", "asset_class": "FX", "market_value": 40000.0},
                ],
            }
        ),
        encoding="utf-8",
    )
    session.write_text(
        json.dumps({"session": {"engine_mode": "PAPER", "market_regime": "TRENDING_UP", "risk_status": "GREEN"}}),
        encoding="utf-8",
    )
    supervisor.write_text(json.dumps({"status": "RUNNING", "restart_count": 0}), encoding="utf-8")
    trades.write_text(
        json.dumps(
            [
                {"symbol": "SPY", "asset_class": "EQUITIES", "strategy_id": "trend", "realized_pnl": 120.0},
                {"symbol": "EUR_USD", "asset_class": "FX", "strategy_id": "carry", "realized_pnl": -20.0},
                {"symbol": "QQQ", "asset_class": "EQUITIES", "strategy_id": "trend", "realized_pnl": 80.0},
            ]
        ),
        encoding="utf-8",
    )
    return artifacts, account, session, supervisor


def test_runtime_portfolio_state_builder_populates_runtime_state(tmp_path) -> None:
    artifacts, account, session, supervisor = _write_runtime_artifacts(tmp_path)

    result = RuntimePortfolioStateBuilder(
        artifacts_dir=artifacts,
        account_state_path=account,
        session_state_path=session,
        supervisor_state_path=supervisor,
    ).build()

    assert result["status"] == "OK"
    assert result["account"]["equity"] == 100000.0
    assert len(result["positions"]) == 2
    assert len(result["trades"]) == 3
    assert result["asset_allocations"] == {"EQUITIES": 60.0, "FX": 40.0}
    assert result["performance_metrics"]["capital_efficiency"] == 1.0
    assert result["market_data"]["market_regime"] == "TRENDING_UP"
    assert result["advisory_only"] is True
    assert result["execution_allowed"] is False


def test_runtime_portfolio_state_builder_missing_artifacts_fail_closed(tmp_path) -> None:
    result = RuntimePortfolioStateBuilder(artifacts_dir=tmp_path / "missing").build()

    assert result["status"] == "DATA UNAVAILABLE"
    assert "account_state_missing" in result["reasons"]
    assert "session_state_missing" in result["reasons"]
    assert "positions_unavailable" in result["reasons"]


def test_runtime_portfolio_state_builder_malformed_artifact_fails_closed(tmp_path) -> None:
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    account = artifacts / "css_account_state_pcnrass.json"
    session = artifacts / "css_session_state_pcnrass.json"
    account.write_text("{bad json", encoding="utf-8")
    session.write_text(json.dumps({"session": {"engine_mode": "PAPER"}}), encoding="utf-8")

    result = RuntimePortfolioStateBuilder(
        artifacts_dir=artifacts,
        account_state_path=account,
        session_state_path=session,
    ).build()

    assert result["status"] == "DATA UNAVAILABLE"
    assert "account_state_malformed" in result["reasons"]
    assert result["positions"] == []
