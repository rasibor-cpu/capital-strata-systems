from __future__ import annotations

from dashboard.web.web_app import _replay_page, create_app


def test_replay_page_registers_read_only_route_and_markup() -> None:
    app = create_app()
    routes = {getattr(route, "path", "") for route in app.routes}
    markup = _replay_page()

    assert "/replay" in routes
    assert "/api/v1/trade-lifecycle-replay" in routes
    assert "CSS Lifecycle Replay Viewer" in markup
    assert "Lifecycle Replay Table" in markup
    assert "Event Mix" in markup
    assert "Replay Health" in markup
    assert "No lifecycle replay events match the current view" in markup
    assert "data-refresh-replay" in markup
    assert "replay-filter-event" in markup
    assert "replay-filter-symbol" in markup
    assert "replay-filter-asset" in markup
    assert "replay-filter-cycle" in markup
    assert "replay-filter-limit" in markup


def test_replay_page_exposes_summary_metrics_and_safe_columns() -> None:
    markup = _replay_page()

    expected = [
        "Total Events",
        "Exits Booked",
        "Realized PnL Handoffs",
        "Defensive Reductions",
        "Capital Releases",
        "Returned Rows",
        "Malformed Lines",
        "Source Exists",
        "<span>Time</span><span>Event</span><span>Symbol</span>",
        "<span>Asset</span><span>Cycle</span><span>Mode</span>",
        "<span>Reason</span><span>Realized PnL</span><span>Position</span>",
    ]

    for item in expected:
        assert item in markup


def test_replay_page_uses_lightweight_limiting_and_filter_query() -> None:
    markup = _replay_page()

    assert 'value="100"' in markup
    assert 'max="1000"' in markup
    assert 'params.set("event_type", eventType)' in markup
    assert 'params.set("symbol", symbol)' in markup
    assert 'params.set("asset_class", asset)' in markup
    assert 'params.set("cycle", cycle)' in markup
    assert 'params.set("limit", limit)' in markup
    assert 'fetch(`/api/v1/trade-lifecycle-replay?' in markup
