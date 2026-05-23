from datetime import datetime, timezone

from backend.intelligence.global_intelligence.event_models import EventCategory, EventSeverity, IntelligenceEvent
from backend.intelligence.global_intelligence.regime_mutation_engine import determine_regime
from backend.intelligence.global_intelligence.event_models import RegimeState


def _make_event(category, severity, confidence):
    return IntelligenceEvent(
        event_id="evt",
        timestamp=datetime.now(timezone.utc),
        title="Test",
        category=category,
        severity=severity,
        confidence=confidence,
        source="Test",
        affected_assets=["MARKET"],
    )


def test_determine_regime_normal():
    assert determine_regime([]) == RegimeState.NORMAL


def test_determine_regime_caution():
    event = _make_event(EventCategory.INFLATION, EventSeverity.MODERATE, 50.0)
    assert determine_regime([event]) == RegimeState.CAUTION


def test_determine_regime_defensive():
    event = _make_event(EventCategory.MONETARY_POLICY, EventSeverity.HIGH, 65.0)
    assert determine_regime([event]) == RegimeState.DEFENSIVE


def test_determine_regime_panic():
    event = _make_event(EventCategory.GEOPOLITICAL, EventSeverity.SEVERE, 75.0)
    assert determine_regime([event]) == RegimeState.PANIC


def test_determine_regime_liquidity_crisis():
    event = _make_event(EventCategory.EXCHANGE, EventSeverity.SEVERE, 80.0)
    assert determine_regime([event]) == RegimeState.LIQUIDITY_CRISIS


def test_determine_regime_opportunity_expansion():
    event = _make_event(EventCategory.EARNINGS, EventSeverity.HIGH, 75.0)
    assert determine_regime([event]) == RegimeState.OPPORTUNITY_EXPANSION
