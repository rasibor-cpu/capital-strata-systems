from backend.intelligence.global_intelligence.event_classifier import classify_event
from backend.intelligence.global_intelligence.event_models import EventCategory


def test_classify_event_monetary_policy():
    event = classify_event("Fed rate hike expected", "The FOMC is signaling higher rates.", "Federal Reserve")
    assert event.category == EventCategory.MONETARY_POLICY
    assert "SPY" in event.affected_assets
    assert event.severity in (event.severity.HIGH, event.severity.MODERATE)


def test_classify_event_regulatory_crypto():
    event = classify_event("SEC action on crypto exchange", "Regulatory notice issued.", "SEC")
    assert event.category == EventCategory.REGULATORY
    assert "BTC" in event.affected_assets
    assert event.confidence == 100.0
