from __future__ import annotations

from pathlib import Path

from backend.validation.live_readiness_gate import LiveReadinessGate


def _trade(pnl: float, score: float):
    return {
        "trade_id": f"t-{pnl}",
        "symbol": "AAPL",
        "asset_class": "EQUITY",
        "strategy_id": "alpha",
        "market_regime": "TRENDING",
        "realized_pnl": pnl,
        "entry_price": 100.0,
        "exit_price": 101.0,
        "quantity": 10.0,
        "holding_duration_minutes": 20.0,
        "is_closed": True,
        "quality_score": score,
    }


def test_live_readiness_go(tmp_path: Path) -> None:
    evidence = tmp_path / "artifacts" / "marathon" / "evidence.json"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text("evidence", encoding="utf-8")

    gate = LiveReadinessGate(repository_root=Path.cwd(), evidence_path=evidence, repository_clean_probe=lambda: True, minimum_win_rate=0.5, minimum_profit_factor=1.0, maximum_drawdown=3.0)
    report = gate.evaluate(
        trades=[_trade(10.0, 88.0), _trade(5.0, 72.0), _trade(-2.0, 48.0)],
        calibration_summary={"audit_trail": {"pressure": 0.1}},
        tests_passing=True,
        runtime_healthy=True,
        alerts_operational=True,
        recovery_operational=True,
        learning_operational=True,
        calibration_complete=True,
    )

    assert report.readiness_status == "GO"
    assert report.failed_checks == ()


def test_live_readiness_conditional_go(tmp_path: Path) -> None:
    evidence = tmp_path / "artifacts" / "marathon" / "evidence.json"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text("evidence", encoding="utf-8")

    gate = LiveReadinessGate(repository_root=Path.cwd(), evidence_path=evidence, repository_clean_probe=lambda: True, minimum_win_rate=0.5, minimum_profit_factor=1.0, maximum_drawdown=3.0)
    report = gate.evaluate(
        trades=[_trade(10.0, 88.0), _trade(-1.0, 44.0)],
        calibration_summary={"audit_trail": {"pressure": 0.1}},
        tests_passing=False,
        runtime_healthy=True,
        alerts_operational=True,
        recovery_operational=True,
        learning_operational=True,
        calibration_complete=True,
    )

    assert report.readiness_status == "CONDITIONAL_GO"
    assert "tests_passing" in report.failed_checks


def test_live_readiness_no_go(tmp_path: Path) -> None:
    evidence = tmp_path / "artifacts" / "marathon" / "evidence.json"

    gate = LiveReadinessGate(repository_root=Path.cwd(), evidence_path=evidence, repository_clean_probe=lambda: False)
    report = gate.evaluate(
        trades=[_trade(-10.0, 20.0)],
        calibration_summary={"audit_trail": {"pressure": 0.1}},
        tests_passing=False,
        runtime_healthy=False,
        alerts_operational=False,
        recovery_operational=False,
        learning_operational=False,
        calibration_complete=False,
    )

    assert report.readiness_status == "NO_GO"
    assert "repository_clean" in report.failed_checks
    assert "paper_marathon_evidence_present" in report.failed_checks
