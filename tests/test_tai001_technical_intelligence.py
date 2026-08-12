from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

import pytest

from backend.intelligence.technical_intelligence import (
    TECHNICAL_INTELLIGENCE_VERSION,
    TechnicalIntelligenceConfig,
    TechnicalIntelligenceEngine,
)
from backend.intelligence import technical_intelligence as tai_module
from backend.trading.autonomous_opportunity_intelligence_engine import (
    AutonomousOpportunityIntelligenceEngine,
)
from backend.trading.opportunity_ranking_engine import OpportunityRankingEngine


def _candles(
    count: int = 60,
    *,
    start: float = 100.0,
    step: float = 0.5,
    volume: float = 1000.0,
    start_time: datetime | None = None,
) -> list[dict[str, float | str]]:
    now = start_time or datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows: list[dict[str, float | str]] = []
    for idx in range(count):
        close = start + (idx * step)
        open_ = close - (step * 0.35 if step else 0.1)
        high = max(open_, close) + 0.4
        low = min(open_, close) - 0.4
        rows.append(
            {
                "timestamp": (now + timedelta(minutes=idx)).isoformat(),
                "open": round(open_, 8),
                "high": round(high, 8),
                "low": round(low, 8),
                "close": round(close, 8),
                "volume": volume + idx,
            }
        )
    return rows


def _scalar_values(value: Any) -> list[Any]:
    if isinstance(value, Mapping):
        output: list[Any] = []
        for item in value.values():
            output.extend(_scalar_values(item))
        return output
    if isinstance(value, (list, tuple)):
        output = []
        for item in value:
            output.extend(_scalar_values(item))
        return output
    return [value]


def _assert_insufficient_public_indicator_contract(snapshot: Any) -> None:
    assert snapshot.insufficient_data is True
    assert snapshot.rsi is None
    assert snapshot.macd == {"line": None, "signal": None, "histogram": None}
    assert snapshot.bollinger["upper"] is None
    assert snapshot.bollinger["middle"] is None
    assert snapshot.bollinger["lower"] is None
    assert snapshot.bollinger["position"] is None
    assert snapshot.bollinger["width"] is None
    assert snapshot.bollinger["state"] == "INSUFFICIENT"
    assert snapshot.atr is None
    assert snapshot.normalized_volatility is None
    assert snapshot.volatility_state == "INSUFFICIENT"

    observations = {item.name: item for item in snapshot.observations}
    if observations:
        assert observations["RSI"].value is None
        assert observations["MACD"].value == {"line": None, "signal": None, "histogram": None}
        assert observations["BOLLINGER"].value["upper"] is None
        assert observations["BOLLINGER"].value["middle"] is None
        assert observations["BOLLINGER"].value["lower"] is None
        assert observations["BOLLINGER"].value["position"] is None
        assert observations["BOLLINGER"].value["width"] is None
        assert observations["BOLLINGER"].value["state"] == "INSUFFICIENT"
        assert observations["ATR"].value is None
        assert all(item.state in {"INSUFFICIENT", "INDETERMINATE"} for item in observations.values())
        assert all(item.confidence == 0.0 for item in observations.values())
        assert all(item.direction_score == 0.0 for item in observations.values())

    forbidden_actionable_states = {
        "ABOVE_UPPER",
        "BELOW_LOWER",
        "IN_BAND",
        "BREAKOUT_CONFIRMED",
        "BREAKOUT_UNCONFIRMED",
        "BREAKDOWN_CONFIRMED",
        "BREAKDOWN_UNCONFIRMED",
        "IN_RANGE",
        "UP",
        "DOWN",
        "HIGH",
        "LOW",
        "NORMAL",
        "OK",
        "OBSERVED",
        "bullish_engulfing",
        "bearish_engulfing",
        "hammer",
        "shooting_star",
    }
    public_strings = {
        value
        for value in _scalar_values(snapshot.to_dict())
        if isinstance(value, str)
    }
    assert forbidden_actionable_states.isdisjoint(public_strings)


