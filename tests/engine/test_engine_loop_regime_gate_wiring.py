from __future__ import annotations

from types import SimpleNamespace

from engine.engine_loop import EngineLoop


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
    def __init__(self, decision: str = "ALLOW", reason: str = "ok") -> None:
        self.decision = decision
        self.reason = reason
        self.calls = []

    def __call__(self, inputs):
        self.calls.append(inputs)
        return {"decision": self.decision, "reason": self.reason}


def _loop() -> EngineLoop:
    loop = EngineLoop(starting_equity=1000.0)
    loop.signal_engine = StaticSignalEngine()
    loop.execution_gate = RecordingExecutionGate()
    loop.audit_logger = None
    return loop


def test_regime_gate_allow_permits_execution_gate_path() -> None:
    loop = _loop()
    loop.regime_gate = RecordingRegimeGate("ALLOW", "ok")

    loop.process_bar("EURUSD", 1.10)
    loop.process_bar("EURUSD", 1.11)

    assert len(loop.regime_gate.calls) == 1
    assert len(loop.execution_gate.calls) == 1
    assert loop.regime_gate_blocks == 0
    assert loop.execution_gate.calls[0]["instrument"] == "EURUSD"


def test_regime_gate_block_prevents_execution_gate_call() -> None:
    loop = _loop()
    loop.regime_gate = RecordingRegimeGate("BLOCK", "test_block")

    loop.process_bar("EURUSD", 1.10)
    loop.process_bar("EURUSD", 1.11)

    assert len(loop.regime_gate.calls) == 1
    assert len(loop.execution_gate.calls) == 0
    assert loop.regime_gate_blocks == 1


def test_missing_bars_5m_fails_closed_before_execution_gate() -> None:
    loop = _loop()
    loop._regime_bars_5m = lambda _instrument: None  # type: ignore[method-assign]

    loop.process_bar("EURUSD", 1.10)
    loop.process_bar("EURUSD", 1.11)

    assert len(loop.execution_gate.calls) == 0
    assert loop.regime_gate_blocks == 1


def test_signal_engine_flat_behavior_remains_before_regime_gate() -> None:
    loop = _loop()
    loop.signal_engine = StaticSignalEngine(direction="FLAT", strength=0.0)
    loop.regime_gate = RecordingRegimeGate("BLOCK", "should_not_be_called")

    loop.process_bar("EURUSD", 1.10)
    loop.process_bar("EURUSD", 1.10)

    assert len(loop.regime_gate.calls) == 0
    assert len(loop.execution_gate.calls) == 0
    assert loop.regime_flat_blocks == 1
    assert loop.regime_gate_blocks == 0
