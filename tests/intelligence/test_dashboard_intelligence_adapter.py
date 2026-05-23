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


def test_dashboard_payload_failure_safe():
    payload = build_dashboard_intelligence_payload(None)
    assert payload["current_regime"] == "NORMAL"
    assert payload["gie_status"] == "OK"