def test_sma_ema_rsi_macd_bollinger_atr_and_volume() -> None:
    engine = TechnicalIntelligenceEngine()
    rows = _candles()

    result = engine.analyze(
        instrument="SPY",
        timeframe="1d",
        candles=rows,
        now=datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc),
    )

    closes = [float(row["close"]) for row in rows]
    assert result.schema_version == TECHNICAL_INTELLIGENCE_VERSION
    assert result.sample_count == 60
    assert result.insufficient_data is False
    assert result.trend_direction == "UP"
    assert result.rsi is not None and result.rsi > 50.0
    assert result.macd["line"] is not None
    assert result.bollinger["upper"] is not None
    assert result.atr is not None and result.atr > 0.0
    assert result.volume_score >= 0.0
    assert engine.sma(closes, 10) == pytest.approx(sum(closes[-10:]) / 10)
    assert engine.ema(closes, 12) is not None


def test_structure_breakout_support_resistance_and_patterns() -> None:
    engine = TechnicalIntelligenceEngine()
    rows = _candles(45, step=0.0)
    prior_resistance = max(float(row["high"]) for row in rows[:-1])
    rows[-1] = {
        **rows[-1],
        "open": prior_resistance + 0.5,
        "high": prior_resistance + 2.0,
        "low": prior_resistance + 0.2,
        "close": prior_resistance + 1.5,
        "volume": 5000.0,
    }

    result = engine.analyze(instrument="BTC-USD", timeframe="15m", candles=rows)

    assert result.support is not None
    assert result.resistance == pytest.approx(prior_resistance)
    assert result.breakout_state == "BREAKOUT_CONFIRMED"
    assert result.distance_from_support is not None
    assert result.distance_from_resistance is not None

    hammer_rows = _candles(44)
    hammer_rows.append(
        {
            "timestamp": datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc).isoformat(),
            "open": 110.0,
            "high": 110.2,
            "low": 104.0,
            "close": 110.1,
            "volume": 1500.0,
        }
    )
    hammer = engine.analyze(instrument="AAPL", timeframe="1h", candles=hammer_rows)
    assert "hammer" in hammer.patterns


def test_bullish_and_bearish_engulfing_patterns_are_descriptive() -> None:
    engine = TechnicalIntelligenceEngine()
    rows = _candles(43)
    rows.extend(
        [
            {"timestamp": "2026-01-01T01:00:00+00:00", "open": 105.0, "high": 106.0, "low": 101.0, "close": 102.0, "volume": 1000.0},
            {"timestamp": "2026-01-01T01:01:00+00:00", "open": 101.5, "high": 107.0, "low": 101.0, "close": 106.5, "volume": 1200.0},
        ]
    )
    bullish = engine.analyze(instrument="MSFT", candles=rows)
    assert "bullish_engulfing" in bullish.patterns
    assert "descriptive_patterns_no_predictive_claim" in {
        obs.reason for obs in bullish.observations if obs.name == "CANDLESTICK"
    }

    rows[-2] = {"timestamp": "2026-01-01T01:00:00+00:00", "open": 102.0, "high": 106.0, "low": 101.0, "close": 105.0, "volume": 1000.0}
    rows[-1] = {"timestamp": "2026-01-01T01:01:00+00:00", "open": 105.5, "high": 106.0, "low": 100.0, "close": 101.5, "volume": 1200.0}
    bearish = engine.analyze(instrument="MSFT", candles=rows)
    assert "bearish_engulfing" in bearish.patterns


