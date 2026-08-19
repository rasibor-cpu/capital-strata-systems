from __future__ import annotations

import ast
import inspect
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

import pytest

from backend.intelligence.technical_intelligence import TECHNICAL_INTELLIGENCE_VERSION
from backend.intelligence import technical_intelligence as tai_module
from backend.trading.autonomous_opportunity_intelligence_engine import (
    AutonomousOpportunityIntelligenceEngine,
)
from backend.trading import autonomous_opportunity_intelligence_engine as aoi_module
from backend.trading.opportunity_ranking_engine import OpportunityRankingEngine
from backend.trading import opportunity_ranking_engine as ranking_module
from dashboard.mission_control.opportunity_ranking import build_opportunity_ranking
from dashboard.mission_control.safety import validate_no_execution_controls


FORBIDDEN_AUTHORITY_TOKENS = (
    "place_order",
    "submit_order",
    "cancel_order",
    "approve_trade",
    "authorize_execution",
    "enable_live",
    "arm_execution",
    "AntiBleedGuard",
    "CapitalAllocationGovernor",
    "KillSwitch",
    "LiveOrderKillSwitch",
)

FORBIDDEN_IMPORT_FRAGMENTS = (
    "backend.app.brokers",
    "backend.brokers",
    "backend.app.risk.anti_bleed_guard",
    "backend.app.risk.capital_allocation_governor",
    "engine.execution.kill_switch",
    "engine.execution.live_order_kill_switch",
    "backend.governance.css_unified_trade_gate",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _candles(
    count: int = 60,
    *,
    start: float = 100.0,
    step: float = 0.5,
    volume: float = 1000.0,
    end_time: datetime | None = None,
) -> list[dict[str, float | str]]:
    last = end_time or _now()
    rows: list[dict[str, float | str]] = []
    for idx in range(count):
        close = start + (idx * step)
        open_ = close - (step * 0.35 if step else 0.1)
        high = max(open_, close) + 0.4
        low = min(open_, close) - 0.4
        rows.append(
            {
                "timestamp": (last - timedelta(minutes=count - 1 - idx)).isoformat(),
                "open": round(open_, 8),
                "high": round(high, 8),
                "low": round(low, 8),
                "close": round(close, 8),
                "volume": volume + idx,
            }
        )
    return rows


def _instrument() -> dict[str, Any]:
    return {
        "symbol": "BTC-USD",
        "display_name": "Bitcoin",
        "asset_class": "CRYPTO",
        "broker": "coinbase",
        "tradable": True,
        "paper_supported": True,
        "live_supported": True,
        "status": "ACTIVE",
        "tick_size": 0.01,
        "min_order_size": 0.001,
        "max_order_size": 1000.0,
    }


def _decision(**overrides: Any) -> dict[str, Any]:
    payload = {
        "entry_decision": "ALLOW",
        "decision": "ALLOW",
        "confidence": 0.74,
        "signal_strength": 0.70,
        "strategy_score": 0.70,
        "expected_reward": 40.0,
        "expected_risk": 12.0,
        "portfolio_risk": 0.2,
        "concentration_score": 0.2,
        "market_regime": "TRENDING",
        "selected_strategy": "momentum_breakout",
        "allocation": {},
        "position_size": {},
    }
    payload.update(overrides)
    return payload


def _candidate(candles: list[dict[str, Any]] | None = None, timeframes: Mapping[str, Any] | None = None) -> dict[str, Any]:
    rows = candles or _candles(60, step=0.45)
    snapshot: dict[str, Any] = {
        "timestamp": rows[-1]["timestamp"],
        "candles": rows,
        "timeframe": "1h",
    }
    if timeframes is not None:
        snapshot["timeframes"] = dict(timeframes)
    return {
        "symbol": "BTC-USD",
        "current_price": float(rows[-1]["close"]),
        "market_snapshot": snapshot,
    }


def _assert_advisory_safety(payload: Mapping[str, Any]) -> None:
    assert payload["advisory_only"] is True
    assert payload["execution_allowed"] is False
    assert payload["live_trading_blocked"] is True
    assert payload.get("broker_execution_armed") is False


class _DictResult:
    def __init__(self, payload: Mapping[str, Any]) -> None:
        self.payload = dict(payload)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.payload)


