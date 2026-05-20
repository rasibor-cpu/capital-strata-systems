from datetime import datetime, timedelta

from backend.intelligence.global_intelligence.macro_calendar_engine import get_upcoming_events, is_high_risk_window


def test_macro_calendar_upcoming_events():
    events = get_upcoming_events()
    assert isinstance(events, list)
    assert len(events) == 5
    assert all("name" in event and "expected_date" in event for event in events)


def test_macro_calendar_high_risk_window():
    events = get_upcoming_events()
    assert events
    first_event_time = datetime.fromisoformat(events[0]["expected_date"].replace("Z", ""))
    check_time = first_event_time + timedelta(days=1)
    assert is_high_risk_window(now=check_time) is True
    far_time = first_event_time - timedelta(days=10)
    assert is_high_risk_window(now=far_time) is False