def test_insufficient_stale_and_malformed_data_fail_closed() -> None:
    engine = TechnicalIntelligenceEngine()
    insufficient = engine.analyze(instrument="QQQ", candles=_candles(5))
    assert insufficient.insufficient_data is True
    _assert_insufficient_public_indicator_contract(insufficient)
    assert insufficient.confidence <= 0.34
    assert insufficient.directional_score == 0.0
    assert insufficient.trend_direction == "INDETERMINATE"
    assert insufficient.trend_strength == 0.0
    assert insufficient.regime == "INSUFFICIENT_DATA"
    assert insufficient.breakout_state == "INSUFFICIENT"
    assert insufficient.volume_score == 0.0
    assert insufficient.volume_anomaly is False
    assert all(item.weighted_score == 0.0 for item in insufficient.component_contributions)
    assert all(item.confidence == 0.0 for item in insufficient.observations)

    generic_rows = _candles(33, step=0.25)
    generic_rows[-2] = {
        **generic_rows[-2],
        "open": 110.0,
        "high": 110.5,
        "low": 106.5,
        "close": 107.0,
        "volume": 1000.0,
    }
    generic_rows[-1] = {
        **generic_rows[-1],
        "open": 106.8,
        "high": 112.5,
        "low": 106.0,
        "close": 112.0,
        "volume": 1000000.0,
    }
    generic = engine.analyze(instrument="QQQ", candles=generic_rows)
    assert generic.insufficient_data is True
    _assert_insufficient_public_indicator_contract(generic)
    assert generic.support is None
    assert generic.resistance is None
    assert generic.distance_from_support is None
    assert generic.distance_from_resistance is None
    assert generic.patterns == ()
    assert generic.breakout_state == "INSUFFICIENT"
    assert generic.trend_direction == "INDETERMINATE"
    assert generic.trend_strength == 0.0
    assert generic.regime == "INSUFFICIENT_DATA"
    assert generic.volume_score == 0.0
    assert generic.volume_anomaly is False
    assert generic.directional_score == 0.0
    assert all(item.score == 0.0 for item in generic.component_contributions)
    assert all(item.confidence == 0.0 for item in generic.component_contributions)
    assert all(item.weighted_score == 0.0 for item in generic.component_contributions)
    assert all(item.reasons == ("insufficient_history",) for item in generic.component_contributions)
    assert all(item.confidence == 0.0 for item in generic.observations)
    assert all(item.direction_score == 0.0 for item in generic.observations)
    structure_observation = next(item for item in generic.observations if item.name == "STRUCTURE")
    assert structure_observation.value["support"] is None
    assert structure_observation.value["resistance"] is None
    assert structure_observation.value["distance_from_support"] is None
    assert structure_observation.value["distance_from_resistance"] is None
    assert structure_observation.value["breakout_state"] == "INSUFFICIENT"
    assert structure_observation.value["score"] == 0.0
    assert structure_observation.value["reasons"] == ("insufficient_history",)
    candlestick_observation = next(item for item in generic.observations if item.name == "CANDLESTICK")
    assert candlestick_observation.value == ()

    malformed = _candles(60)
    malformed[-1] = {**malformed[-1], "high": 90.0, "low": 120.0}
    invalid = engine.analyze(instrument="QQQ", candles=malformed)
    assert invalid.insufficient_data is True
    assert invalid.execution_allowed is False
    assert "invalid_ohlcv_data" in invalid.data_warnings

    stale = engine.analyze(
        instrument="QQQ",
        candles=_candles(60),
        now=datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc),
    )
    assert stale.freshness == "STALE"
    assert "stale_data" in stale.data_warnings


def test_future_timestamped_candles_fail_closed_and_cannot_influence_current_evidence() -> None:
    engine = TechnicalIntelligenceEngine()
    evaluation_time = datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc)
    historical = _candles(60, step=0.25)
    baseline = engine.analyze(
        instrument="SPY",
        candles=historical,
        now=evaluation_time,
    )

    contaminated = [
        *historical,
        {
            "timestamp": (evaluation_time + timedelta(minutes=1)).isoformat(),
            "open": 1000.0,
            "high": 1010.0,
            "low": 995.0,
            "close": 1005.0,
            "volume": 1000000.0,
        },
    ]
    future = engine.analyze(
        instrument="SPY",
        candles=contaminated,
        now=evaluation_time,
    )

    assert baseline.insufficient_data is False
    assert baseline.directional_score != 0.0
    assert future.insufficient_data is True
    _assert_insufficient_public_indicator_contract(future)
    assert future.freshness == "FUTURE_TIMESTAMP"
    assert "FUTURE_TIMESTAMP" in future.data_warnings
    assert "future_timestamped_market_data" in future.data_warnings
    assert future.directional_score == 0.0
    assert future.confidence == 0.0
    assert future.trend_direction == "INDETERMINATE"
    assert future.trend_strength == 0.0
    assert future.regime == "INSUFFICIENT_DATA"
    assert future.breakout_state == "INSUFFICIENT"
    assert future.support is None
    assert future.resistance is None