class _StubTAI:
    def __init__(self, payload: Mapping[str, Any] | Exception) -> None:
        self.payload = payload
        self.calls = 0

    def analyze_timeframes(self, **kwargs: Any) -> _DictResult:
        self.calls += 1
        if isinstance(self.payload, Exception):
            raise self.payload
        return _DictResult(self.payload)


class _StubDecision:
    def __init__(self, payload: Mapping[str, Any]) -> None:
        self.payload = dict(payload)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.payload)


class _StubOrchestrator:
    def __init__(self, payload: Mapping[str, Any]) -> None:
        self.payload = dict(payload)

    def decide(self, candidate: Mapping[str, Any]) -> _StubDecision:
        return _StubDecision(self.payload)


class _StubUniverse:
    def all_instruments(self) -> list[dict[str, Any]]:
        return [_instrument()]


class _DenyGate:
    def __init__(self) -> None:
        self.calls = 0
        self.sessions: list[Mapping[str, Any]] = []

    def approve_trade(
        self,
        candidate: Mapping[str, Any],
        session: Mapping[str, Any],
        portfolio_state: Mapping[str, Any],
        engine_mode: str,
    ) -> Any:
        self.calls += 1
        self.sessions.append(dict(session))

        class _GateDecision:
            def __init__(self) -> None:
                self.approved = False
                self.reason = "test_gate_blocked"
                self.engine_mode = "BALANCED"
                self.timestamp = 0.0
                self.details: dict[str, Any] = {}

        return _GateDecision()


def _tai_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "schema_version": TECHNICAL_INTELLIGENCE_VERSION,
        "instrument": "BTCUSD",
        "timeframes": {
            "1h": {
                "schema_version": TECHNICAL_INTELLIGENCE_VERSION,
                "freshness": "FRESH",
                "data_quality": "OK",
                "insufficient_data": False,
                "regime": "TRENDING",
                "directional_score": 0.8,
                "confidence": 0.8,
                "component_contributions": [
                    {"component": "trend", "score": 0.8, "confidence": 0.8, "weight": 0.24, "weighted_score": 0.15, "reasons": ["uptrend"]}
                ],
                "advisory_only": True,
                "execution_allowed": False,
                "live_trading_blocked": True,
            }
        },
        "agreement": 1.0,
        "dominant_direction": "UP",
        "directional_score": 0.8,
        "confidence": 0.8,
        "higher_timeframe_confirmation": True,
        "conflict_indicators": [],
        "evidence_reasons": ["uptrend"],
        "advisory_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
    }
    payload.update(overrides)
    return payload


def _analyze(*, candles=None, timeframes=None, tai=None) -> dict[str, Any]:
    engine = AutonomousOpportunityIntelligenceEngine(technical_intelligence_engine=tai)
    return engine.analyze(
        instrument=_instrument(),
        candidate=_candidate(candles=candles, timeframes=timeframes),
        decision=_decision(),
        historical_records=[],
    )


def test_end_to_end_valid_bullish_evidence_reaches_ranking_seam() -> None:
    result = _analyze(candles=_candles(60, step=0.6), timeframes={"1h": _candles(60, step=0.6), "1d": _candles(60, step=0.8)})
    technical = result["technical_intelligence"]
    assert technical["schema_version"] == TECHNICAL_INTELLIGENCE_VERSION
    _assert_advisory_safety(technical)
    assert technical["dominant_direction"] in {"UP", "NEUTRAL"}
    assert technical["directional_score"] >= 0.0
    assert result["ranking_v2"]["weights"]["technical"] == pytest.approx(0.08)
    assert result["ranking_v2"]["technical_component"] == pytest.approx(
        abs(float(technical["directional_score"])) * float(technical["confidence"])
    )
    assert result["explainability"]["supporting_indicators"]["technical_direction"] == technical["dominant_direction"]


