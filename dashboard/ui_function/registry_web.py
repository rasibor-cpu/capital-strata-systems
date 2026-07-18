"""Desktop web dashboard UI function definitions (Phase 176C)."""

from __future__ import annotations

from dashboard.ui_function.models import CSSUIFunctionDefinition, defn

_WEB_NAV = (
    ("dashboard", "/dashboard", "Dashboard"),
    ("positions", "/positions", "Positions"),
    ("trade", "/trade", "Trade"),
    ("trade_summary", "/trade-summary", "Trade Summary"),
    ("command_centre", "/session-command-centre", "Command Centre"),
    ("live_readiness_certification", "/live-readiness-certification", "Live Cert"),
    ("execution", "/execution", "Execution"),
    ("risk_governance", "/risk-governance", "Risk & Governance"),
    ("market_opportunities", "/market-opportunities", "Market"),
    ("broker", "/broker", "Broker"),
    ("margin", "/margin", "Margin"),
)

_WEB_REFRESH = (
    ("dashboard", "/dashboard", "data-refresh", "GET /api/v1/frontend-state; GET /api/v1/capital-allocation-intelligence"),
    ("positions", "/positions", "data-refresh-positions", "GET /api/v1/frontend-state"),
    ("execution", "/execution", "data-refresh-execution", "GET /api/v1/frontend-state"),
    ("risk_governance", "/risk-governance", "data-refresh-risk-governance", "GET /api/v1/frontend-state"),
    ("trade", "/trade", "data-refresh-trade", "GET /api/v1/frontend-state"),
    ("market_opportunities", "/market-opportunities", "data-refresh-market-opportunities", "GET /api/v1/frontend-state"),
    ("broker", "/broker", "data-refresh-broker", "GET /api/v1/frontend-state"),
    ("margin", "/margin", "data-refresh-margin", "GET /api/v1/margin-snapshot"),
)

WEB_CONTROLS: list[CSSUIFunctionDefinition] = []

for key, route, label in _WEB_NAV:
    WEB_CONTROLS.append(
        defn(
            control_id=f"web.nav.{key}",
            page_id=f"web_{key}",
            section="navigation",
            label=label,
            control_type="nav",
            desktop_route=route,
            expected_action="navigate",
            expected_api=f"GET {route}",
            expected_success_state="http_200_and_active_nav",
            evidence_source="dashboard/web/web_app.py:_app_nav",
            implementation_status="FUNCTIONAL",
            test_id="test_web_nav_functional",
            desktop_mobile="DESKTOP_ONLY",
        )
    )

for page, route, attr, api in _WEB_REFRESH:
    WEB_CONTROLS.append(
        defn(
            control_id=f"web.refresh.{page}",
            page_id=f"web_{page}",
            section="refresh",
            label="Refresh",
            control_type="refresh",
            desktop_route=route,
            expected_action="fetch_and_bind_state",
            expected_service="dashboard.runtime.api_bridge",
            expected_api=api,
            expected_success_state="panels_updated_or_DATA_UNAVAILABLE",
            expected_failure_state="visible_error_or_degraded_indicator",
            evidence_source="dashboard/web/web_app.py",
            implementation_status="FUNCTIONAL",
            test_id="test_web_refresh_apis",
            desktop_mobile="DESKTOP_ONLY",
        )
    )

for cid, label, api in (
    ("web.trade.search", "Trade search", "client_filter"),
    ("web.trade.asset_filter", "Asset class filter", "client_filter"),
    ("web.trade.sort", "Trade sort", "client_filter"),
    ("web.trade.watch_only", "Watchlist only", "localStorage"),
    ("web.trade.watch_toggle", "WATCH/WATCHED", "localStorage"),
):
    WEB_CONTROLS.append(
        defn(
            control_id=cid,
            page_id="web_trade",
            section="filters",
            label=label,
            control_type="filter",
            desktop_route="/trade",
            expected_action="client_side_filter",
            expected_api=api,
            expected_success_state="universe_rerendered",
            evidence_source="dashboard/web/web_app.py:_trade_script",
            implementation_status="FUNCTIONAL",
            test_id="test_web_trade_filters_present",
            desktop_mobile="DESKTOP_ONLY",
            limitation="Client-side only; does not mutate backend state.",
        )
    )

WEB_CONTROLS.extend(
    [
        defn(
            control_id="web.scc.autoload",
            page_id="web_command_centre",
            section="intelligence",
            label="Session Command Centre load",
            control_type="api_action",
            desktop_route="/session-command-centre",
            expected_api="GET /api/v1/session-command-centre",
            expected_service="dashboard.runtime.api_bridge",
            expected_success_state="scores_and_cards_populated",
            implementation_status="FUNCTIONAL",
            test_id="test_web_scc_api",
            desktop_mobile="DESKTOP_ONLY",
        ),
        defn(
            control_id="web.scc.nav_links",
            page_id="web_command_centre",
            section="intelligence",
            label="SCC Navigation Links",
            control_type="link",
            desktop_route="/session-command-centre",
            expected_api="GET /api/v1/session-command-centre",
            expected_action="render_clickable_hrefs",
            expected_success_state="anchor_elements_with_href",
            evidence_source="dashboard/web/web_app.py:_session_command_centre_page",
            implementation_status="FUNCTIONAL",
            test_id="test_web_scc_nav_links_clickable",
            desktop_mobile="DESKTOP_ONLY",
            notes="Repaired in Phase 176C: spans replaced with anchors when href present.",
        ),
        defn(
            control_id="web.live_cert.autoload",
            page_id="web_live_readiness_certification",
            section="certification",
            label="Live readiness load",
            control_type="api_action",
            desktop_route="/live-readiness-certification",
            expected_api="GET /api/v1/live-readiness-certification",
            implementation_status="FUNCTIONAL",
            test_id="test_web_live_cert_api",
            desktop_mobile="DESKTOP_ONLY",
        ),
        defn(
            control_id="web.trade_summary.autoload",
            page_id="web_trade_summary",
            section="summary",
            label="Trade summary load",
            control_type="api_action",
            desktop_route="/trade-summary",
            expected_api="GET /api/v1/trade-summary",
            implementation_status="FUNCTIONAL",
            test_id="test_web_trade_summary_api",
            desktop_mobile="DESKTOP_ONLY",
        ),
    ]
)