def test_volume_anomaly_threshold_and_insufficient_volume_fail_closed() -> None:
    config = TechnicalIntelligenceConfig(volume_anomaly_ratio=2.0)
    engine = TechnicalIntelligenceEngine(config)
    rows = _candles(60, step=0.1, volume=100.0)
    for row in rows:
        row["volume"] = 100.0

    below_threshold = [dict(row) for row in rows]
    below_threshold[-1]["volume"] = 199.99
    normal = engine.analyze(instrument="QQQ", candles=below_threshold)
    assert normal.volume_anomaly is False

    at_threshold = [dict(row) for row in rows]
    at_threshold[-1]["volume"] = 200.0
    anomalous = engine.analyze(instrument="QQQ", candles=at_threshold)
    assert anomalous.insufficient_data is False
    assert anomalous.volume_anomaly is True
    assert anomalous.volume_score == pytest.approx(1.0)

    malformed = [dict(row) for row in rows]
    malformed[-1]["volume"] = -1.0
    invalid = engine.analyze(instrument="QQQ", candles=malformed)
    assert invalid.insufficient_data is True
    assert invalid.confidence == 0.0
    assert invalid.volume_anomaly is False
    assert invalid.volume_score == 0.0

    insufficient = _candles(5, step=0.1, volume=0.0)
    insufficient[-1]["volume"] = 1000000.0
    weak = engine.analyze(instrument="QQQ", candles=insufficient)
    assert weak.insufficient_data is True
    assert weak.confidence <= 0.34
    assert weak.volume_anomaly is False
    assert weak.volume_score == 0.0


def test_repeatability_and_output_contract_are_stable() -> None:
    engine = TechnicalIntelligenceEngine()
    rows = _candles(60)

    first = engine.analyze(instrument="ES", timeframe="5m", candles=rows).to_dict()
    second = engine.analyze(instrument="ES", timeframe="5m", candles=rows).to_dict()

    assert first == second
    assert first["advisory_only"] is True
    assert first["execution_allowed"] is False
    assert first["live_trading_blocked"] is True
    assert "component_contributions" in first
    assert "evidence_reasons" in first


def test_multi_timeframe_agreement_conflict_and_higher_timeframe_confirmation() -> None:
    engine = TechnicalIntelligenceEngine()
    result = engine.analyze_timeframes(
        instrument="BTC-USD",
        timeframe_candles={
            "5m": _candles(60, step=-0.5),
            "1h": _candles(60, step=0.6),
            "1d": _candles(60, step=0.7),
        },
    )

    assert result.dominant_direction == "UP"
    assert result.higher_timeframe_confirmation is True
    assert "5m" in result.conflict_indicators
    assert 0.0 <= result.agreement <= 1.0
    assert result.execution_allowed is False


def test_support_resistance_does_not_look_ahead() -> None:
    engine = TechnicalIntelligenceEngine()
    prefix = _candles(45, step=0.1)
    without_future = engine.analyze(instrument="SPY", candles=prefix)
    with_future = engine.analyze(
        instrument="SPY",
        candles=[
            *prefix,
            {
                "timestamp": "2026-01-01T02:00:00+00:00",
                "open": 500.0,
                "high": 510.0,
                "low": 495.0,
                "close": 505.0,
                "volume": 2000.0,
            },
        ],
    )

    assert without_future.resistance is not None
    assert with_future.resistance == pytest.approx(max(float(row["high"]) for row in prefix))
    assert with_future.resistance != pytest.approx(510.0)
    assert with_future.breakout_state.startswith("BREAKOUT")