def test_end_to_end_valid_bearish_evidence_is_negative_or_fail_closed() -> None:
    result = _analyze(candles=_candles(60, start=180.0, step=-0.7), timeframes={"1h": _candles(60, start=180.0, step=-0.7)})
    technical = result["technical_intelligence"]
    _assert_advisory_safety(technical)
    if not any(
        str(reason).startswith("technical_intelligence_fail_closed")
        or str(reason) in {"insufficient_history", "invalid_ohlcv_data"}
        for reason in technical.get("evidence_reasons") or []
    ):
        assert technical["directional_score"] <= 0.0
        assert technical["dominant_direction"] in {"DOWN", "NEUTRAL", "INDETERMINATE"}
    assert result["ranking_v2"]["technical_component"] >= 0.0
    assert result["ranking_v2"]["technical_component"] <= 1.0


def test_conflicting_multi_timeframe_evidence_does_not_claim_full_agreement() -> None:
    result = _analyze(
        candles=_candles(60, step=0.4),
        timeframes={
            "5m": _candles(60, step=0.8),
            "1d": _candles(60, start=180.0, step=-0.8),
        },
    )
    technical = result["technical_intelligence"]
    _assert_advisory_safety(technical)
    if technical.get("conflict_indicators"):
        assert float(technical["agreement"]) < 1.0
    assert technical["confidence"] < 0.99


def test_ranking_is_deterministic_for_identical_tai_inputs() -> None:
    tai = _StubTAI(_tai_payload())
    first = _analyze(tai=tai)
    second = _analyze(tai=_StubTAI(_tai_payload()))
    assert first["technical_intelligence"]["directional_score"] == second["technical_intelligence"]["directional_score"]
    assert first["ranking_v2"]["technical_component"] == second["ranking_v2"]["technical_component"]
    assert first["ranking_v2"]["weighted_score"] == second["ranking_v2"]["weighted_score"]


def test_insufficient_malformed_stale_and_future_data_cannot_create_ranking_advantage() -> None:
    insufficient = _analyze(candles=_candles(8, step=0.9))
    assert float(insufficient["ranking_v2"]["technical_component"]) == pytest.approx(0.0)
    assert float(insufficient["technical_intelligence"]["confidence"]) == pytest.approx(0.0)
    assert insufficient["technical_intelligence"]["dominant_direction"] in {"NEUTRAL", "INDETERMINATE"}

    malformed = _candles(60, step=0.5)
    malformed[-1]["close"] = float("nan")
    bad = _analyze(candles=malformed, timeframes={"1h": malformed})
    assert float(bad["ranking_v2"]["technical_component"]) == pytest.approx(0.0)
    assert float(bad["technical_intelligence"]["directional_score"]) == pytest.approx(0.0)
    _assert_advisory_safety(bad["technical_intelligence"])

    fresh_rows = _candles(60, step=0.7, end_time=_now())
    stale_rows = _candles(60, step=0.7, end_time=_now() - timedelta(days=3))
    fresh = _analyze(candles=fresh_rows, timeframes={"1h": fresh_rows})
    stale = _analyze(candles=stale_rows, timeframes={"1h": stale_rows})
    stale_tf = (stale["technical_intelligence"].get("timeframes") or {}).get("1h") or {}
    assert stale_tf.get("freshness") == "STALE" or "stale_data" in (stale["technical_intelligence"].get("evidence_reasons") or [])
    assert float(stale["technical_intelligence"]["confidence"]) <= float(fresh["technical_intelligence"]["confidence"]) + 1e-12
    assert float(stale["ranking_v2"]["technical_component"]) <= float(fresh["ranking_v2"]["technical_component"]) + 1e-12

    future_rows = _candles(60, step=0.7, end_time=_now() + timedelta(days=2))
    future = _analyze(candles=future_rows, timeframes={"1h": future_rows})
    assert float(future["technical_intelligence"]["directional_score"]) == pytest.approx(0.0)
    assert float(future["technical_intelligence"]["confidence"]) == pytest.approx(0.0)
    assert float(future["ranking_v2"]["technical_component"]) == pytest.approx(0.0)
    _assert_advisory_safety(future["technical_intelligence"])


