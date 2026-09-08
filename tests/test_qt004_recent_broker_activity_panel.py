from pathlib import Path

from fastapi.testclient import TestClient

from launcher import css_mobile_launcher as launcher


TEMPLATE = Path("launcher/templates/mobile_dashboard.html")


def test_qt004_template_contains_recent_broker_activity_panel():
    page = TEMPLATE.read_text(encoding="utf-8")

    assert 'id="recent-broker-activity"' in page
    assert "Recent Broker Activity" in page
    assert "ACCOUNT HISTORY" in page
    assert "Execution feed" in page


def test_qt004_template_uses_recent_broker_activity_contract():
    page = TEMPLATE.read_text(encoding="utf-8")

    assert "recent_broker_activity" in page
    assert "activity_count" in page
    assert "classification" in page
    assert "net_amount" in page


def test_qt004_launcher_publishes_template_facing_activity_contract(
    monkeypatch,
):
    snapshot = {
        "status": "AVAILABLE",
        "balances": {
            "combinedBalances": [],
        },
        "positions": {
            "positions": [],
        },
        "activities": {
            "status": "AVAILABLE",
            "provenance": "QUESTRADE_ACTIVITIES",
            "activities": [
                {
                    "action": "DIV",
                    "symbol": "ENB",
                    "description": "ENBRIDGE INC CASH DIV",
                    "netAmount": 6.91,
                    "currency": "USD",
                    "type": "Dividends",
                }
            ],
            "activity_count": 1,
        },
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }

    monkeypatch.setattr(
        launcher._QUESTRADE_MISSION_CONTROL_CACHE,
        "read",
        lambda: snapshot,
    )

    payload = launcher.apply_launcher_questrade_read_only_cache({})

    # This verifies the source contract remains correct.
    assert payload["broker_activity"]["activity_count"] == 1
    assert (
        payload["broker_activity"]["rows"][0]["classification"]
        == "DIVIDEND"
    )


def test_qt004_activity_panel_is_display_only():
    page = TEMPLATE.read_text(encoding="utf-8").lower()

    section_start = page.index('id="recent-broker-activity"')
    section = page[section_start:section_start + 5000]

    forbidden = (
        "submit order",
        "place order",
        "cancel order",
        "modify order",
        "/orders",
        "execution_allowed = true",
        "broker_execution_armed = true",
    )

    assert all(token not in section for token in forbidden)


def test_qt004_template_labels_activity_as_non_execution_feed():
    page = TEMPLATE.read_text(encoding="utf-8")

    section_start = page.index('id="recent-broker-activity"')
    section = page[section_start:section_start + 5000]

    assert "ACCOUNT HISTORY" in section
    assert "Execution feed" in section
    assert ">NO<" in section.replace("\n", "").replace(" ", "")



def test_qt004_frontend_state_preserves_recent_broker_activity(
    monkeypatch,
):
    snapshot = {
        "status": "AVAILABLE",
        "balances": {
            "combinedBalances": [],
        },
        "positions": {
            "positions": [],
        },
        "activities": {
            "status": "AVAILABLE",
            "provenance": "QUESTRADE_ACTIVITIES",
            "activities": [
                {
                    "action": "DIV",
                    "symbol": "ENB",
                    "description": "ENBRIDGE INC CASH DIV",
                    "netAmount": 6.91,
                    "currency": "USD",
                    "type": "Dividends",
                }
            ],
            "activity_count": 1,
        },
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }

    monkeypatch.setattr(
        launcher._QUESTRADE_MISSION_CONTROL_CACHE,
        "read",
        lambda: snapshot,
    )

    state = launcher.build_launcher_frontend_state()

    activity = state["recent_broker_activity"]

    assert activity["status"] == "AVAILABLE"
    assert activity["activity_count"] == 1
    assert activity["rows"][0]["symbol"] == "ENB"
    assert activity["rows"][0]["classification"] == "DIVIDEND"

    assert activity["real_time_fill_feed"] is False
    assert activity["portfolio_mutation_authority"] is False
    assert activity["execution_authority"] is False


def test_qt004_mobile_context_receives_recent_broker_activity(
    monkeypatch,
):
    activity = {
        "status": "AVAILABLE",
        "source": "QUESTRADE_ACTIVITIES",
        "activity_count": 1,
        "rows": [
            {
                "classification": "DIVIDEND",
                "symbol": "ENB",
                "description": "ENBRIDGE INC CASH DIV",
                "net_amount": 6.91,
                "currency": "USD",
            }
        ],
        "telemetry_semantics": "ACCOUNT_HISTORY",
        "real_time_fill_feed": False,
        "portfolio_mutation_authority": False,
        "execution_authority": False,
    }

    original = launcher.build_launcher_frontend_state

    def wrapped(*args, **kwargs):
        result = original(*args, **kwargs)
        result["recent_broker_activity"] = dict(activity)
        return result

    monkeypatch.setattr(
        launcher,
        "build_launcher_frontend_state",
        wrapped,
    )

    context = launcher.build_mobile_dashboard_context()

    assert context["recent_broker_activity"] == activity


def test_qt004_real_mobile_route_renders_activity_from_context(
    monkeypatch,
):
    from fastapi.testclient import TestClient

    activity = {
        "status": "AVAILABLE",
        "source": "QUESTRADE_ACTIVITIES",
        "activity_count": 1,
        "rows": [
            {
                "classification": "DIVIDEND",
                "symbol": "ENB",
                "description": "ENBRIDGE INC CASH DIV",
                "net_amount": 6.91,
                "currency": "USD",
            }
        ],
        "telemetry_semantics": "ACCOUNT_HISTORY",
        "real_time_fill_feed": False,
        "portfolio_mutation_authority": False,
        "execution_authority": False,
    }

    original = launcher.build_mobile_dashboard_context

    def wrapped_context():
        context = original()
        context["recent_broker_activity"] = dict(activity)
        return context

    monkeypatch.setattr(
        launcher,
        "build_mobile_dashboard_context",
        wrapped_context,
    )

    with TestClient(launcher.app) as client:
        response = client.get(
            "/mobile",
            headers={
                "x-css-user-id": "qt004-route-test",
                "x-css-role": "SUPER_USER",
            },
        )

    assert response.status_code == 200

    html = response.text

    start = html.index('id="recent-broker-activity"')
    panel = html[start:start + 12000]

    assert "DIVIDEND" in panel
    assert "ENB" in panel
    assert "USD" in panel
    assert "6.91" in panel
    assert "ACCOUNT HISTORY" in panel
    assert "Execution feed" in panel

    lowered = panel.lower()

    assert "submit order" not in lowered
    assert "place order" not in lowered
    assert "/orders" not in lowered