def test_autonomous_integration_is_advisory_only_and_exposes_technical_contract() -> None:
    engine = AutonomousOpportunityIntelligenceEngine()
    result = engine.analyze(
        instrument={
            "symbol": "BTC-USD",
            "asset_class": "CRYPTO",
            "tick_size": 0.01,
            "min_order_size": 0.001,
            "max_order_size": 1000.0,
        },
        candidate={
            "symbol": "BTC-USD",
            "current_price": 68000.0,
            "market_snapshot": {
                "timeframes": {
                    "5m": _candles(60, step=0.4),
                    "1h": _candles(60, step=0.5),
                },
                "candles": _candles(60, step=0.5),
            },
        },
        decision={
            "selected_strategy": "momentum_breakout",
            "confidence": 0.74,
            "concentration_score": 0.2,
        },
        historical_records=[],
    )

    technical = result["technical_intelligence"]
    assert technical["schema_version"] == TECHNICAL_INTELLIGENCE_VERSION
    assert technical["advisory_only"] is True
    assert technical["execution_allowed"] is False
    assert technical["live_trading_blocked"] is True
    assert result["ranking_v2"]["weights"]["technical"] == pytest.approx(0.08)
    assert result["explainability"]["supporting_indicators"]["technical_confidence"] >= 0.0


def test_trade_authority_isolation_and_existing_gate_denial_is_preserved() -> None:
    source = inspect.getsource(tai_module)
    for forbidden in ("place_order", "submit_order", "approve_trade", "authorize_execution"):
        assert forbidden not in source

    snapshot = TechnicalIntelligenceEngine().analyze(
        instrument="BTC-USD",
        candles=_candles(60, step=0.4),
    ).to_dict()
    assert snapshot["advisory_only"] is True
    assert snapshot["execution_allowed"] is False
    assert snapshot["live_trading_blocked"] is True

    class _Universe:
        def all_instruments(self) -> list[dict[str, Any]]:
            return [
                {
                    "symbol": "BTC-USD",
                    "display_name": "Bitcoin",
                    "asset_class": "CRYPTO",
                    "broker": "coinbase",
                    "tradable": True,
                    "paper_supported": True,
                    "live_supported": True,
                    "status": "ACTIVE",
                }
            ]

    class _Decision:
        def to_dict(self) -> dict[str, Any]:
            return {
                "entry_decision": "ALLOW",
                "decision": "ALLOW",
                "confidence": 0.95,
                "signal_strength": 0.95,
                "strategy_score": 0.95,
                "expected_reward": 100.0,
                "expected_risk": 10.0,
                "portfolio_risk": 0.1,
                "concentration_score": 0.1,
                "market_regime": "TRENDING",
                "selected_strategy": "momentum_breakout",
                "allocation": {"allocation_amount": 2000.0},
                "position_size": {"recommended_position_size": 0.25},
            }

    class _Orchestrator:
        def decide(self, candidate: Mapping[str, Any]) -> _Decision:
            return _Decision()

    class _DenyGate:
        def __init__(self) -> None:
            self.calls = 0

        def approve_trade(
            self,
            candidate: Mapping[str, Any],
            session: Mapping[str, Any],
            portfolio_state: Mapping[str, Any],
            engine_mode: str,
        ) -> Any:
            self.calls += 1

            class _GateDecision:
                def __init__(self) -> None:
                    self.approved = False
                    self.reason = "test_gate_blocked"
                    self.engine_mode = "BALANCED"
                    self.timestamp = 0.0
                    self.details: dict[str, Any] = {}

            return _GateDecision()

    gate = _DenyGate()
    ranking_engine = OpportunityRankingEngine(
        instrument_universe=_Universe(),
        intelligence_orchestrator=_Orchestrator(),
        unified_trade_gate=gate,
    )
    ranked = ranking_engine.rank_all()

    assert gate.calls == 1
    assert ranked[0]["action"] == "BLOCK"
    assert ranked[0]["diagnostics"]["gate"]["approved"] is False
    technical = ranked[0]["diagnostics"]["intelligence"]["technical_intelligence"]
    assert technical["advisory_only"] is True
    assert technical["execution_allowed"] is False
    assert technical["live_trading_blocked"] is True