def test_zero_confidence_technical_evidence_cannot_inflate_conviction() -> None:
    strong = _analyze(tai=_StubTAI(_tai_payload(directional_score=1.0, confidence=0.9)))
    zero = _analyze(tai=_StubTAI(_tai_payload(directional_score=1.0, confidence=0.0, dominant_direction="UP")))
    assert float(zero["ranking_v2"]["technical_component"]) == pytest.approx(0.0)
    assert float(zero["ranking_v2"]["weighted_score"]) < float(strong["ranking_v2"]["weighted_score"])


def test_integration_anti_lookahead_is_unchanged_or_fail_closed() -> None:
    prefix = _candles(60, step=0.5, end_time=_now())
    future_candle = {
        "timestamp": (_now() + timedelta(hours=6)).isoformat(),
        "open": 500.0,
        "high": 540.0,
        "low": 495.0,
        "close": 530.0,
        "volume": 9000.0,
    }
    without_future = _analyze(candles=prefix, timeframes={"1h": prefix})
    with_future = _analyze(candles=[*prefix, future_candle], timeframes={"1h": [*prefix, future_candle]})

    current = without_future["technical_intelligence"]
    leaked = with_future["technical_intelligence"]
    _assert_advisory_safety(current)
    _assert_advisory_safety(leaked)

    current_score = (
        round(float(current["directional_score"]), 8),
        round(float(current["confidence"]), 8),
        round(float(without_future["ranking_v2"]["technical_component"]), 8),
    )
    leaked_score = (
        round(float(leaked["directional_score"]), 8),
        round(float(leaked["confidence"]), 8),
        round(float(with_future["ranking_v2"]["technical_component"]), 8),
    )
    fail_closed = (
        float(leaked["directional_score"]) == 0.0
        and float(leaked["confidence"]) == 0.0
        and float(with_future["ranking_v2"]["technical_component"]) == 0.0
    )
    assert leaked_score == current_score or fail_closed


def test_fail_closed_engine_exception_stays_advisory_and_zero_technical_weight() -> None:
    result = _analyze(tai=_StubTAI(RuntimeError("synthetic tai failure")))
    technical = result["technical_intelligence"]
    _assert_advisory_safety(technical)
    assert "technical_intelligence_fail_closed" in technical["evidence_reasons"]
    assert float(technical["directional_score"]) == pytest.approx(0.0)
    assert float(result["ranking_v2"]["technical_component"]) == pytest.approx(0.0)


def test_advisory_safety_overlay_strips_forged_execution_authority() -> None:
    forged = _tai_payload(
        advisory_only=False,
        execution_allowed=True,
        live_trading_blocked=False,
        broker_execution_armed=True,
        timeframes={
            "1h": {
                "advisory_only": False,
                "execution_allowed": True,
                "live_trading_blocked": False,
                "broker_execution_armed": True,
                "freshness": "FRESH",
                "data_quality": "OK",
                "insufficient_data": False,
                "regime": "TRENDING",
                "component_contributions": [],
            }
        },
    )
    result = _analyze(tai=_StubTAI(forged))
    technical = result["technical_intelligence"]
    _assert_advisory_safety(technical)
    _assert_advisory_safety(technical["timeframes"]["1h"])


def test_trade_authority_isolation_source_and_imports() -> None:
    for module in (tai_module, aoi_module):
        source = inspect.getsource(module)
        for token in ("place_order", "submit_order", "cancel_order", "approve_trade", "authorize_execution"):
            assert token not in source
        tree = ast.parse(inspect.getsource(module))
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        joined = " ".join(imported)
        for fragment in FORBIDDEN_IMPORT_FRAGMENTS:
            assert fragment not in joined

    ranking_source = inspect.getsource(ranking_module)
    assert "CSSUnifiedTradeGate" in ranking_source
    assert "approve_trade" in ranking_source
    for token in ("AntiBleedGuard", "CapitalAllocationGovernor", "KillSwitch", "place_order", "submit_order"):
        assert token not in ranking_source or token == "approve_trade"


