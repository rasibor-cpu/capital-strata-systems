from __future__ import annotations

import copy
import json
import time
from collections.abc import Callable

import dashboard.mobile.mobile_app as mobile_app
from dashboard.mobile.mobile_app import (
    _broker_page as mobile_broker_page,
    _dashboard_page as mobile_dashboard_page,
    _login_page as mobile_login_page,
    _positions_page as mobile_positions_page,
    _trade_ticket_page as mobile_trade_ticket_page,
)
from dashboard.runtime.dashboard_hydration_coordinator import (
    DashboardHydrationCoordinator,
)
from dashboard.runtime.frontend_contract import (
    build_frontend_payload,
    build_websocket_delta,
)
from dashboard.runtime.runtime_smoke_test import build_smoke_payloads
from dashboard.web.web_app import (
    _broker_page,
    _dashboard_page,
    _execution_page,
    _market_opportunities_page,
    _positions_page,
    _risk_governance_page,
    _trade_page,
)


PAYLOAD_BUDGET_MS = 100.0
WEBSOCKET_DELTA_BUDGET_MS = 100.0
HTML_PAGE_BUDGET_MS = 100.0
MOBILE_PAGE_BUDGET_MS = 150.0
FRONTEND_PAYLOAD_MAX_BYTES = 64 * 1024
WEBSOCKET_DELTA_MAX_BYTES = 16 * 1024
HTML_PAGE_MAX_BYTES = 512 * 1024


def _elapsed_ms(factory: Callable[[], object]) -> tuple[object, float]:
    started = time.perf_counter()
    value = factory()
    return value, (time.perf_counter() - started) * 1000


def _json_size(payload: object) -> int:
    return len(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def _assert_under_budget(name: str, elapsed_ms: float, budget_ms: float) -> None:
    assert elapsed_ms < budget_ms, (
        f"{name} exceeded performance budget: "
        f"{elapsed_ms:.2f}ms >= {budget_ms:.2f}ms"
    )


def _assert_size(name: str, size_bytes: int, max_bytes: int) -> None:
    assert size_bytes < max_bytes, (
        f"{name} exceeded size budget: {size_bytes} bytes >= {max_bytes} bytes"
    )


def _smoke_state(payloads: dict | None = None):
    return DashboardHydrationCoordinator().hydrate(
        **(payloads if payloads is not None else build_smoke_payloads())
    )


def test_frontend_payload_generation_stays_fast_and_compact() -> None:
    state = _smoke_state()

    # Warm the deterministic bridge once so import/setup cost is not measured.
    build_frontend_payload(state)

    payload, elapsed_ms = _elapsed_ms(lambda: build_frontend_payload(state))

    _assert_under_budget("frontend payload generation", elapsed_ms, PAYLOAD_BUDGET_MS)
    _assert_size("frontend payload", _json_size(payload), FRONTEND_PAYLOAD_MAX_BYTES)
    assert payload["source_metadata"]["frontend_safe"] is True
    assert payload["source_metadata"]["secrets_redacted"] is True
    assert "sections" in payload
    assert "portfolio_summary" in payload["sections"]
    assert "portfolio_greeks" in payload["sections"]


def test_websocket_delta_generation_is_incremental_and_compact() -> None:
    previous_payload = build_frontend_payload(_smoke_state())
    updated_payloads = copy.deepcopy(build_smoke_payloads())
    updated_payloads["execution_payload"]["accepted_trade_count"] = 3
    updated_payloads["execution_payload"]["last_execution_event"] = (
        "Performance smoke execution delta"
    )
    current_payload = build_frontend_payload(_smoke_state(updated_payloads))

    delta, elapsed_ms = _elapsed_ms(
        lambda: build_websocket_delta(
            previous_payload,
            current_payload,
            sequence=2,
            sections=("execution", "risk", "positions", "broker"),
        )
    )

    _assert_under_budget(
        "websocket delta generation",
        elapsed_ms,
        WEBSOCKET_DELTA_BUDGET_MS,
    )
    _assert_size("websocket delta", _json_size(delta), WEBSOCKET_DELTA_MAX_BYTES)
    assert delta["changed_sections"] == ["execution"]
    assert set(delta["data"]) == {"execution"}
    assert "account_summary" not in delta["data"]


def test_web_pages_render_within_html_budget() -> None:
    web_pages: dict[str, Callable[[], str]] = {
        "dashboard": _dashboard_page,
        "positions": _positions_page,
        "trade": _trade_page,
        "execution": _execution_page,
        "risk_governance": _risk_governance_page,
        "market_opportunities": _market_opportunities_page,
        "broker": _broker_page,
    }

    for name, render in web_pages.items():
        render()
        html, elapsed_ms = _elapsed_ms(render)

        _assert_under_budget(f"web {name} page render", elapsed_ms, HTML_PAGE_BUDGET_MS)
        _assert_size(f"web {name} html", len(html.encode("utf-8")), HTML_PAGE_MAX_BYTES)
        assert "/api/v1/frontend-state" in html


def test_mobile_pages_render_within_html_budget(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(mobile_app, "MOBILE_EVENTS_FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(mobile_app, "MOBILE_CONTROL_FILE", tmp_path / "controls.json")
    monkeypatch.setattr(mobile_app, "load_local_env", lambda: None)
    
    mobile_app.save_mobile_controls({"mobile_trading_mode": "MOBILE_LIVE_TRADING_ARMED"})
    user_ctx = {
        "user_id": "00017",
        "display_name": "CSS Trader",
        "role": "TRADER",
    }
    session = {"created": 1.0}
    mobile_pages: dict[str, Callable[[], str]] = {
        "login": mobile_login_page,
        "dashboard": lambda: mobile_dashboard_page(user_ctx, session),
        "positions": lambda: mobile_positions_page(user_ctx, session),
        "broker": lambda: mobile_broker_page(user_ctx, session),
        "trade": lambda: mobile_trade_ticket_page(user_ctx),
    }

    for name, render in mobile_pages.items():
        render()
        html, elapsed_ms = _elapsed_ms(render)

        _assert_under_budget(
            f"mobile {name} page render",
            elapsed_ms,
            MOBILE_PAGE_BUDGET_MS,
        )
        _assert_size(
            f"mobile {name} html",
            len(html.encode("utf-8")),
            HTML_PAGE_MAX_BYTES,
        )
        assert "Capital Strata Systems" in html or "CSS" in html
