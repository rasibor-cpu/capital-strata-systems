from backend.intelligence.global_intelligence.dashboard_intelligence_adapter import build_dashboard_intelligence_payload
from backend.intelligence.global_intelligence.event_classifier import classify_event
from backend.intelligence.global_intelligence.intelligence_state_manager import IntelligenceStateManager


def test_build_dashboard_intelligence_payload():
    state_manager = IntelligenceStateManager()
    event = classify_event("Fed rate hike expected", "The FOMC decision is due.", "Federal Reserve")
    state_manager.add_event(event)
    payload = build_dashboard_intelligence_payload(state_manager)

    assert payload["current_regime"] in {"NORMAL", "CAUTION", "DEFENSIVE", "PANIC", "OPPORTUNITY_EXPANSION", "LIQUIDITY_CRISIS"}
    assert payload["event_count"] == 1
    assert isinstance(payload["active_events"], list)
    assert payload["highest_severity"] in {"LOW", "MODERATE", "HIGH", "SEVERE", "CRITICAL"}
    assert payload["gie_status"] == "OK"
    assert "decision_state" in payload


def test_dashboard_payload_failure_safe():
    payload = build_dashboard_intelligence_payload(None)
    assert payload["current_regime"] == "NORMAL"
    assert payload["gie_status"] == "OK"


def test_dashboard_payload_canonical_decision_state():
    state_manager = IntelligenceStateManager()
    payload = build_dashboard_intelligence_payload(
        state_manager,
        canonical_decision={
            "timestamp": "2026-06-24T12:00:00+00:00",
            "market_regime": "TRENDING",
            "selected_strategy": "alpha",
            "confidence": 0.78,
            "signal_strength": 0.81,
            "portfolio_risk": 0.2,
            "allocation": {"allocation_amount": 1200.0},
            "position_size": {"recommended_position_size": 100.0},
            "entry_decision": "ALLOW",
            "learning_context": {"confidence": 0.73, "last_strategy_outcome": "WIN"},
        },
    )

    state = payload["decision_state"]
    assert state["current_market_regime"] == "TRENDING"
    assert state["selected_strategy"] == "alpha"
    assert state["confidence_score"] == 0.78
    assert state["signal_strength"] == 0.81
    assert state["allocation"] == 1200.0
    assert state["position_size"] == 100.0
    assert state["current_decision"] == "ALLOW"
    assert state["learning_confidence"] == 0.73