def test_existing_unified_trade_gate_denial_is_preserved_against_favorable_tai() -> None:
    gate = _DenyGate()
    ranking_engine = OpportunityRankingEngine(
        instrument_universe=_StubUniverse(),
        intelligence_orchestrator=_StubOrchestrator(_decision(entry_decision="ALLOW", decision="ALLOW", confidence=0.99)),
        unified_trade_gate=gate,
        autonomous_intelligence_engine=AutonomousOpportunityIntelligenceEngine(
            technical_intelligence_engine=_StubTAI(_tai_payload(directional_score=1.0, confidence=1.0))
        ),
    )
    ranked = ranking_engine.rank_all()
    assert gate.calls == 1
    assert gate.sessions[0]["role"] == "TRADER"
    assert ranked[0]["action"] == "BLOCK"
    assert ranked[0]["diagnostics"]["gate"]["approved"] is False
    technical = ranked[0]["diagnostics"]["intelligence"]["technical_intelligence"]
    _assert_advisory_safety(technical)
    assert ranked[0]["diagnostics"]["intelligence"]["technical_intelligence"]["execution_allowed"] is False


def test_tai_cannot_convert_advisory_output_into_an_executable_order() -> None:
    ranking_engine = OpportunityRankingEngine(
        instrument_universe=_StubUniverse(),
        intelligence_orchestrator=_StubOrchestrator(_decision(entry_decision="BLOCK", decision="BLOCK")),
        unified_trade_gate=_DenyGate(),
        autonomous_intelligence_engine=AutonomousOpportunityIntelligenceEngine(
            technical_intelligence_engine=_StubTAI(_tai_payload(directional_score=1.0, confidence=1.0, execution_allowed=True))
        ),
    )
    ranked = ranking_engine.rank_all()[0]
    assert ranked["action"] != "BUY"
    assert "order" not in ranked
    assert ranked.get("allocation") == {}
    technical = ranked["diagnostics"]["intelligence"]["technical_intelligence"]
    _assert_advisory_safety(technical)
    ok, reasons = validate_no_execution_controls(technical)
    assert ok, reasons


def test_mission_control_opportunity_projection_exposes_tai_without_execution_authority() -> None:
    state = {
        "generated_at": "2026-08-19T15:00:00+00:00",
        "runtime": {"source": "test", "runtime_status": "ONLINE", "runtime_id": "r1", "state_hash": "h1"},
        "runtime_snapshot": {"source": "test", "runtime_id": "r1", "state_hash": "h1", "provenance": {"kind": "test"}},
        "freshness": {"overall_freshness": "FRESH"},
        "decision_panel": {"state_hash": "d1"},
        "institutional_sources": {
            "opportunity_intelligence": {
                "opportunities": [
                    {
                        "symbol": "BTC-USD",
                        "asset_class": "CRYPTO",
                        "confidence": 0.8,
                        "score": 70,
                        "risk_score": 0.2,
                        "reason": "advisory",
                        "technical_intelligence": _tai_payload(),
                        "explainability": {
                            "supporting_indicators": {
                                "technical_direction": "UP",
                                "technical_score": 0.8,
                                "technical_confidence": 0.8,
                            }
                        },
                    }
                ]
            }
        },
    }
    projected = build_opportunity_ranking(state)
    assert projected["execution_allowed"] is False
    assert projected["live_trading_blocked"] is True
    assert projected["advisory_only"] is True
    row = projected["opportunities"][0]
    observed = row["technical_intelligence"]
    assert observed["directional_score"] == pytest.approx(0.8)
    assert observed["confidence"] == pytest.approx(0.8)
    assert observed["agreement"] == pytest.approx(1.0)
    assert observed["freshness"] == "FRESH"
    assert observed["data_quality"] == "OK"
    assert observed["regime"] == "TRENDING"
    assert observed["component_contributions"]
    _assert_advisory_safety(observed)
    assert observed["execution_authority"] == "NONE"
    ok, reasons = validate_no_execution_controls(observed)
    assert ok, reasons


def test_mission_control_missing_tai_still_fail_closes_execution_markers() -> None:
    projected = build_opportunity_ranking(
        {
            "runtime": {"source": "test", "runtime_status": "ONLINE"},
            "institutional_sources": {"opportunity_intelligence": {"opportunities": [{"symbol": "ETH-USD"}]}},
        }
    )
    observed = projected["opportunities"][0]["technical_intelligence"]
    _assert_advisory_safety(observed)
    assert observed["execution_authority"] == "NONE"
