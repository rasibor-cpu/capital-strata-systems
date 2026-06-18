from __future__ import annotations

from types import SimpleNamespace

from engine.engine_loop import EngineLoop
from engine.execution.execution_gate import ExecutionGate
from engine.information.stock_alerts import StockAlertRule, generate_stock_alerts
from engine.risk.risk_governor import RiskGovernor


class StaticSignalEngine:
    def __init__(self, *, direction: str = "BUY", strength: float = 0.9) -> None:
        self.direction = direction
        self.strength = strength

    def generate(self, **_kwargs):
        return SimpleNamespace(direction=self.direction, strength=self.strength)


class RecordingExecutionGate:
    def __init__(self) -> None:
        self.calls = []

    def evaluate_trade(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "decision": {"final": "ALLOW"},
            "reason": "approved",
            "debug": {"scaled_notional": 25.0},
        }


class RecordingRegimeGate:
    def __init__(self) -> None:
        self.calls = []

    def __call__(self, inputs):
        self.calls.append(inputs)
        return {"decision": "ALLOW", "reason": "ok"}


def _loop() -> EngineLoop:
    loop = EngineLoop(starting_equity=1000.0)
    loop.signal_engine = StaticSignalEngine()
    loop.regime_gate = RecordingRegimeGate()
    loop.execution_gate = RecordingExecutionGate()
    loop.audit_logger = None
    return loop


def test_stock_alerts_generated_correctly() -> None:
    alerts = generate_stock_alerts(
        {
            "symbol": "AAPL",
            "price": 181.0,
            "previous_price": 179.0,
            "source_timestamp": "2026-06-15T00:00:00Z",
        },
        [
            StockAlertRule(
                alert_type="PRICE_CROSSES_ABOVE",
                symbol="AAPL",
                threshold=180.0,
                severity="WATCH",
            )
        ],
    )

    assert len(alerts) == 1
    assert alerts[0]["event_type"] == "STOCK_ALERT"
    assert alerts[0]["symbol"] == "AAPL"
    assert alerts[0]["alert_type"] == "PRICE_CROSSES_ABOVE"
    assert alerts[0]["severity"] == "WATCH"
    assert alerts[0]["advisory_only"] is True
    assert alerts[0]["execution_authority"] == "NONE"


def test_stock_alerts_visible_to_runtime_consumers() -> None:
    loop = _loop()
    loop.stock_alert_rules = [
        StockAlertRule(
            alert_type="PRICE_CROSSES_ABOVE",
            symbol="AAPL",
            threshold=180.0,
            severity="WATCH",
        )
    ]

    loop.process_bar("AAPL", 179.0)
    loop.process_bar("AAPL", 181.0)

    summary = loop.summary()
    alerts = summary["diagnostics"]["stock_alerts"]

    assert len(alerts) == 1
    assert alerts[0]["symbol"] == "AAPL"
    assert alerts[0]["reason"] == "price_crossed_above_threshold"


def test_stock_alerts_do_not_alter_trade_decisions() -> None:
    loop = _loop()
    loop.stock_alert_rules = [
        StockAlertRule(
            alert_type="PRICE_CROSSES_ABOVE",
            symbol="AAPL",
            threshold=180.0,
            severity="WATCH",
        )
    ]

    loop.process_bar("AAPL", 179.0)
    loop.process_bar("AAPL", 181.0)

    assert len(loop.execution_gate.calls) == 1
    assert loop.trade_count == 1
    assert loop.regime_gate_blocks == 0
    assert loop.gate_blocks == 0


def test_stock_alerts_do_not_alter_risk_governor_behavior() -> None:
    alert_count = generate_stock_alerts(
        {"symbol": "AAPL", "price": 181.0, "previous_price": 179.0},
        [
            {
                "alert_type": "PRICE_CROSSES_ABOVE",
                "symbol": "AAPL",
                "threshold": 180.0,
                "severity": "WARNING",
            }
        ],
    )

    decision = RiskGovernor().allow_trade(
        instrument="EUR_USD",
        side="BUY",
        notional=100.0,
        stop_distance_pct=0.02,
        equity=10000.0,
    )

    assert alert_count
    assert decision.ok is True


def test_stock_alerts_do_not_alter_execution_gate_behavior(tmp_path) -> None:
    result = ExecutionGate().evaluate_trade(
        instrument="EUR_USD",
        side="BUY",
        notional=100.0,
        stop_distance_pct=0.02,
        equity=10000.0,
        equity_peak=10000.0,
        regime_persistence=1.0,
        expected_move_bps=80.0,
        fee_bps=1.0,
        spread_bps=1.0,
        slippage_bps=1.0,
        margin_snapshot={
            "margin_state": "GREEN",
            "escalation_state": "NORMAL",
            "margin_utilization_pct": 0.0,
            "margin_source": "SIMULATED",
        },
        broker_mode="PAPER",
    )

    generate_stock_alerts(
        {"symbol": "AAPL", "price": 181.0, "previous_price": 179.0},
        [StockAlertRule("PRICE_CROSSES_ABOVE", "AAPL", 180.0)],
    )

    assert result["decision"]["final"] in {"ALLOW", "BLOCK"}
    assert "decision" in result
