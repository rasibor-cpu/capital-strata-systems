from engine.execution.execution_gate import ExecutionGate


class CapturingAntiBleed:
    def __init__(self):
        self.kwargs = None

    def evaluate(self, **kwargs):
        self.kwargs = kwargs
        return {"approved": False, "reason": "trade_size_too_small"}


def test_pilot_exception_requires_explicit_cad_currency():
    gate = ExecutionGate(anti_bleed_guard=CapturingAntiBleed())
    decision = gate._evaluate_anti_bleed(
        instrument="ABC",
        side="BUY",
        notional=5,
        expected_move_bps=100,
        fee_bps=1,
        spread_bps=1,
        slippage_bps=1,
        notional_currency="USD",
        pilot_min_size_exception=object(),
    )
    assert not decision["approved"]
    assert decision["reason"] == "pilot_min_size_currency_not_cad"


def test_cad_pilot_exception_is_forwarded_to_antibleed_without_enabling_it():
    guard = CapturingAntiBleed()
    gate = ExecutionGate(anti_bleed_guard=guard)
    marker = object()
    decision = gate._evaluate_anti_bleed(
        instrument="ABC",
        side="BUY",
        notional=5,
        expected_move_bps=100,
        fee_bps=1,
        spread_bps=1,
        slippage_bps=1,
        notional_currency="CAD",
        pilot_min_size_exception=marker,
    )
    assert not decision["approved"]
    assert guard.kwargs["pilot_min_size_exception"] is marker
    assert guard.kwargs["trade_size"] == 5.0


def test_ordinary_antibleed_path_does_not_require_currency():
    guard = CapturingAntiBleed()
    gate = ExecutionGate(anti_bleed_guard=guard)
    gate._evaluate_anti_bleed(
        instrument="ABC",
        side="BUY",
        notional=100,
        expected_move_bps=100,
        fee_bps=1,
        spread_bps=1,
        slippage_bps=1,
    )
    assert guard.kwargs["pilot_min_size_exception"] is None
