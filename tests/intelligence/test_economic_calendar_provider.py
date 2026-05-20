from datetime import datetime, timezone

from backend.intelligence.global_intelligence.economic_calendar_provider import EconomicCalendarProvider


def test_economic_calendar_provider_week_events():
    provider = EconomicCalendarProvider()
    events = provider.get_week_events()
    assert isinstance(events, list)
    assert len(events) >= 1
    assert all("name" in event and "expected_date" in event for event in events)


def test_is_major_event_today_and_today_events():
    provider = EconomicCalendarProvider()
    now = datetime.now(timezone.utc)
    week_events = provider.get_week_events(now=now)
    assert provider.is_major_event_today(now=now) is False
    today_events = provider.get_today_events(now=now)
    assert isinstance(today_events, list)
    assert all(event["name"] in {"FOMC", "CPI", "PPI", "NFP", "GDP", "UNEMPLOYMENT_CLAIMS"} for event in today_events)
