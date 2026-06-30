import os
import time
from pathlib import Path

from backend.runtime.runtime_artifact_freshness import RuntimeArtifactFreshnessManager


def test_artifact_freshness_reports_fresh_aging_and_stale(tmp_path: Path) -> None:
    account = tmp_path / "css_account_state_pcnrass.json"
    portfolio = tmp_path / "runtime_portfolio_state.json"
    validation = tmp_path / "validation_summary.json"
    account.write_text("{}", encoding="utf-8")
    portfolio.write_text("{}", encoding="utf-8")
    validation.write_text("{}", encoding="utf-8")
    now = time.time()
    os.utime(portfolio, (now - 75, now - 75))
    os.utime(validation, (now - 150, now - 150))

    result = RuntimeArtifactFreshnessManager(
        artifacts_dir=tmp_path,
        session_state_path=tmp_path / "session.json",
        supervisor_state_path=tmp_path / "supervisor.json",
        thresholds={"account_state": 100, "runtime_portfolio_state": 100, "validation_summary": 100},
    ).evaluate(runtime_active=False)

    assert result["artifacts"]["account_state"]["status"] == "FRESH"
    assert result["artifacts"]["runtime_portfolio_state"]["status"] == "AGING"
    assert result["artifacts"]["validation_summary"]["status"] == "STALE"
    assert result["artifacts"]["validation_summary"]["freshness_percentage"] == 0.0


def test_artifact_freshness_reports_no_recent_trades_for_missing_active_ledger(tmp_path: Path) -> None:
    ledger = tmp_path / "closed_trades.jsonl"
    ledger.write_text("", encoding="utf-8")
    old = time.time() - 3600
    os.utime(ledger, (old, old))

    result = RuntimeArtifactFreshnessManager(
        artifacts_dir=tmp_path,
        closed_trade_ledger_path=ledger,
    ).evaluate(runtime_active=True)

    assert result["artifacts"]["closed_trade_ledger"]["status"] == "NO_RECENT_TRADES"
    assert "no_recent_closed_trades" in result["warnings"]
