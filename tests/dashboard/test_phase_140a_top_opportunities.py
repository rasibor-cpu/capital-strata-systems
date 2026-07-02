from __future__ import annotations

from dashboard.runtime.frontend_contract import build_frontend_payload
from dashboard.web.web_app import _market_opportunities_page
from dashboard.mobile.mobile_app import _opportunities_page


TRADER = {"user_id": "00017", "display_name": "CSS Trader", "role": "TRADER"}
SESSION = {"created": 1.0}


def _payload(opportunities):
    return build_frontend_payload(
        {
            "market_summary": {
                "liquidity_state": "HEALTHY",
                "volatility_state": "NORMAL",
                "spread_state": "TIGHT",
            },
            "risk_summary": {"risk_state": "NORMAL"},
            "opportunities": opportunities,
        }
    )["sections"]["opportunities"]


def test_phase_140a_green_approved_opportunities_show_first_and_red_excluded() -> None:
    opportunities = _payload(
        [
            {"symbol": "RED1", "status": "RED", "approval_state": "NOT_APPROVED", "score": 99},
            {"symbol": "OK1", "status": "GREEN", "approval_state": "APPROVED", "score": 80, "explanation": "approved"},
            {"symbol": "WATCH1", "status": "AMBER", "approval_state": "NEAR_APPROVED", "score": 70},
        ]
    )

    assert opportunities["display_state"] == "GREEN_APPROVED"
    assert [row["symbol"] for row in opportunities["items"]] == ["OK1"]
    assert "RED1" not in [row["symbol"] for row in opportunities["items"]]
    assert opportunities["items"][0]["opportunity_explanation"] == "approved"
    assert opportunities["market_health"] == "GREEN"


def test_phase_140a_amber_watch_fallback_when_no_green_exists() -> None:
    opportunities = _payload(
        [
            {"symbol": "BLOCKED", "status": "NOT_APPROVED", "score": 90},
            {"symbol": "NEAR", "status": "WATCH", "approval_state": "NEAR_APPROVED", "score": 65},
        ]
    )

    assert opportunities["display_state"] == "AMBER_WATCH"
    assert [row["symbol"] for row in opportunities["items"]] == ["NEAR"]


def test_phase_140a_all_red_returns_capital_preservation_empty_state() -> None:
    opportunities = _payload(
        [
            {"symbol": "R1", "status": "RED", "approval_state": "NOT_APPROVED"},
            {"symbol": "R2", "risk_state": "RED", "approval_state": "BLOCKED"},
        ]
    )

    assert opportunities["count"] == 0
    assert opportunities["display_state"] == "CAPITAL_PRESERVATION"
    assert "Capital preservation" in opportunities["empty_state"]


def test_phase_140a_desktop_and_mobile_render_display_only_opportunity_surfaces() -> None:
    desktop = _market_opportunities_page()
    mobile = _opportunities_page(TRADER, SESSION)

    assert "Top Opportunities" in desktop
    assert "Market Health" in desktop
    assert "Capital preservation active" in desktop
    assert "Top Opportunities" in mobile
    assert "Market Health" in mobile
    assert "Approved paper-mode candidate" in mobile
    assert "Excluded by risk-aware display" not in mobile
