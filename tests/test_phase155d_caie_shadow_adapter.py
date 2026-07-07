from __future__ import annotations

from copy import deepcopy

from backend.allocation.caie_shadow_adapter import CAIEShadowAdapter
from backend.allocation.opportunity_validator import validate_opportunity_proposal
from backend.runtime.caie_runtime_bridge import CAIERuntimeBridge


def _raw_proposal(
    proposal_id: str,
    *,
    symbol: str = "BTC-USD",
    asset_class: str = "CRYPTO",
    probability: float = 0.75,
    confidence: float = 0.8,
    expected_drawdown_pct: float = 0.2,
    risk_score: float = 35.0,
    requested_capital: float = 1000.0,
) -> dict:
    return {
        "proposal_id": proposal_id,
        "symbol": symbol,
        "asset_class": asset_class,
        "probability": probability,
        "confidence": confidence,
        "expected_drawdown_pct": expected_drawdown_pct,
        "risk_score": risk_score,
        "requested_capital": requested_capital,
    }


def _validated(*items: dict) -> list[dict]:
    out: list[dict] = []
    for item in items:
        result = validate_opportunity_proposal(item)
        assert result["valid"] is True
        out.append(result)
    return out


def _contexts(*proposal_ids: str) -> dict:
    brokers = ["COINBASE", "OANDA", "COINBASE", "OANDA"]
    return {
        pid: {
            "broker": brokers[index % len(brokers)],
            "liquidity_score": 0.8,
            "regime_alignment": 0.7,
        }
        for index, pid in enumerate(proposal_ids)
    }


def test_phase155d_successful_advisory_generation() -> None:
    validated = _validated(
        _raw_proposal("p1", probability=0.82, expected_drawdown_pct=0.2),
        _raw_proposal("p2", probability=0.72, expected_drawdown_pct=0.2),
    )
    bridge = CAIERuntimeBridge()

    result = bridge.run_after_trade_gate(
        trade_gate_completed=True,
        validated_proposals=validated,
        available_capital=3000.0,
        proposal_contexts=_contexts("p1", "p2"),
    )

    assert result["caie_status"] == "AVAILABLE"
    assert len(result["ranked_opportunities"]) == 2
    assert result["execution_action"] == "NO_EXECUTION"


def test_phase155d_empty_proposal_list_returns_safe_empty_advisory() -> None:
    result = CAIERuntimeBridge().run_after_trade_gate(
        trade_gate_completed=True,
        validated_proposals=[],
        available_capital=2500.0,
    )

    assert result["caie_status"] == "NO_OPPORTUNITIES"
    assert result["ranked_opportunities"] == []
    assert result["unused_capital"] == 2500.0


def test_phase155d_invalid_proposal_fails_closed() -> None:
    invalid_validated = [{"valid": False, "normalized": None}]

    result = CAIERuntimeBridge().run_after_trade_gate(
        trade_gate_completed=True,
        validated_proposals=invalid_validated,
        available_capital=1000.0,
    )

    assert result["caie_status"] == "UNAVAILABLE"
    assert result["execution_action"] == "NO_EXECUTION"


def test_phase155d_scoring_failure_fails_closed(monkeypatch) -> None:
    class _FailScore:
        def score(self, *_args, **_kwargs):
            return {"valid": False, "reason": "forced_scoring_failure"}

    adapter = CAIEShadowAdapter(scoring_engine=_FailScore())
    validated = _validated(_raw_proposal("p1"))

    result = adapter.generate_advisory(validated, available_capital=1000.0, proposal_contexts=_contexts("p1"))

    assert result["caie_status"] == "UNAVAILABLE"
    assert result["reason"] == "scoring_unavailable"


def test_phase155d_optimizer_failure_fails_closed() -> None:
    class _FailOptimizer:
        def optimize(self, *_args, **_kwargs):
            return {"valid": False, "reason": "forced_optimizer_failure"}

    adapter = CAIEShadowAdapter(portfolio_optimizer=_FailOptimizer())
    validated = _validated(_raw_proposal("p1"))

    result = adapter.generate_advisory(validated, available_capital=1000.0, proposal_contexts=_contexts("p1"))

    assert result["caie_status"] == "UNAVAILABLE"
    assert result["reason"] == "optimizer_unavailable"


def test_phase155d_runtime_continues_after_caie_exception() -> None:
    class _ExplodingAdapter:
        def generate_advisory(self, *_args, **_kwargs):
            raise RuntimeError("boom")

    bridge = CAIERuntimeBridge(shadow_adapter=_ExplodingAdapter())

    result = bridge.run_after_trade_gate(
        trade_gate_completed=True,
        validated_proposals=_validated(_raw_proposal("p1")),
        available_capital=1000.0,
        proposal_contexts=_contexts("p1"),
    )

    assert result["caie_status"] == "UNAVAILABLE"
    assert result["execution_action"] == "NO_EXECUTION"


def test_phase155d_deterministic_advisory_output() -> None:
    validated = _validated(
        _raw_proposal("p1", probability=0.81),
        _raw_proposal("p2", probability=0.76),
    )
    contexts = _contexts("p1", "p2")
    bridge = CAIERuntimeBridge()

    first = bridge.run_after_trade_gate(
        trade_gate_completed=True,
        validated_proposals=validated,
        available_capital=2500.0,
        proposal_contexts=contexts,
    )
    second = bridge.run_after_trade_gate(
        trade_gate_completed=True,
        validated_proposals=deepcopy(validated),
        available_capital=2500.0,
        proposal_contexts=deepcopy(contexts),
        runtime_timestamp=first["runtime_timestamp"],
    )

    assert first == second


def test_phase155d_no_execution_authorization() -> None:
    result = CAIERuntimeBridge().run_after_trade_gate(
        trade_gate_completed=False,
        validated_proposals=None,
        available_capital=1000.0,
    )

    assert result["advisory_only"] is True
    assert result["shadow_mode"] is True
    assert result["execution_action"] == "NO_EXECUTION"


def test_phase155d_no_runtime_crash_with_missing_data() -> None:
    bridge = CAIERuntimeBridge()
    result = bridge.run_after_trade_gate(
        trade_gate_completed=True,
        validated_proposals=None,
        available_capital=1000.0,
    )

    assert result["caie_status"] == "UNAVAILABLE"
    assert result["execution_action"] == "NO_EXECUTION"
