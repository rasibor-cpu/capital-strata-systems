from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse

from dashboard.runtime.api_bridge import (
    DashboardStateProvider,
    create_dashboard_state_router,
)
from dashboard.runtime.dashboard_hydration_coordinator import (
    DashboardHydrationCoordinator,
)
from dashboard.runtime.dashboard_state import DashboardState
from dashboard.runtime.runtime_smoke_test import build_smoke_payloads
from dashboard.runtime.ws_bridge import create_ws_router
from dashboard.mission_control.host_registration import register_mission_control
from backend.executive_intelligence.distribution_routes import create_executive_brief_distribution_router
from backend.reports_center.routes import create_reports_center_router
from backend.common.branding import get_brand_service


BRAND = get_brand_service()


def demo_dashboard_state_provider() -> DashboardState:
    """
    Build a read-only demo DashboardState for standalone web dashboard access.

    Production/live integrations should pass an injected state provider instead
    of adding direct broker access to this web layer.
    """

    return DashboardHydrationCoordinator().hydrate(**build_smoke_payloads())


def create_app(
    state_provider: DashboardStateProvider | None = None,
) -> FastAPI:
    provider = state_provider or demo_dashboard_state_provider
    app = FastAPI(
        title=f"{BRAND.organization_name} Institutional Web Dashboard",
        version="0.1.0",
    )
    app.include_router(create_dashboard_state_router(provider))
    app.include_router(create_ws_router(provider))
    register_mission_control(app, provider if state_provider is not None else None)
    app.include_router(create_executive_brief_distribution_router())
    app.include_router(create_reports_center_router())

    @app.get("/", include_in_schema=False)
    async def index() -> RedirectResponse:
        return RedirectResponse("/dashboard", status_code=303)

    @app.get("/manifest.webmanifest")
    async def manifest() -> JSONResponse:
        return JSONResponse(
            BRAND.manifest(),
            media_type="application/manifest+json",
        )

    @app.get("/favicon.ico")
    async def favicon() -> FileResponse:
        return _brand_file("favicon")

    @app.get("/favicon-16x16.png")
    async def favicon_16() -> FileResponse:
        return _brand_file("favicon_16")

    @app.get("/favicon-32x32.png")
    async def favicon_32() -> FileResponse:
        return _brand_file("favicon_32")

    @app.get("/apple-touch-icon.png")
    @app.get("/static/apple_touch_icon_180.png")
    async def apple_touch_icon() -> FileResponse:
        return _brand_file("apple_touch")

    @app.get("/static/css_pwa_icon_192.png")
    async def css_pwa_icon_192() -> FileResponse:
        return _brand_file("icon_192")

    @app.get("/static/css_pwa_icon_512.png")
    async def css_pwa_icon_512() -> FileResponse:
        return _brand_file("icon_512")

    @app.get("/pwa/{filename}")
    async def canonical_pwa_icon(filename: str) -> FileResponse:
        file_to_key = {
            BRAND.asset(key).filename: key
            for key in ("icon_192", "icon_512", "maskable_192", "maskable_512")
        }
        asset_key = file_to_key.get(filename)
        if asset_key is None:
            raise HTTPException(status_code=404, detail="pwa_asset_not_found")
        return _brand_file(asset_key)

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard() -> HTMLResponse:
        return HTMLResponse(_dashboard_page())

    @app.get("/positions", response_class=HTMLResponse)
    async def positions() -> HTMLResponse:
        return HTMLResponse(_positions_page())

    @app.get("/trade", response_class=HTMLResponse)
    async def trade() -> HTMLResponse:
      return HTMLResponse(_trade_page())

    @app.get("/trade-summary", response_class=HTMLResponse)
    async def trade_summary() -> HTMLResponse:
        return HTMLResponse(_trade_summary_page())

    @app.get("/session-command-centre", response_class=HTMLResponse)
    async def session_command_centre() -> HTMLResponse:
        return HTMLResponse(_session_command_centre_page())

    @app.get("/live-readiness-certification", response_class=HTMLResponse)
    async def live_readiness_certification() -> HTMLResponse:
        return HTMLResponse(_live_readiness_certification_page())

    @app.get("/execution", response_class=HTMLResponse)
    async def execution() -> HTMLResponse:
        return HTMLResponse(_execution_page())

    @app.get("/risk-governance", response_class=HTMLResponse)
    async def risk_governance() -> HTMLResponse:
        return HTMLResponse(_risk_governance_page())

    @app.get("/market-opportunities", response_class=HTMLResponse)
    async def market_opportunities() -> HTMLResponse:
        return HTMLResponse(_market_opportunities_page())

    @app.get("/broker", response_class=HTMLResponse)
    async def broker() -> HTMLResponse:
        return HTMLResponse(_broker_page())

    @app.get("/margin", response_class=HTMLResponse)
    async def margin_view() -> HTMLResponse:
        return HTMLResponse(_margin_page())

    @app.get("/api/v1/margin-snapshot")
    async def margin_api() -> dict[str, Any]:
        state = provider()
        summary = state.last_scan_results.get("account_summary", {})
        broker = str(summary.get("broker", "NONE")).upper()
        mode = str(summary.get("account_mode", "SIMULATED")).upper()
        
        snapshot = None
        try:
            if broker == "OANDA":
                from engine.risk.oanda_margin_adapter import OandaMarginAdapter
                snapshot = OandaMarginAdapter(mode=mode).get_margin_snapshot()
            elif broker == "COINBASE":
                from engine.risk.coinbase_margin_adapter import CoinbaseMarginAdapter
                snapshot = CoinbaseMarginAdapter(mode=mode).get_margin_snapshot()
        except Exception:
            pass

        if not snapshot:
            return {"ok": False, "status": "DATA_UNAVAILABLE"}

        margin_state_val = getattr(snapshot, "margin_state", "UNKNOWN")
        if hasattr(margin_state_val, "value"):
            margin_state_val = margin_state_val.value
        else:
            margin_state_val = str(margin_state_val)

        return {
            "ok": True,
            "broker": str(getattr(snapshot, "broker", "UNKNOWN")),
            "account_id": str(getattr(snapshot, "account_id", "UNKNOWN")),
            "equity": float(getattr(snapshot, "equity", 0.0)),
            "cash": float(getattr(snapshot, "cash", 0.0)),
            "buying_power": float(getattr(snapshot, "buying_power", 0.0)),
            "maintenance_margin": float(getattr(snapshot, "maintenance_margin", 0.0)),
            "initial_margin": float(getattr(snapshot, "initial_margin", 0.0)),
            "margin_used": float(getattr(snapshot, "margin_used", 0.0)),
            "margin_available": float(getattr(snapshot, "margin_available", 0.0)),
            "margin_ratio": float(getattr(snapshot, "margin_ratio", 0.0)),
            "margin_state": margin_state_val,
            "timestamp": str(getattr(snapshot, "timestamp", "UNKNOWN")),
        }


    @app.get("/health")
    async def health() -> dict[str, Any]:
        state = provider()
        return {
            "ok": True,
            "session_id": state.session_id,
            "resolved_mode": state.resolved_mode(),
            "engine_mode": state.engine_mode,
        }

    return app


def _app_nav(active: str) -> str:
    links = [
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
    ]

    return "\n".join(
        (
            '<nav class="app-nav" aria-label="Web dashboard navigation">',
            *(
                (
                    f'<a href="{href}" class="{"active" if key == active else ""}">'
                    f"{label}</a>"
                )
                for key, href, label in links
            ),
            "</nav>",
        )
    )


def _brand_file(asset_key: str) -> FileResponse:
    asset = BRAND.asset(asset_key)
    return FileResponse(
        BRAND.asset_path(asset_key),
        media_type=asset.media_type,
        headers={
            "Cache-Control": "public, max-age=86400, immutable",
            "X-CSS-PWA-Version": BRAND.asset_version,
        },
    )


def _icon_links() -> str:
    return BRAND.html_head(
        manifest_href="/manifest.webmanifest",
        include_viewport=False,
    )


def _dashboard_page() -> str:
    panel_ids = json.dumps(
        [
            "account_summary",
            "pnl_summary",
            "positions",
        "portfolio_summary",
        "portfolio_greeks",
            "risk",
            "governance",
            "market",
            "execution",
            "broker",
            "opportunities",
            "capital_allocation_intelligence",
            "institutional_investment_committee",
            "analytics",
        ]
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>CSS Institutional Web Dashboard</title>
  {_icon_links()}
  <style>{_css()}</style>
</head>
<body><div style="background-color:#ffebee;color:#b71c1c;text-align:center;padding:8px;font-weight:bold;font-size:0.85em;border-bottom:1px solid #b71c1c;" aria-label="Risk Warning">Trading involves substantial risk. Loss of capital may occur. Past performance does not guarantee future results.</div>
  <main class="shell">
    <header class="topbar">
      <div class="brand-lockup">
        <div class="brand-mark" aria-hidden="true">CSS</div>
        <div>
          <p class="eyebrow">Capital Strata Systems</p>
          <h1>Institutional Web Dashboard</h1>
        </div>
      </div>
      <section class="status-strip" aria-label="System status">
        <span id="status-mode">System PAPER</span>
        <span id="status-engine">Engine SAFE</span>
        <span id="status-session">Session pending</span>
        <span id="status-ws">WebSocket connecting</span>
      </section>
    </header>

    <section class="control-row" aria-label="Dashboard controls">
      <button type="button" data-refresh>Refresh</button>
      <span>DashboardState bridge</span>
      <span>Read-only web surface</span>
      <span>No frontend broker access</span>
    </section>
    {_app_nav("dashboard")}

    <section class="metric-band" aria-label="Pilot safety controls">
      <article id="live-capital-banner">
        <strong>LIVE CAPITAL ACTIVE</strong>
        <span>Operational pilot safeguards enabled</span>
      </article>
      <article id="operational-identity-strip">
        <strong>Operational Identity</strong>
        <span>LIVE CAPITAL ACTIVE</span>
      </article>
      <article id="reconciliation-visibility-panel">
        <strong>Reconciliation Visibility</strong>
        <span>Broker reconciliation surfaced</span>
      </article>
      <article id="kill-switch-panel">
        <strong>Kill Switch</strong>
        <span>Global live-order kill switch monitored</span>
      </article>
    </section>

    <section class="metric-band" aria-label="Opportunity scoring governance">
      <article>
        <strong>Top Ranked</strong>
        <span data-value="opportunities.scoring_overview.top_ranked_symbols.0">N/A</span>
      </article>
      <article>
        <strong>Top Composite</strong>
        <span data-value="opportunities.scoring_overview.top_composite_scores.0">0.00</span>
      </article>
      <article>
        <strong>Best Adjusted Edge</strong>
        <span data-value="opportunities.scoring_overview.best_adjusted_edge">0.00</span>
      </article>
      <article>
        <strong>Avg Execution Quality</strong>
        <span data-value="opportunities.scoring_overview.average_execution_quality">0.00</span>
      </article>
      <article>
        <strong>Top Survivability</strong>
        <span data-value="opportunities.scoring_overview.highest_survivability_symbols.0">N/A</span>
      </article>
    </section>

    <section class="metric-band" aria-label="Profitability edge analytics">
      <article>
        <strong>Expectancy</strong>
        <span data-value="analytics.expectancy">0.00</span>
      </article>
      <article>
        <strong>Profit Factor</strong>
        <span data-value="analytics.profit_factor">0.00</span>
      </article>
      <article>
        <strong>Estimated Exec Costs</strong>
        <span data-value="analytics.estimated_execution_cost">$0.00</span>
      </article>
      <article>
        <strong>Signal Quality</strong>
        <span data-value="analytics.signal_quality">0.00</span>
      </article>
      <article>
        <strong>Current Edge Estimate</strong>
        <span data-value="analytics.current_edge_estimate">0.00</span>
      </article>
      <article>
        <strong>Drawdown State</strong>
        <span data-value="analytics.drawdown_state">0.00</span>
      </article>
    </section>

    <section class="metric-band" aria-label="Capital allocation intelligence">
      <article>
        <strong>Shadow Capital Used</strong>
        <span data-value="capital_allocation_intelligence.allocation_summary.capital_used">$0.00</span>
      </article>
      <article>
        <strong>Cash Allocation</strong>
        <span data-value="capital_allocation_intelligence.cash_allocation">$0.00</span>
      </article>
      <article>
        <strong>Unused Capital</strong>
        <span data-value="capital_allocation_intelligence.unused_capital">$0.00</span>
      </article>
      <article>
        <strong>Portfolio Diversification</strong>
        <span data-value="capital_allocation_intelligence.portfolio_diversification">0.00</span>
      </article>
      <article>
        <strong>Expected Return</strong>
        <span data-value="capital_allocation_intelligence.expected_return">0.00</span>
      </article>
      <article>
        <strong>Expected Risk</strong>
        <span data-value="capital_allocation_intelligence.expected_risk">0.00</span>
      </article>
      <article>
        <strong>Confidence</strong>
        <span data-value="capital_allocation_intelligence.confidence">0.00</span>
      </article>
    </section>

    <section class="metric-band" aria-label="Institutional investment committee">
      <article>
        <strong>Committee Score</strong>
        <span data-value="institutional_investment_committee.committee_score">0.00</span>
      </article>
      <article>
        <strong>Committee Decision</strong>
        <span data-value="institutional_investment_committee.decision">WAIT</span>
      </article>
      <article>
        <strong>Capital Rank</strong>
        <span data-value="institutional_investment_committee.capital_rank">0</span>
      </article>
      <article>
        <strong>Expected Drawdown</strong>
        <span data-value="institutional_investment_committee.expected_drawdown">0.00</span>
      </article>
      <article>
        <strong>Confidence</strong>
        <span data-value="institutional_investment_committee.confidence">0.00</span>
      </article>
      <article>
        <strong>Capital Efficiency</strong>
        <span data-value="institutional_investment_committee.capital_efficiency">0.00</span>
      </article>
      <article>
        <strong>Consensus Score</strong>
        <span data-value="institutional_investment_committee.consensus_score">0.00</span>
      </article>
      <article>
        <strong>Consensus</strong>
        <span data-value="institutional_investment_committee.consensus">NO_VOTES</span>
      </article>
    </section>

    <section class="metric-band" aria-label="Account overview">
      <article>
        <strong>Cash Balance</strong>
        <span data-value="account_summary.cash_balance">$0.00</span>
      </article>
      <article>
        <strong>Total Equity</strong>
        <span data-value="account_summary.total_equity">$0.00</span>
      </article>
      <article>
        <strong>Net PnL</strong>
        <span data-value="pnl_summary.net_pnl">$0.00</span>
      </article>
      <article>
        <strong>Exposure</strong>
        <span data-value="pnl_summary.total_exposure">$0.00</span>
      </article>
      <article>
        <strong>Risk State</strong>
        <span data-value="risk.risk_state">NORMAL</span>
      </article>
      <article>
        <strong>Execution</strong>
        <span data-value="execution.execution_state">IDLE</span>
      </article>
    </section>

    <section class="metric-band" aria-label="Portfolio and Greeks overview">
      <article>
        <strong>Portfolio Health</strong>
        <span data-value="portfolio_summary.portfolio_health">STABLE</span>
      </article>
      <article>
        <strong>Total Exposure</strong>
        <span data-value="portfolio_summary.total_exposure">$0.00</span>
      </article>
      <article>
        <strong>Available Capital</strong>
        <span data-value="portfolio_summary.available_capital">$0.00</span>
      </article>
      <article>
        <strong>Portfolio Delta</strong>
        <span data-value="portfolio_greeks.net_delta">0.00</span>
      </article>
      <article>
        <strong>Portfolio Gamma</strong>
        <span data-value="portfolio_greeks.net_gamma">0.00</span>
      </article>
      <article>
        <strong>Greeks Status</strong>
        <span data-value="portfolio_greeks.greeks_status">NO_OPTIONS</span>
      </article>
    </section>

    <section class="dashboard-grid" aria-label="Institutional dashboard panels">
      <article class="panel wide" data-panel="account_summary">
        <div class="panel-head">
          <h2>Account Overview</h2>
          <span data-value="account_summary.currency">USD</span>
        </div>
        <div class="kv-grid">
          <div><strong>Broker</strong><span data-value="account_summary.broker">NONE</span></div>
          <div><strong>Mode</strong><span data-value="account_summary.account_mode">paper</span></div>
          <div><strong>Buying Power</strong><span data-value="account_summary.buying_power">$0.00</span></div>
          <div><strong>Margin Used</strong><span data-value="account_summary.margin_used">$0.00</span></div>
          <div><strong>Available Margin</strong><span data-value="account_summary.available_margin">$0.00</span></div>
          <div><strong>Win Rate</strong><span data-value="pnl_summary.win_rate_pct">0.00%</span></div>
        </div>
      </article>

      <article class="panel" data-panel="positions">
        <div class="panel-head">
          <h2>Live Positions</h2>
          <span data-value="positions.total">0</span>
        </div>
        <div class="table" id="positions-table"></div>
      </article>

      <article class="panel" data-panel="portfolio_summary">
        <div class="panel-head">
          <h2>Portfolio Summary</h2>
          <span data-value="portfolio_summary.portfolio_status">NO_POSITIONS</span>
        </div>
        <div class="kv-grid two">
          <div><strong>Total Exposure</strong><span data-value="portfolio_summary.total_exposure">$0.00</span></div>
          <div><strong>Cash</strong><span data-value="portfolio_summary.cash">$0.00</span></div>
          <div><strong>Equity</strong><span data-value="portfolio_summary.equity">$0.00</span></div>
          <div><strong>Available Capital</strong><span data-value="portfolio_summary.available_capital">$0.00</span></div>
          <div><strong>Allocated Capital</strong><span data-value="portfolio_summary.allocated_capital">$0.00</span></div>
          <div><strong>Reserved Capital</strong><span data-value="portfolio_summary.reserved_capital">$0.00</span></div>
          <div><strong>Diversification Score</strong><span data-value="portfolio_summary.diversification_score">0.00</span></div>
          <div><strong>Risk Score</strong><span data-value="portfolio_summary.risk_score">0.00</span></div>
          <div><strong>Capital Efficiency</strong><span data-value="portfolio_summary.capital_efficiency">0.00%</span></div>
          <div><strong>Correlation Score</strong><span data-value="portfolio_summary.correlation_score">0.00</span></div>
          <div><strong>Concentration Score</strong><span data-value="portfolio_summary.concentration_score">0.00</span></div>
          <div><strong>Portfolio Health</strong><span data-value="portfolio_summary.portfolio_health">STABLE</span></div>
        </div>
      </article>

      <article class="panel" data-panel="portfolio_greeks">
        <div class="panel-head">
          <h2>Portfolio Greeks</h2>
          <span data-value="portfolio_greeks.greeks_status">NO_OPTIONS</span>
        </div>
        <div class="kv-grid two">
          <div><strong>Delta</strong><span data-value="portfolio_greeks.delta">0.00</span></div>
          <div><strong>Gamma</strong><span data-value="portfolio_greeks.gamma">0.00</span></div>
          <div><strong>Theta</strong><span data-value="portfolio_greeks.theta">0.00</span></div>
          <div><strong>Vega</strong><span data-value="portfolio_greeks.vega">0.00</span></div>
          <div><strong>Rho</strong><span data-value="portfolio_greeks.rho">0.00</span></div>
          <div><strong>Net Delta</strong><span data-value="portfolio_greeks.net_delta">0.00</span></div>
          <div><strong>Net Gamma</strong><span data-value="portfolio_greeks.net_gamma">0.00</span></div>
          <div><strong>Net Theta</strong><span data-value="portfolio_greeks.net_theta">0.00</span></div>
          <div><strong>Net Vega</strong><span data-value="portfolio_greeks.net_vega">0.00</span></div>
          <div><strong>Net Rho</strong><span data-value="portfolio_greeks.net_rho">0.00</span></div>
          <div><strong>Options Exposure</strong><span data-value="portfolio_greeks.options_exposure">$0.00</span></div>
          <div><strong>Underlying Exposure</strong><span data-value="portfolio_greeks.underlying_exposure">$0.00</span></div>
          <div><strong>Hedge Ratio</strong><span data-value="portfolio_greeks.hedge_ratio">0.00</span></div>
          <div><strong>Source</strong><span data-value="portfolio_greeks.source">position_state</span></div>
        </div>
      </article>

      <article class="panel" data-panel="risk">
        <div class="panel-head">
          <h2>Risk Control Center</h2>
          <span data-value="risk.gate_status">OPEN</span>
        </div>
        <div class="kv-grid two">
          <div><strong>Exposure Utilization</strong><span data-value="risk.exposure_utilization_pct">0.00%</span></div>
          <div><strong>Current Drawdown</strong><span data-value="risk.current_drawdown_pct">0.00%</span></div>
          <div><strong>Daily Loss Limit</strong><span data-value="risk.daily_loss_limit">$0.00</span></div>
          <div><strong>Position Limit</strong><span data-value="risk.position_limit">0</span></div>
        </div>
        <ul class="compact-list" id="risk-breaches"></ul>
      </article>

      <article class="panel" data-panel="governance">
        <div class="panel-head">
          <h2>Governance Center</h2>
          <span id="governance-ready">READY</span>
        </div>
        <div class="toggle-grid">
          <span data-flag="governance.governance_enabled">Governance</span>
          <span data-flag="governance.session_locked">Session Lock</span>
          <span data-flag="governance.defensive_mode_active">Defensive</span>
          <span data-flag="governance.unified_trade_gate_active">Unified Gate</span>
        </div>
        <p class="panel-note" data-value="governance.last_governance_event">No governance event</p>
      </article>

      <article class="panel wide" data-panel="market">
        <div class="panel-head">
          <h2>Market Regime Panel</h2>
          <span data-value="market.regime_state">UNKNOWN</span>
        </div>
        <div class="signal-grid">
          <div><strong>Trend</strong><span data-value="market.trend_state">UNKNOWN</span></div>
          <div><strong>Volatility</strong><span data-value="market.volatility_state">UNKNOWN</span></div>
          <div><strong>Liquidity</strong><span data-value="market.liquidity_state">UNKNOWN</span></div>
          <div><strong>Momentum</strong><span data-value="market.momentum_state">UNKNOWN</span></div>
          <div><strong>Pressure</strong><span data-value="market.pressure_state">UNKNOWN</span></div>
          <div><strong>Spread</strong><span data-value="market.spread_state">UNKNOWN</span></div>
          <div><strong>VWAP State</strong><span data-value="market.vwap_state">UNKNOWN</span></div>
          <div><strong>Confluence</strong><span data-value="market.signal_confluence_state">UNKNOWN</span></div>
        </div>
      </article>

      <article class="panel" data-panel="execution">
        <div class="panel-head">
          <h2>Execution Center</h2>
          <span data-value="execution.execution_cost_state">UNKNOWN</span>
        </div>
        <div class="kv-grid two">
          <div><strong>Accepted</strong><span data-value="execution.accepted_trade_count">0</span></div>
          <div><strong>Rejected</strong><span data-value="execution.rejected_trade_count">0</span></div>
          <div><strong>Pending</strong><span data-value="execution.pending_trade_count">0</span></div>
          <div><strong>Total Cost</strong><span data-value="execution.total_execution_cost">$0.00</span></div>
        </div>
        <p class="panel-note" data-value="execution.last_execution_event">No execution event</p>
      </article>

      <article class="panel" data-panel="broker">
        <div class="panel-head">
          <h2>Broker Control Panel</h2>
          <span data-value="broker.broker_mode">paper</span>
        </div>
        <div class="kv-grid two">
          <div><strong>Selected</strong><span data-value="broker.selected_broker">NONE</span></div>
          <div><strong>Connected</strong><span data-bool="broker.connected">NO</span></div>
          <div><strong>Live Trading</strong><span data-bool="broker.live_trading_enabled">NO</span></div>
          <div><strong>Heartbeat</strong><span data-value="broker.last_heartbeat">NONE</span></div>
        </div>
      </article>

      <article class="panel" data-panel="opportunities">
        <div class="panel-head">
          <h2>Opportunity Monitor</h2>
          <span data-value="opportunities.count">0</span>
        </div>
        <div class="empty-state" id="opportunities-list">No active opportunities</div>
      </article>

      <article class="panel wide" data-panel="capital_allocation_intelligence">
        <div class="panel-head">
          <h2>Capital Allocation Intelligence</h2>
          <span data-value="capital_allocation_intelligence.allocation_summary.allocated_opportunity_count">0</span>
        </div>
        <div class="kv-grid two">
          <div><strong>Capital Used</strong><span data-value="capital_allocation_intelligence.allocation_summary.capital_used">$0.00</span></div>
          <div><strong>Capital Remaining</strong><span data-value="capital_allocation_intelligence.allocation_summary.capital_remaining">$0.00</span></div>
          <div><strong>Cash Reserve</strong><span data-value="capital_allocation_intelligence.allocation_summary.cash_reserve">$0.00</span></div>
          <div><strong>Deployable Capital</strong><span data-value="capital_allocation_intelligence.allocation_summary.deployable_capital">$0.00</span></div>
          <div><strong>Expected Return</strong><span data-value="capital_allocation_intelligence.expected_return">0.00</span></div>
          <div><strong>Expected Risk</strong><span data-value="capital_allocation_intelligence.expected_risk">0.00</span></div>
          <div><strong>Portfolio Diversification</strong><span data-value="capital_allocation_intelligence.portfolio_diversification">0.00</span></div>
          <div><strong>Confidence</strong><span data-value="capital_allocation_intelligence.confidence">0.00</span></div>
        </div>
        <div class="table" id="capital-allocation-list"></div>
        <ul class="compact-list" id="capital-allocation-warnings"></ul>
      </article>

      <article class="panel wide" data-panel="institutional_investment_committee">
        <div class="panel-head">
          <h2>Institutional Investment Committee</h2>
          <span data-value="institutional_investment_committee.decision">WAIT</span>
        </div>
        <div class="kv-grid two">
          <div><strong>Committee Score</strong><span data-value="institutional_investment_committee.committee_score">0.00</span></div>
          <div><strong>Capital Rank</strong><span data-value="institutional_investment_committee.capital_rank">0</span></div>
          <div><strong>Expected Return</strong><span data-value="institutional_investment_committee.expected_return">0.00</span></div>
          <div><strong>Expected Drawdown</strong><span data-value="institutional_investment_committee.expected_drawdown">0.00</span></div>
          <div><strong>Confidence</strong><span data-value="institutional_investment_committee.confidence">0.00</span></div>
          <div><strong>Capital Efficiency</strong><span data-value="institutional_investment_committee.capital_efficiency">0.00</span></div>
          <div><strong>Opportunity Rank</strong><span data-value="institutional_investment_committee.opportunity_rank">0</span></div>
          <div><strong>Consensus Score</strong><span data-value="institutional_investment_committee.consensus_score">0.00</span></div>
          <div><strong>Consensus</strong><span data-value="institutional_investment_committee.consensus">NO_VOTES</span></div>
          <div><strong>Recommendation</strong><span data-value="institutional_investment_committee.committee_recommendation">No committee recommendation available.</span></div>
        </div>
        <div class="table" id="committee-opportunity-list"></div>
        <div class="table" id="committee-vote-list"></div>
      </article>
    </section>
  </main>

  <script>
    const PANEL_IDS = {panel_ids};
    const state = {{ payload: null, sections: {{}} }};

    function money(value) {{
      return new Intl.NumberFormat("en-US", {{ style: "currency", currency: "USD" }}).format(Number(value || 0));
    }}

    function pct(value) {{
      return `${{Number(value || 0).toFixed(2)}}%`;
    }}

    function get(path) {{
      const parts = path.split(".");
      let value = state.sections?.[parts.shift()];
      for (const part of parts) {{
        if (value === null || value === undefined) return undefined;
        value = value?.[part];
      }}
      return value;
    }}

    function formatField(path, value) {{
      if (["cash_balance", "total_equity", "buying_power", "margin_used", "available_margin", "net_pnl", "total_exposure", "daily_loss_limit", "total_execution_cost", "cash", "equity", "available_capital", "allocated_capital", "reserved_capital", "options_exposure", "underlying_exposure", "capital_used", "capital_remaining", "cash_reserve", "deployable_capital", "cash_allocation", "unused_capital"].some((key) => path.endsWith(key))) {{
        return money(value);
      }}
      if (["win_rate_pct", "exposure_utilization_pct", "current_drawdown_pct", "capital_efficiency"].some((key) => path.endsWith(key))) {{
        return pct(value);
      }}
      if (value === true) return "YES";
      if (value === false) return "NO";
      if (value === null || value === undefined || value === "") return "NONE";
      return String(value);
    }}

    function escapeHtml(value) {{
      return String(value ?? "").replace(/[&<>"']/g, (char) => ({{
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "\\"": "&quot;",
        "'": "&#39;"
      }}[char]));
    }}

    function render(payload) {{
      state.payload = payload;
      state.sections = payload.sections || {{}};
      const session = payload.session || {{}};
      const mode = String(payload.resolved_mode || session.resolved_mode || "paper").toUpperCase();
      document.getElementById("status-mode").textContent = `System ${{mode}}`;
      document.getElementById("status-engine").textContent = `Engine ${{session.engine_mode || "SAFE"}}`;
      document.getElementById("status-session").textContent = `Session ${{payload.session_id || session.session_id || "pending"}}`;

      document.querySelectorAll("[data-value]").forEach((node) => {{
        const path = node.getAttribute("data-value");
        node.textContent = formatField(path, get(path));
      }});
      document.querySelectorAll("[data-bool]").forEach((node) => {{
        const value = get(node.getAttribute("data-bool"));
        node.textContent = value ? "YES" : "NO";
      }});
      document.querySelectorAll("[data-flag]").forEach((node) => {{
        const value = Boolean(get(node.getAttribute("data-flag")));
        node.classList.toggle("on", value);
        node.classList.toggle("off", !value);
      }});

      renderPositions();
      renderRiskBreaches();
      renderOpportunities();
      renderCapitalAllocation();
      renderCommittee();
    }}

    function renderPositions() {{
      const positions = state.sections.positions || {{}};
      const table = document.getElementById("positions-table");
      const items = positions.items || [];
      const rows = items.length ? items : Object.entries(positions.by_asset || {{}}).map(([asset_class, open_positions]) => ({{ asset_class, open_positions }}));
      if (!rows.length) {{
        table.innerHTML = `<div class="empty-state">No open positions</div>`;
        return;
      }}
      table.innerHTML = `
        <div class="row head"><span>Asset</span><span>Open</span><span>Realized</span><span>Unrealized</span><span>Exposure</span></div>
        ${{rows.map((row) => `
          <div class="row">
            <span>${{escapeHtml(row.asset_class || "UNKNOWN")}}</span>
            <span>${{row.open_positions || 0}}</span>
            <span>${{money(row.realized_pnl || 0)}}</span>
            <span>${{money(row.unrealized_pnl || 0)}}</span>
            <span>${{money(row.exposure || 0)}}</span>
          </div>
        `).join("")}}
      `;
    }}

    function renderRiskBreaches() {{
      const list = document.getElementById("risk-breaches");
      const breaches = state.sections.risk?.risk_limits_breached || [];
      list.innerHTML = breaches.length ? breaches.map((item) => `<li>${{escapeHtml(item)}}</li>`).join("") : "<li>NONE</li>";
    }}

    function renderOpportunities() {{
      const target = document.getElementById("opportunities-list");
      const items = state.sections.opportunities?.items || [];
      target.innerHTML = items.length ? items.map((item) => `<div>${{escapeHtml(JSON.stringify(item))}}</div>`).join("") : "No active opportunities";
    }}

    function renderCapitalAllocation() {{
      const section = state.sections.capital_allocation_intelligence || {{}};
      const target = document.getElementById("capital-allocation-list");
      const warnings = document.getElementById("capital-allocation-warnings");
      const plan = section.capital_plan || [];
      target.innerHTML = plan.length ? `
        <div class="row head"><span>Rank</span><span>Asset</span><span>Broker</span><span>Capital</span><span>Score</span></div>
        ${{plan.map((row) => `
          <div class="row">
            <span>${{escapeHtml(row.rank || "")}}</span>
            <span>${{escapeHtml(row.asset || "UNKNOWN")}}</span>
            <span>${{escapeHtml(row.broker || "UNKNOWN")}}</span>
            <span>${{money(row.allocated_capital || 0)}}</span>
            <span>${{Number(row.score || 0).toFixed(2)}}</span>
          </div>
          <div class="row detail"><span>${{escapeHtml(row.rationale || "")}}</span></div>
        `).join("")}}
      ` : `<div class="empty-state">No shadow allocation recommendations</div>`;
      const warningItems = section.warnings || [];
      warnings.innerHTML = warningItems.length ? warningItems.map((item) => `<li>${{escapeHtml(item)}}</li>`).join("") : "<li>NONE</li>";
    }}

    function renderCommittee() {{
      const section = state.sections.institutional_investment_committee || {{}};
      const target = document.getElementById("committee-opportunity-list");
      if (!target) return;
      const rows = section.top_opportunities || [];
      target.innerHTML = rows.length ? `
        <div class="row head"><span>Rank</span><span>Symbol</span><span>Decision</span><span>Score</span><span>Capital</span></div>
        ${{rows.map((row) => `
          <div class="row">
            <span>${{escapeHtml(row.capital_rank || "")}}</span>
            <span>${{escapeHtml(row.symbol || "UNKNOWN")}}</span>
            <span>${{escapeHtml(row.decision || "WAIT")}}</span>
            <span>${{Number(row.committee_score || 0).toFixed(2)}}</span>
            <span>${{money(row.recommended_capital || 0)}}</span>
          </div>
          <div class="row detail"><span>${{escapeHtml(row.recommendation || "")}}</span></div>
        `).join("")}}
      ` : `<div class="empty-state">No committee-ranked opportunities</div>`;
      const votesTarget = document.getElementById("committee-vote-list");
      if (!votesTarget) return;
      const votes = section.committee_votes || [];
      votesTarget.innerHTML = votes.length ? `
        <div class="row head"><span>Committee</span><span>Vote</span><span>Confidence</span><span>Score</span></div>
        ${{votes.map((vote) => `
          <div class="row">
            <span>${{escapeHtml(vote.committee || "UNKNOWN")}}</span>
            <span>${{escapeHtml(vote.vote || "ABSTAIN")}}</span>
            <span>${{Number(vote.confidence || 0).toFixed(2)}}</span>
            <span>${{Number(vote.committee_score || 0).toFixed(2)}}</span>
          </div>
          <div class="row detail"><span>${{escapeHtml(vote.reason || "")}}</span></div>
        `).join("")}}
      ` : `<div class="empty-state">No committee votes available</div>`;
    }}

    function normalizeCapitalAllocationPayload(payload) {{
      const report = payload.data || {{}};
      const metrics = payload.portfolio_metrics || report.portfolio_metrics || {{}};
      const summary = payload.allocation_summary || report.allocation_summary || {{}};
      return {{
        generated_at: payload.generated_at || report.generated_at,
        advisory_only: true,
        execution_allowed: false,
        capital_plan: payload.capital_plan || report.allocation_plan || [],
        allocation_summary: summary,
        portfolio_metrics: metrics,
        recommendations: payload.recommendations || report.recommendations || [],
        warnings: payload.warnings || report.warnings || [],
        cash_allocation: metrics.cash_allocation || summary.capital_remaining || 0,
        unused_capital: summary.capital_remaining || 0,
        portfolio_diversification: metrics.diversification_score || 0,
        expected_return: metrics.expected_portfolio_return || 0,
        expected_risk: metrics.expected_portfolio_risk || 0,
        confidence: metrics.portfolio_confidence || 0
      }};
    }}

    async function refreshCapitalAllocation() {{
      const response = await fetch("/api/v1/capital-allocation-intelligence", {{ cache: "no-store" }});
      const payload = await response.json();
      state.sections.capital_allocation_intelligence = normalizeCapitalAllocationPayload(payload);
      render({{ ...(state.payload || {{}}), sections: state.sections }});
    }}

    async function refresh() {{
      const response = await fetch("/api/v1/frontend-state", {{ cache: "no-store" }});
      render(await response.json());
      refreshCapitalAllocation().catch(() => undefined);
    }}

    function connectSocket() {{
      const indicator = document.getElementById("status-ws");
      const protocol = location.protocol === "https:" ? "wss" : "ws";
      const socket = new WebSocket(`${{protocol}}://${{location.host}}/ws/v1/dashboard-state`);
      socket.addEventListener("open", () => {{ indicator.textContent = "WebSocket live"; }});
      socket.addEventListener("message", (event) => {{
        const message = JSON.parse(event.data);
        if (message.message_type === "dashboard_snapshot") render(message);
        if (message.message_type === "dashboard_delta") {{
          state.sections = {{ ...state.sections, ...(message.data || {{}}) }};
          render({{ ...(state.payload || {{}}), sections: state.sections }});
        }}
      }});
      socket.addEventListener("close", () => {{
        indicator.textContent = "WebSocket reconnecting";
        setTimeout(connectSocket, 2500);
      }});
      socket.addEventListener("error", () => {{ indicator.textContent = "WebSocket degraded"; }});
    }}

    document.querySelector("[data-refresh]").addEventListener("click", refresh);
    refresh().catch(() => undefined);
    connectSocket();
  </script>
</body>
</html>"""


def _positions_page() -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  {_icon_links()}
  <title>CSS Professional Positions</title>
  <style>{_css()}</style>
</head>
<body><div style="background-color:#ffebee;color:#b71c1c;text-align:center;padding:8px;font-weight:bold;font-size:0.85em;border-bottom:1px solid #b71c1c;" aria-label="Risk Warning">Trading involves substantial risk. Loss of capital may occur. Past performance does not guarantee future results.</div>
  <main class="shell">
    <header class="topbar">
      <div class="brand-lockup">
        <div class="brand-mark" aria-hidden="true">CSS</div>
        <div>
          <p class="eyebrow">Capital Strata Systems</p>
          <h1>Professional Positions</h1>
        </div>
      </div>
      <section class="status-strip" aria-label="System status">
        <span id="positions-mode">System PAPER</span>
        <span id="positions-engine">Engine SAFE</span>
        <span id="positions-session">Session pending</span>
        <span id="positions-updated">Snapshot pending</span>
      </section>
    </header>
    {_app_nav("positions")}

    <section class="control-row" aria-label="Positions controls">
      <button type="button" data-refresh-positions>Refresh</button>
      <span>DashboardState positions contract</span>
      <span>Read-only inventory</span>
      <span>No trade execution from this view</span>
    </section>

    <section class="metric-band positions-metrics" aria-label="Position metrics">
      <article>
        <strong>Total Positions</strong>
        <span data-pos-value="positions.total">0</span>
      </article>
      <article>
        <strong>Long / Short</strong>
        <span id="long-short-metric">0 / 0</span>
      </article>
      <article>
        <strong>Winners / Losers</strong>
        <span id="winner-loser-metric">0 / 0</span>
      </article>
      <article>
        <strong>Total Exposure</strong>
        <span data-pos-value="pnl_summary.total_exposure">$0.00</span>
      </article>
      <article>
        <strong>Unrealized PnL</strong>
        <span data-pos-value="pnl_summary.unrealized_pnl">$0.00</span>
      </article>
      <article>
        <strong>Risk Gate</strong>
        <span data-pos-value="risk.gate_status">OPEN</span>
      </article>
    </section>

    <section class="positions-workspace">
      <article class="panel positions-main">
        <div class="panel-head">
          <h2>Position Inventory</h2>
          <span id="position-count-badge">0 OPEN</span>
        </div>
        <div class="position-table" id="position-detail-table"></div>
      </article>

      <aside class="positions-side">
        <article class="panel compact-panel">
          <div class="panel-head">
            <h2>Asset Allocation</h2>
            <span>BY ASSET</span>
          </div>
          <div class="summary-table" id="asset-allocation-table"></div>
        </article>

        <article class="panel compact-panel">
          <div class="panel-head">
            <h2>Active Symbols</h2>
            <span id="active-symbol-count">0</span>
          </div>
          <div class="symbol-cloud" id="active-symbols"></div>
        </article>
      </aside>
    </section>
  </main>

  <script>{_positions_script()}</script>
</body>
</html>"""


def _positions_script() -> str:
    return """
const positionState = { payload: null, sections: {} };

function money(value) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(value || 0));
}

function numberValue(value) {
  return Number(value || 0).toLocaleString("en-US", { maximumFractionDigits: 6 });
}

function getValue(path) {
  const [section, key] = path.split(".");
  return positionState.sections?.[section]?.[key];
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\\"": "&quot;",
    "'": "&#39;"
  }[char]));
}

function formatValue(path, value) {
  if (["total_exposure", "unrealized_pnl"].some((key) => path.endsWith(key))) {
    return money(value);
  }
  if (value === null || value === undefined || value === "") return "NONE";
  return String(value);
}

function renderPositionSnapshot(payload) {
  positionState.payload = payload;
  positionState.sections = payload.sections || {};
  const session = payload.session || {};
  const positions = positionState.sections.positions || {};

  document.getElementById("positions-mode").textContent = `System ${String(payload.resolved_mode || "paper").toUpperCase()}`;
  document.getElementById("positions-engine").textContent = `Engine ${session.engine_mode || "SAFE"}`;
  document.getElementById("positions-session").textContent = `Session ${payload.session_id || session.session_id || "pending"}`;
  document.getElementById("positions-updated").textContent = `Updated ${payload.generated_at || "pending"}`;
  document.getElementById("long-short-metric").textContent = `${positions.long_count || 0} / ${positions.short_count || 0}`;
  document.getElementById("winner-loser-metric").textContent = `${positions.winner_count || 0} / ${positions.loser_count || 0}`;
  document.getElementById("position-count-badge").textContent = `${positions.total || 0} OPEN`;

  document.querySelectorAll("[data-pos-value]").forEach((node) => {
    const path = node.getAttribute("data-pos-value");
    node.textContent = formatValue(path, getValue(path));
  });

  renderPositionTable(positions.items || []);
  renderAssetAllocation(positions);
  renderActiveSymbols(positions.active_symbols || []);
}

function renderPositionTable(items) {
  const target = document.getElementById("position-detail-table");
  if (!items.length) {
    target.innerHTML = `<div class="empty-state">No open positions</div>`;
    return;
  }
  target.innerHTML = `
    <div class="position-row position-head">
      <span>Symbol</span><span>Asset</span><span>Side</span><span>Qty</span><span>Entry</span><span>Mark</span><span>Exposure</span><span>Unrealized</span>
    </div>
    ${items.map((item) => `
      <div class="position-row">
        <span>${escapeHtml(item.symbol || "UNKNOWN")}</span>
        <span>${escapeHtml(item.asset_class || "UNKNOWN")}</span>
        <span><em class="side-badge ${String(item.side || "").toLowerCase()}">${escapeHtml(item.side || "UNKNOWN")}</em></span>
        <span>${numberValue(item.qty)}</span>
        <span>${money(item.entry_price)}</span>
        <span>${money(item.current_price)}</span>
        <span>${money(item.exposure)}</span>
        <span class="${Number(item.unrealized_pnl || 0) >= 0 ? "positive" : "negative"}">${money(item.unrealized_pnl)}</span>
      </div>
    `).join("")}
  `;
}

function renderAssetAllocation(positions) {
  const target = document.getElementById("asset-allocation-table");
  const byAsset = positions.by_asset || {};
  const items = positions.items || [];
  const rows = Object.entries(byAsset).map(([asset, count]) => {
    const exposure = items.filter((item) => item.asset_class === asset).reduce((total, item) => total + Number(item.exposure || 0), 0);
    const unrealized = items.filter((item) => item.asset_class === asset).reduce((total, item) => total + Number(item.unrealized_pnl || 0), 0);
    return { asset, count, exposure, unrealized };
  });
  if (!rows.length) {
    target.innerHTML = `<div class="empty-state">No asset allocation</div>`;
    return;
  }
  target.innerHTML = rows.map((row) => `
    <div class="summary-row">
      <span>${escapeHtml(row.asset)}</span>
      <span>${row.count} open</span>
      <span>${money(row.exposure)}</span>
      <span class="${row.unrealized >= 0 ? "positive" : "negative"}">${money(row.unrealized)}</span>
    </div>
  `).join("");
}

function renderActiveSymbols(symbols) {
  const target = document.getElementById("active-symbols");
  document.getElementById("active-symbol-count").textContent = String(symbols.length);
  target.innerHTML = symbols.length
    ? symbols.map((symbol) => `<span>${escapeHtml(symbol)}</span>`).join("")
    : `<div class="empty-state">No active symbols</div>`;
}

async function refreshPositions() {
  const response = await fetch("/api/v1/frontend-state", { cache: "no-store" });
  renderPositionSnapshot(await response.json());
}

document.querySelector("[data-refresh-positions]").addEventListener("click", refreshPositions);
refreshPositions().catch(() => undefined);
"""


def _execution_page() -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  {_icon_links()}
  <title>CSS Execution History</title>
  <style>{_css()}</style>
</head>
<body><div style="background-color:#ffebee;color:#b71c1c;text-align:center;padding:8px;font-weight:bold;font-size:0.85em;border-bottom:1px solid #b71c1c;" aria-label="Risk Warning">Trading involves substantial risk. Loss of capital may occur. Past performance does not guarantee future results.</div>
  <main class="shell">
    <header class="topbar">
      <div class="brand-lockup">
        <div class="brand-mark" aria-hidden="true">CSS</div>
        <div>
          <p class="eyebrow">Capital Strata Systems</p>
          <h1>Execution / Trade History</h1>
        </div>
      </div>
      <section class="status-strip" aria-label="System status">
        <span id="execution-mode">System PAPER</span>
        <span id="execution-engine">Engine SAFE</span>
        <span id="execution-session">Session pending</span>
        <span id="execution-updated">Snapshot pending</span>
      </section>
    </header>
    {_app_nav("execution")}

    <section class="control-row" aria-label="Execution controls">
      <button type="button" data-refresh-execution>Refresh</button>
      <span>DashboardState execution contract</span>
      <span>Read-only history</span>
      <span>No order placement from this view</span>
    </section>

    <section class="metric-band" aria-label="Execution metrics">
      <article>
        <strong>Execution State</strong>
        <span data-exec-value="execution.execution_state">IDLE</span>
      </article>
      <article>
        <strong>Accepted</strong>
        <span data-exec-value="execution.accepted_trade_count">0</span>
      </article>
      <article>
        <strong>Rejected</strong>
        <span data-exec-value="execution.rejected_trade_count">0</span>
      </article>
      <article>
        <strong>Pending</strong>
        <span data-exec-value="execution.pending_trade_count">0</span>
      </article>
      <article>
        <strong>Total Cost</strong>
        <span data-exec-value="execution.total_execution_cost">$0.00</span>
      </article>
      <article>
        <strong>History Rows</strong>
        <span data-exec-value="execution.recent_trade_count">0</span>
      </article>
    </section>

    <section class="execution-workspace">
      <article class="panel execution-main">
        <div class="panel-head">
          <h2>Trade / Execution History</h2>
          <span id="execution-history-badge">0 ROWS</span>
        </div>
        <div class="execution-table" id="execution-history-table"></div>
      </article>

      <aside class="execution-side">
        <article class="panel compact-panel">
          <div class="panel-head">
            <h2>Cost Breakdown</h2>
            <span data-exec-value="execution.execution_cost_state">UNKNOWN</span>
          </div>
          <div class="kv-grid two">
            <div><strong>Slippage</strong><span data-exec-value="execution.slippage_cost">$0.00</span></div>
            <div><strong>Spread</strong><span data-exec-value="execution.spread_cost">$0.00</span></div>
            <div><strong>Fee</strong><span data-exec-value="execution.fee_cost">$0.00</span></div>
            <div><strong>Avg Slip</strong><span data-exec-value="execution.avg_slippage_bps">0.00 bps</span></div>
          </div>
        </article>

        <article class="panel compact-panel">
          <div class="panel-head">
            <h2>Last Event</h2>
            <span>SUMMARY</span>
          </div>
          <p class="panel-note" data-exec-value="execution.last_execution_event">No execution event</p>
        </article>
      </aside>
    </section>
  </main>

  <script>{_execution_script()}</script>
</body>
</html>"""


def _execution_script() -> str:
    return """
const executionState = { payload: null, sections: {} };

function money(value) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(value || 0));
}

function numberValue(value) {
  return Number(value || 0).toLocaleString("en-US", { maximumFractionDigits: 6 });
}

function bps(value) {
  return `${Number(value || 0).toFixed(2)} bps`;
}

function getValue(path) {
  const [section, key] = path.split(".");
  return executionState.sections?.[section]?.[key];
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\\"": "&quot;",
    "'": "&#39;"
  }[char]));
}

function formatExecutionValue(path, value) {
  if (["total_execution_cost", "slippage_cost", "spread_cost", "fee_cost"].some((key) => path.endsWith(key))) {
    return money(value);
  }
  if (["avg_slippage_bps", "avg_spread_bps"].some((key) => path.endsWith(key))) {
    return bps(value);
  }
  if (value === null || value === undefined || value === "") return "NONE";
  return String(value);
}

function renderExecutionSnapshot(payload) {
  executionState.payload = payload;
  executionState.sections = payload.sections || {};
  const session = payload.session || {};
  const execution = executionState.sections.execution || {};

  document.getElementById("execution-mode").textContent = `System ${String(payload.resolved_mode || "paper").toUpperCase()}`;
  document.getElementById("execution-engine").textContent = `Engine ${session.engine_mode || "SAFE"}`;
  document.getElementById("execution-session").textContent = `Session ${payload.session_id || session.session_id || "pending"}`;
  document.getElementById("execution-updated").textContent = `Updated ${payload.generated_at || "pending"}`;
  document.getElementById("execution-history-badge").textContent = `${execution.recent_trade_count || 0} ROWS`;

  document.querySelectorAll("[data-exec-value]").forEach((node) => {
    const path = node.getAttribute("data-exec-value");
    node.textContent = formatExecutionValue(path, getValue(path));
  });

  renderExecutionHistory(execution.recent_trades || []);
}

function renderExecutionHistory(rows) {
  const target = document.getElementById("execution-history-table");
  if (!rows.length) {
    target.innerHTML = `<div class="empty-state">No execution history rows</div>`;
    return;
  }
  target.innerHTML = `
    <div class="execution-row execution-head">
      <span>Time</span><span>Symbol</span><span>Asset</span><span>Side</span><span>Mode</span><span>Broker</span><span>Status</span><span>Qty</span><span>Amount</span><span>Cost</span>
    </div>
    ${rows.map((row) => `
      <div class="execution-row">
        <span>${escapeHtml(row.timestamp || "UNKNOWN")}</span>
        <span>${escapeHtml(row.symbol || "UNKNOWN")}</span>
        <span>${escapeHtml(row.asset_class || "UNKNOWN")}</span>
        <span><em class="side-badge ${String(row.side || "").toLowerCase()}">${escapeHtml(row.side || "UNKNOWN")}</em></span>
        <span>${escapeHtml(row.mode || "paper")}</span>
        <span>${escapeHtml(row.broker || "CSS")}</span>
        <span>${escapeHtml(row.status || "UNKNOWN")}</span>
        <span>${numberValue(row.qty)}</span>
        <span>${money(row.amount)}</span>
        <span>${money(row.execution_cost)}</span>
      </div>
    `).join("")}
  `;
}

async function refreshExecution() {
  const response = await fetch("/api/v1/frontend-state", { cache: "no-store" });
  renderExecutionSnapshot(await response.json());
}

document.querySelector("[data-refresh-execution]").addEventListener("click", refreshExecution);
refreshExecution().catch(() => undefined);
"""


def _risk_governance_page() -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  {_icon_links()}
  <title>CSS Risk & Governance Center</title>
  <style>{_css()}</style>
</head>
<body><div style="background-color:#ffebee;color:#b71c1c;text-align:center;padding:8px;font-weight:bold;font-size:0.85em;border-bottom:1px solid #b71c1c;" aria-label="Risk Warning">Trading involves substantial risk. Loss of capital may occur. Past performance does not guarantee future results.</div>
  <main class="shell">
    <header class="topbar">
      <div class="brand-lockup">
        <div class="brand-mark" aria-hidden="true">CSS</div>
        <div>
          <p class="eyebrow">Capital Strata Systems</p>
          <h1>Risk & Governance Center</h1>
        </div>
      </div>
      <section class="status-strip" aria-label="System status">
        <span id="rg-mode">System PAPER</span>
        <span id="rg-engine">Engine SAFE</span>
        <span id="rg-session">Session pending</span>
        <span id="rg-updated">Snapshot pending</span>
      </section>
    </header>
    {_app_nav("risk_governance")}

    <section class="control-row" aria-label="Risk and governance controls">
      <button type="button" data-refresh-risk-governance>Refresh</button>
      <span>DashboardState risk contract</span>
      <span>Governance-safe display</span>
      <span>No authority mutation from this view</span>
    </section>

    <section class="metric-band" aria-label="Risk and governance metrics">
      <article>
        <strong>Risk State</strong>
        <span data-rg-value="risk.risk_state">NORMAL</span>
      </article>
      <article>
        <strong>Gate Status</strong>
        <span data-rg-value="risk.gate_status">OPEN</span>
      </article>
      <article>
        <strong>Drawdown</strong>
        <span data-rg-value="risk.current_drawdown_pct">0.00%</span>
      </article>
      <article>
        <strong>Exposure Utilization</strong>
        <span data-rg-value="risk.exposure_utilization_pct">0.00%</span>
      </article>
      <article>
        <strong>Session Lock</strong>
        <span data-rg-bool="governance.session_locked">NO</span>
      </article>
      <article>
        <strong>Defensive Mode</strong>
        <span data-rg-bool="governance.defensive_mode_active">NO</span>
      </article>
    </section>

    <section class="risk-governance-workspace">
      <article class="panel risk-main">
        <div class="panel-head">
          <h2>Risk Control Center</h2>
          <span data-rg-value="risk.gate_status">OPEN</span>
        </div>
        <div class="kv-grid two">
          <div><strong>Total Exposure</strong><span data-rg-value="risk.total_exposure">$0.00</span></div>
          <div><strong>Exposure Limit</strong><span data-rg-value="risk.exposure_limit">$0.00</span></div>
          <div><strong>Daily Loss Limit</strong><span data-rg-value="risk.daily_loss_limit">$0.00</span></div>
          <div><strong>Position Limit</strong><span data-rg-value="risk.position_limit">0</span></div>
          <div><strong>Current Drawdown</strong><span data-rg-value="risk.current_drawdown_pct">0.00%</span></div>
          <div><strong>Max Drawdown</strong><span data-rg-value="risk.max_drawdown_pct">0.00%</span></div>
        </div>
        <div class="breach-panel">
          <h3>Risk Limit Breaches</h3>
          <ul class="compact-list" id="rg-risk-breaches"></ul>
        </div>
      </article>

      <aside class="risk-governance-side">
        <article class="panel compact-panel">
          <div class="panel-head">
            <h2>Governance Authority</h2>
            <span id="rg-authority-state">READY</span>
          </div>
          <div class="toggle-grid">
            <span data-rg-flag="governance.governance_enabled">Governance Enabled</span>
            <span data-rg-flag="governance.audit_enabled">Audit Enabled</span>
            <span data-rg-flag="governance.unified_trade_gate_active">Unified Gate</span>
            <span data-rg-flag="governance.defensive_mode_active">Defensive Mode</span>
          </div>
        </article>

        <article class="panel compact-panel">
          <div class="panel-head">
            <h2>Governance Event</h2>
            <span>LAST</span>
          </div>
          <p class="panel-note" data-rg-value="governance.last_governance_event">No governance event</p>
        </article>
      </aside>
    </section>
  </main>

  <script>{_risk_governance_script()}</script>
</body>
</html>"""


def _risk_governance_script() -> str:
    return """
const rgState = { payload: null, sections: {} };

function money(value) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(value || 0));
}

function pct(value) {
  return `${Number(value || 0).toFixed(2)}%`;
}

function getValue(path) {
  const [section, key] = path.split(".");
  return rgState.sections?.[section]?.[key];
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\\"": "&quot;",
    "'": "&#39;"
  }[char]));
}

function formatRiskGovernanceValue(path, value) {
  if (["total_exposure", "exposure_limit", "daily_loss_limit"].some((key) => path.endsWith(key))) {
    return money(value);
  }
  if (["current_drawdown_pct", "max_drawdown_pct", "exposure_utilization_pct"].some((key) => path.endsWith(key))) {
    return pct(value);
  }
  if (value === true) return "YES";
  if (value === false) return "NO";
  if (value === null || value === undefined || value === "") return "NONE";
  return String(value);
}

function renderRiskGovernanceSnapshot(payload) {
  rgState.payload = payload;
  rgState.sections = payload.sections || {};
  const session = payload.session || {};
  const risk = rgState.sections.risk || {};
  const governance = rgState.sections.governance || {};

  document.getElementById("rg-mode").textContent = `System ${String(payload.resolved_mode || "paper").toUpperCase()}`;
  document.getElementById("rg-engine").textContent = `Engine ${session.engine_mode || "SAFE"}`;
  document.getElementById("rg-session").textContent = `Session ${payload.session_id || session.session_id || "pending"}`;
  document.getElementById("rg-updated").textContent = `Updated ${payload.generated_at || "pending"}`;
  document.getElementById("rg-authority-state").textContent = governance.session_locked ? "LOCKED" : "READY";

  document.querySelectorAll("[data-rg-value]").forEach((node) => {
    const path = node.getAttribute("data-rg-value");
    node.textContent = formatRiskGovernanceValue(path, getValue(path));
  });
  document.querySelectorAll("[data-rg-bool]").forEach((node) => {
    node.textContent = getValue(node.getAttribute("data-rg-bool")) ? "YES" : "NO";
  });
  document.querySelectorAll("[data-rg-flag]").forEach((node) => {
    const value = Boolean(getValue(node.getAttribute("data-rg-flag")));
    node.classList.toggle("on", value);
    node.classList.toggle("off", !value);
  });

  renderRiskBreaches(risk.risk_limits_breached || []);
}

function renderRiskBreaches(breaches) {
  const target = document.getElementById("rg-risk-breaches");
  target.innerHTML = breaches.length
    ? breaches.map((item) => `<li>${escapeHtml(item)}</li>`).join("")
    : "<li>NONE</li>";
}

async function refreshRiskGovernance() {
  const response = await fetch("/api/v1/frontend-state", { cache: "no-store" });
  renderRiskGovernanceSnapshot(await response.json());
}

document.querySelector("[data-refresh-risk-governance]").addEventListener("click", refreshRiskGovernance);
refreshRiskGovernance().catch(() => undefined);
"""


def _trade_page() -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  {_icon_links()}
  <title>CSS Trade Universe</title>
  <style>{_css()}</style>
</head>
<body><div style="background-color:#ffebee;color:#b71c1c;text-align:center;padding:8px;font-weight:bold;font-size:0.85em;border-bottom:1px solid #b71c1c;" aria-label="Risk Warning">Trading involves substantial risk. Loss of capital may occur. Past performance does not guarantee future results.</div>
  <main class="shell">
    <header class="topbar">
      <div class="brand-lockup">
        <div class="brand-mark" aria-hidden="true">CSS</div>
        <div>
          <p class="eyebrow">Capital Strata Systems</p>
          <h1>Trade Universe</h1>
        </div>
      </div>
      <section class="status-strip" aria-label="System status">
        <span id="trade-mode">System PAPER</span>
        <span id="trade-engine">Engine SAFE</span>
        <span id="trade-session">Session pending</span>
        <span id="trade-updated">Snapshot pending</span>
      </section>
    </header>
    {_app_nav("trade")}

    <section class="control-row trade-controls" aria-label="Trade universe controls">
      <button type="button" data-refresh-trade>Refresh</button>
      <input type="search" id="trade-search" placeholder="Search symbol" aria-label="Search symbol">
      <select id="trade-asset-filter" aria-label="Filter by asset class">
        <option value="ALL">All assets</option>
      </select>
      <select id="trade-sort" aria-label="Sort universe">
        <option value="symbol_asc">Symbol A-Z</option>
        <option value="symbol_desc">Symbol Z-A</option>
        <option value="price_desc">Price high-low</option>
        <option value="price_asc">Price low-high</option>
        <option value="spread_asc">Spread low-high</option>
        <option value="spread_desc">Spread high-low</option>
      </select>
      <label class="watch-only-toggle"><input type="checkbox" id="trade-watch-only"> Watchlist only</label>
      <span>Canonical market universe source</span>
      <span>Read-only trade data layer</span>
    </section>

    <section class="metric-band" aria-label="Trade universe metrics">
      <article>
        <strong>Universe Count</strong>
        <span id="trade-universe-count">0</span>
      </article>
      <article>
        <strong>Visible Rows</strong>
        <span id="trade-visible-count">0</span>
      </article>
      <article>
        <strong>Watchlist</strong>
        <span id="trade-watch-count">0</span>
      </article>
      <article>
        <strong>In Position</strong>
        <span id="trade-in-position-count">0</span>
      </article>
      <article>
        <strong>Universe Source</strong>
        <span id="trade-source">UNKNOWN</span>
      </article>
      <article>
        <strong>Asset Classes</strong>
        <span id="trade-asset-count">0</span>
      </article>
    </section>

    <section class="trade-workspace">
      <article class="panel trade-main">
        <div class="panel-head">
          <h2>Canonical Market Universe Grid</h2>
          <span id="trade-grid-badge">0 ROWS</span>
        </div>
        <div class="trade-table" id="trade-universe-table"></div>
      </article>
    </section>
  </main>

  <script>{_trade_script()}</script>
</body>
</html>"""


def _trade_script() -> str:
    return """
const tradeState = { payload: null, sections: {}, rows: [] };
const WATCHLIST_KEY = "css.trade.watchlist.v1";

function numberValue(value) {
  return Number(value || 0).toLocaleString("en-US", { maximumFractionDigits: 6 });
}

function signed(value) {
  const n = Number(value || 0);
  return `${n >= 0 ? "+" : ""}${n.toFixed(4)}`;
}

function getWatchlist() {
  try {
    const parsed = JSON.parse(localStorage.getItem(WATCHLIST_KEY) || "[]");
    return new Set(Array.isArray(parsed) ? parsed.map((v) => String(v).toUpperCase()) : []);
  } catch {
    return new Set();
  }
}

function saveWatchlist(set) {
  localStorage.setItem(WATCHLIST_KEY, JSON.stringify(Array.from(set).sort()));
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\\"": "&quot;",
    "'": "&#39;"
  }[char]));
}

function currentRows() {
  const search = String(document.getElementById("trade-search").value || "").trim().toUpperCase();
  const asset = String(document.getElementById("trade-asset-filter").value || "ALL");
  const sort = String(document.getElementById("trade-sort").value || "symbol_asc");
  const watchOnly = document.getElementById("trade-watch-only").checked;
  const watchlist = getWatchlist();

  let rows = [...tradeState.rows];
  if (search) {
    rows = rows.filter((row) => String(row.symbol || "").toUpperCase().includes(search));
  }
  if (asset !== "ALL") {
    rows = rows.filter((row) => String(row.asset_class || "") === asset);
  }
  if (watchOnly) {
    rows = rows.filter((row) => watchlist.has(String(row.symbol || "").toUpperCase()));
  }

  const cmpNum = (a, b, key, asc = true) => asc ? Number(a[key] || 0) - Number(b[key] || 0) : Number(b[key] || 0) - Number(a[key] || 0);
  const cmpStr = (a, b, key, asc = true) => asc ? String(a[key] || "").localeCompare(String(b[key] || "")) : String(b[key] || "").localeCompare(String(a[key] || ""));

  if (sort === "symbol_asc") rows.sort((a, b) => cmpStr(a, b, "symbol", true));
  if (sort === "symbol_desc") rows.sort((a, b) => cmpStr(a, b, "symbol", false));
  if (sort === "price_asc") rows.sort((a, b) => cmpNum(a, b, "price", true));
  if (sort === "price_desc") rows.sort((a, b) => cmpNum(a, b, "price", false));
  if (sort === "spread_asc") rows.sort((a, b) => cmpNum(a, b, "spread_bps", true));
  if (sort === "spread_desc") rows.sort((a, b) => cmpNum(a, b, "spread_bps", false));

  return rows;
}

function renderTradeUniverse() {
  const universe = tradeState.sections.trade || {};
  const allRows = tradeState.rows;
  const rows = currentRows();
  const watchlist = getWatchlist();
  const target = document.getElementById("trade-universe-table");

  document.getElementById("trade-universe-count").textContent = String(allRows.length);
  document.getElementById("trade-visible-count").textContent = String(rows.length);
  document.getElementById("trade-watch-count").textContent = String(watchlist.size);
  document.getElementById("trade-in-position-count").textContent = String(allRows.filter((row) => Boolean(row.in_position)).length);
  document.getElementById("trade-source").textContent = String(universe.source || "UNKNOWN");
  document.getElementById("trade-asset-count").textContent = String((universe.asset_classes || []).length);
  document.getElementById("trade-grid-badge").textContent = `${rows.length} ROWS`;

  if (!rows.length) {
    target.innerHTML = `<div class="empty-state">No symbols match current filters</div>`;
    return;
  }

  target.innerHTML = `
    <div class="trade-row trade-head">
      <span>Watch</span><span>Symbol</span><span>Asset</span><span>Price</span><span>VWAP</span><span>VWAP Dev</span><span>Spread (bps)</span><span>Signal</span><span>Status</span><span>Position</span>
    </div>
    ${rows.map((row) => {
      const symbol = String(row.symbol || "UNKNOWN").toUpperCase();
      const watched = watchlist.has(symbol);
      return `
        <div class="trade-row">
          <span><button type="button" class="watch-btn ${watched ? "on" : "off"}" data-watch-symbol="${escapeHtml(symbol)}">${watched ? "WATCHED" : "WATCH"}</button></span>
          <span>${escapeHtml(symbol)}</span>
          <span>${escapeHtml(row.asset_class || "UNKNOWN")}</span>
          <span>${numberValue(row.price)}</span>
          <span>${numberValue(row.vwap)}</span>
          <span class="${Number(row.vwap_dev || 0) >= 0 ? "positive" : "negative"}">${signed(row.vwap_dev)}</span>
          <span>${numberValue(row.spread_bps)}</span>
          <span>${escapeHtml(row.signal || "WATCH")}</span>
          <span>${escapeHtml(row.status || "MONITOR_ONLY")}</span>
          <span>${row.in_position ? "OPEN" : "FLAT"}</span>
        </div>
      `;
    }).join("")}
  `;

  target.querySelectorAll("[data-watch-symbol]").forEach((node) => {
    node.addEventListener("click", () => {
      const symbol = String(node.getAttribute("data-watch-symbol") || "").toUpperCase();
      const updated = getWatchlist();
      if (updated.has(symbol)) updated.delete(symbol);
      else updated.add(symbol);
      saveWatchlist(updated);
      renderTradeUniverse();
    });
  });
}

function syncAssetFilter() {
  const select = document.getElementById("trade-asset-filter");
  const current = String(select.value || "ALL");
  const classes = (tradeState.sections.trade?.asset_classes || []);
  select.innerHTML = `<option value="ALL">All assets</option>${classes.map((asset) => `<option value="${escapeHtml(asset)}">${escapeHtml(asset)}</option>`).join("")}`;
  if (["ALL", ...classes].includes(current)) {
    select.value = current;
  }
}

function renderTradeSnapshot(payload) {
  tradeState.payload = payload;
  tradeState.sections = payload.sections || {};
  tradeState.rows = Array.isArray(tradeState.sections.trade?.items) ? tradeState.sections.trade.items : [];
  const session = payload.session || {};

  document.getElementById("trade-mode").textContent = `System ${String(payload.resolved_mode || "paper").toUpperCase()}`;
  document.getElementById("trade-engine").textContent = `Engine ${session.engine_mode || "SAFE"}`;
  document.getElementById("trade-session").textContent = `Session ${payload.session_id || session.session_id || "pending"}`;
  document.getElementById("trade-updated").textContent = `Updated ${tradeState.sections.trade?.generated_at || payload.generated_at || "pending"}`;

  syncAssetFilter();
  renderTradeUniverse();
}

async function refreshTrade() {
  const response = await fetch("/api/v1/frontend-state", { cache: "no-store" });
  renderTradeSnapshot(await response.json());
}

document.querySelector("[data-refresh-trade]").addEventListener("click", refreshTrade);
document.getElementById("trade-search").addEventListener("input", renderTradeUniverse);
document.getElementById("trade-asset-filter").addEventListener("change", renderTradeUniverse);
document.getElementById("trade-sort").addEventListener("change", renderTradeUniverse);
document.getElementById("trade-watch-only").addEventListener("change", renderTradeUniverse);
refreshTrade().catch(() => undefined);
"""


def _market_opportunities_page() -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  {_icon_links()}
  <title>CSS Market & Opportunity Center</title>
  <style>{_css()}</style>
</head>
<body><div style="background-color:#ffebee;color:#b71c1c;text-align:center;padding:8px;font-weight:bold;font-size:0.85em;border-bottom:1px solid #b71c1c;" aria-label="Risk Warning">Trading involves substantial risk. Loss of capital may occur. Past performance does not guarantee future results.</div>
  <main class="shell">
    <header class="topbar">
      <div class="brand-lockup">
        <div class="brand-mark" aria-hidden="true">CSS</div>
        <div>
          <p class="eyebrow">Capital Strata Systems</p>
          <h1>Market & Opportunity Center</h1>
        </div>
      </div>
      <section class="status-strip" aria-label="System status">
        <span id="mo-mode">System PAPER</span>
        <span id="mo-engine">Engine SAFE</span>
        <span id="mo-session">Session pending</span>
        <span id="mo-updated">Snapshot pending</span>
      </section>
    </header>
    {_app_nav("market_opportunities")}

    <section class="control-row" aria-label="Market and opportunity controls">
      <button type="button" data-refresh-market-opportunities>Refresh</button>
      <span>DashboardState market contract</span>
      <span>Monitor-only opportunities</span>
      <span>No order placement from this view</span>
    </section>

    <section class="metric-band" aria-label="Market regime metrics">
      <article>
        <strong>Regime</strong>
        <span data-mo-value="market.regime_state">UNKNOWN</span>
      </article>
      <article>
        <strong>Trend</strong>
        <span data-mo-value="market.trend_state">UNKNOWN</span>
      </article>
      <article>
        <strong>Volatility</strong>
        <span data-mo-value="market.volatility_state">UNKNOWN</span>
      </article>
      <article>
        <strong>Liquidity</strong>
        <span data-mo-value="market.liquidity_state">UNKNOWN</span>
      </article>
      <article>
        <strong>Confluence</strong>
        <span data-mo-value="market.signal_confluence_state">UNKNOWN</span>
      </article>
      <article>
        <strong>Opportunities</strong>
        <span data-mo-value="opportunities.count">0</span>
      </article>
      <article>
        <strong>Market Health</strong>
        <span data-mo-value="opportunities.market_health">DATA UNAVAILABLE</span>
      </article>
    </section>

    <section class="market-opportunity-workspace">
      <article class="panel market-main">
        <div class="panel-head">
          <h2>Market Regime Panel</h2>
          <span data-mo-value="market.execution_cost_state">UNKNOWN</span>
        </div>
        <div class="signal-grid">
          <div><strong>Probability</strong><span data-mo-value="market.probability_state">UNKNOWN</span></div>
          <div><strong>Velocity</strong><span data-mo-value="market.velocity_state">UNKNOWN</span></div>
          <div><strong>Mean Reversion</strong><span data-mo-value="market.mean_reversion_state">UNKNOWN</span></div>
          <div><strong>Momentum</strong><span data-mo-value="market.momentum_state">UNKNOWN</span></div>
          <div><strong>Pressure</strong><span data-mo-value="market.pressure_state">UNKNOWN</span></div>
          <div><strong>Acceleration</strong><span data-mo-value="market.acceleration_state">UNKNOWN</span></div>
          <div><strong>Spread</strong><span data-mo-value="market.spread_state">UNKNOWN</span></div>
          <div><strong>VWAP State</strong><span data-mo-value="market.vwap_state">UNKNOWN</span></div>
          <div><strong>VWAP Distance</strong><span data-mo-value="market.vwap_distance">0.0000</span></div>
          <div><strong>VWAP Elasticity</strong><span data-mo-value="market.vwap_elasticity">0.0000</span></div>
        </div>
      </article>

      <article class="panel opportunity-main">
        <div class="panel-head">
          <h2>Opportunity Monitor</h2>
          <span>Top Opportunities</span>
          <span id="opportunity-count-badge">0 ITEMS</span>
        </div>
        <div class="opportunity-table" id="opportunity-table"></div>
      </article>
    </section>
  </main>

  <script>{_market_opportunities_script()}</script>
</body>
</html>"""


def _trade_summary_page() -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>CSS Trade Summary</title>
  <style>{_css()}</style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div class="brand-lockup"><div class="brand-mark">CSS</div><div><p class="eyebrow">Capital Strata Systems</p><h1>Trade Summary</h1></div></div>
      <section class="status-strip"><span>Display Only</span><span>No order controls</span></section>
    </header>
    {_app_nav("trade_summary")}
    <section class="metric-band" id="trade-summary-band" aria-label="Compact trade summary">
      <article><strong>Date / Time</strong><span data-ts="date_time">DATA UNAVAILABLE</span></article>
      <article><strong>Mode</strong><span data-ts="mode">DATA UNAVAILABLE</span></article>
      <article><strong>Broker</strong><span data-ts="broker">DATA UNAVAILABLE</span></article>
      <article><strong>Engine Mode</strong><span data-ts="engine_mode">DATA UNAVAILABLE</span></article>
      <article><strong>Account Balance</strong><span data-ts="account_balance">DATA UNAVAILABLE</span></article>
      <article><strong>Equity</strong><span data-ts="equity">DATA UNAVAILABLE</span></article>
      <article><strong>Open Positions</strong><span data-ts="open_positions">DATA UNAVAILABLE</span></article>
      <article><strong>Realized PnL</strong><span data-ts="realized_pnl">DATA UNAVAILABLE</span></article>
      <article><strong>Unrealized PnL</strong><span data-ts="unrealized_pnl">DATA UNAVAILABLE</span></article>
      <article><strong>Last Cycle / Update</strong><span data-ts="last_cycle">DATA UNAVAILABLE</span></article>
      <article><strong>Execution Status</strong><span data-ts="execution_status">DATA UNAVAILABLE</span></article>
    </section>
  </main>
  <script>
    function show(v) {{ return v === null || v === undefined || v === "" ? "DATA UNAVAILABLE" : String(v); }}
    fetch("/api/v1/trade-summary", {{cache:"no-store"}})
      .then((r) => r.json())
      .then((p) => {{
        const data = p.data || {{}};
        document.querySelectorAll("[data-ts]").forEach((node) => {{
          node.textContent = show(data[node.getAttribute("data-ts")]);
        }});
        const cycle = document.querySelector('[data-ts="last_cycle"]');
        if (cycle) cycle.textContent = `${{show(data.last_cycle)}} / ${{show(data.last_update)}}`;
      }})
      .catch(() => undefined);
  </script>
</body>
</html>"""


def _session_command_centre_page() -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>CSS Session Command Centre</title>
  <style>{_css()}</style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div class="brand-lockup"><div class="brand-mark">CSS</div><div><p class="eyebrow">Capital Strata Systems</p><h1>Session Command Centre</h1></div></div>
      <section class="status-strip"><span>Advanced Intelligence</span><span>Display Only</span></section>
    </header>
    {_app_nav("command_centre")}
    <section class="metric-band" aria-label="Advanced intelligence scores">
      <article><strong>Trade Quality Score</strong><span data-scc="trade_quality_score">0</span></article>
      <article><strong>Capital Efficiency Score</strong><span data-scc="capital_efficiency_score">0</span></article>
      <article><strong>Engine Health Score</strong><span data-scc="engine_health_score">0</span></article>
      <article><strong>Opportunity Centre</strong><span data-scc="opportunity_centre.display_state">DATA UNAVAILABLE</span></article>
      <article><strong>Runtime Health</strong><span data-scc="runtime_health.execution_state">DATA UNAVAILABLE</span></article>
      <article><strong>AI Market Narrative</strong><span data-scc="ai_market_narrative">DATA UNAVAILABLE</span></article>
    </section>
    <section class="dashboard-grid">
      <article class="panel wide"><div class="panel-head"><h2>Daily Executive Summary</h2><span>READ ONLY</span></div><p id="daily-executive-summary" class="panel-note">DATA UNAVAILABLE</p></article>
      <article class="panel"><div class="panel-head"><h2>Navigation Links</h2><span id="nav-count">0</span></div><div id="scc-nav-links" class="symbol-cloud"></div></article>
      <article class="panel"><div class="panel-head"><h2>Intelligence Cards</h2><span id="card-count">0</span></div><div id="scc-cards" class="compact-list"></div></article>
    </section>
  </main>
  <script>
    function pick(obj, path) {{ return path.split(".").reduce((acc, key) => acc && acc[key], obj); }}
    function show(v) {{ return v === null || v === undefined || v === "" ? "DATA UNAVAILABLE" : String(v); }}
    fetch("/api/v1/session-command-centre", {{cache:"no-store"}})
      .then((r) => r.json())
      .then((p) => {{
        const data = p.data || {{}};
        document.querySelectorAll("[data-scc]").forEach((node) => {{
          node.textContent = show(pick(data, node.getAttribute("data-scc")));
        }});
        document.getElementById("daily-executive-summary").textContent = show(data.daily_executive_summary);
        const links = data.navigation_links || [];
        document.getElementById("nav-count").textContent = String(links.length);
        document.getElementById("scc-nav-links").innerHTML = links.map((link) => {{
          const label = show(link.label || link.title || link.name);
          const href = link.href || link.route || link.url || "";
          if (href && typeof href === "string" && href !== "DATA UNAVAILABLE") {{
            const safe = String(href).replace(/"/g, "&quot;");
            return `<a class="scc-nav-link" href="${{safe}}">${{label}}</a>`;
          }}
          return `<span class="scc-nav-disabled" title="No route available">${{label}}</span>`;
        }}).join("");
        const cards = data.intelligence_cards || [];
        document.getElementById("card-count").textContent = String(cards.length);
        document.getElementById("scc-cards").innerHTML = cards.map((card) => `<li>${{show(card.title)}}: ${{show(card.value)}} (${{show(card.status)}})</li>`).join("");
      }})
      .catch((err) => {{
        const note = document.getElementById("daily-executive-summary");
        if (note) note.textContent = "DATA UNAVAILABLE — session command centre request failed.";
        console.error("session-command-centre load failed", err);
      }});
  </script>
</body>
</html>"""


def _live_readiness_certification_page() -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>CSS Live Readiness Certification</title>
  <style>{_css()}</style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div class="brand-lockup"><div class="brand-mark">CSS</div><div><p class="eyebrow">Capital Strata Systems</p><h1>Live Readiness Certification</h1></div></div>
      <section class="status-strip"><span>Read Only</span><span>No live execution</span></section>
    </header>
    {_app_nav("live_readiness_certification")}
    <section class="metric-band" aria-label="Live readiness certification summary">
      <article><strong>Live Readiness Score</strong><span data-lrc="live_readiness_score">DATA UNAVAILABLE</span></article>
      <article><strong>Certification Status</strong><span data-lrc="certification_status">DATA UNAVAILABLE</span></article>
      <article><strong>GO / NO-GO</strong><span data-lrc="go_no_go">DATA UNAVAILABLE</span></article>
      <article><strong>Software Version</strong><span data-lrc="software_version">DATA UNAVAILABLE</span></article>
      <article><strong>Commit</strong><span data-lrc="commit">DATA UNAVAILABLE</span></article>
      <article><strong>Engineering Tag</strong><span data-lrc="engineering_tag">DATA UNAVAILABLE</span></article>
      <article><strong>Last Certification Time</strong><span data-lrc="last_certification_time">DATA UNAVAILABLE</span></article>
    </section>
    <section class="dashboard-grid">
      <article class="panel"><div class="panel-head"><h2>Warnings</h2><span id="lrc-warning-count">0</span></div><ul id="lrc-warnings" class="compact-list"></ul></article>
      <article class="panel"><div class="panel-head"><h2>Blockers</h2><span id="lrc-blocker-count">0</span></div><ul id="lrc-blockers" class="compact-list"></ul></article>
    </section>
  </main>
  <script>
    function show(v) {{ return v === null || v === undefined || v === "" ? "DATA UNAVAILABLE" : String(v); }}
    function row(v) {{ return `<li>${{show(v)}}</li>`; }}
    fetch("/api/v1/live-readiness-certification", {{cache:"no-store"}})
      .then((r) => r.json())
      .then((p) => {{
        const data = p.data || {{}};
        document.querySelectorAll("[data-lrc]").forEach((node) => {{
          node.textContent = show(data[node.getAttribute("data-lrc")]);
        }});
        const warnings = Array.isArray(data.warnings) ? data.warnings : [];
        const blockers = Array.isArray(data.blockers) ? data.blockers : [];
        document.getElementById("lrc-warning-count").textContent = String(warnings.length);
        document.getElementById("lrc-blocker-count").textContent = String(blockers.length);
        document.getElementById("lrc-warnings").innerHTML = warnings.map(row).join("") || "<li>None reported</li>";
        document.getElementById("lrc-blockers").innerHTML = blockers.map(row).join("") || "<li>None reported</li>";
      }})
      .catch(() => undefined);
  </script>
</body>
</html>"""


def _market_opportunities_script() -> str:
    return """
const moState = { payload: null, sections: {} };

function numberValue(value) {
  return Number(value || 0).toLocaleString("en-US", { maximumFractionDigits: 4 });
}

function pct(value) {
  return `${(Number(value || 0) * 100).toFixed(2)}%`;
}

function getValue(path) {
  const [section, key] = path.split(".");
  return moState.sections?.[section]?.[key];
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\\"": "&quot;",
    "'": "&#39;"
  }[char]));
}

function formatMarketOpportunityValue(path, value) {
  if (["vwap_distance", "vwap_elasticity", "score"].some((key) => path.endsWith(key))) {
    return numberValue(value);
  }
  if (path.endsWith("probability")) {
    return pct(value);
  }
  if (value === null || value === undefined || value === "") return "NONE";
  return String(value);
}

function renderMarketOpportunitySnapshot(payload) {
  moState.payload = payload;
  moState.sections = payload.sections || {};
  const session = payload.session || {};
  const opportunities = moState.sections.opportunities || {};

  document.getElementById("mo-mode").textContent = `System ${String(payload.resolved_mode || "paper").toUpperCase()}`;
  document.getElementById("mo-engine").textContent = `Engine ${session.engine_mode || "SAFE"}`;
  document.getElementById("mo-session").textContent = `Session ${payload.session_id || session.session_id || "pending"}`;
  document.getElementById("mo-updated").textContent = `Updated ${payload.generated_at || "pending"}`;
  document.getElementById("opportunity-count-badge").textContent = `${opportunities.count || 0} ITEMS`;

  document.querySelectorAll("[data-mo-value]").forEach((node) => {
    const path = node.getAttribute("data-mo-value");
    node.textContent = formatMarketOpportunityValue(path, getValue(path));
  });

  renderOpportunities(opportunities.items || []);
}

function renderOpportunities(items) {
  const target = document.getElementById("opportunity-table");
  if (!items.length) {
    const emptyState = moState.sections.opportunities?.empty_state || "Capital preservation active: no risk-approved opportunities are available.";
    target.innerHTML = `<div class="empty-state">${escapeHtml(emptyState)}</div>`;
    return;
  }
  target.innerHTML = `
    <div class="opportunity-row opportunity-head">
      <span>Symbol</span><span>Asset</span><span>Side</span><span>Signal</span><span>Score</span><span>Probability</span><span>Status</span><span>Explanation</span>
    </div>
    ${items.map((item) => `
      <div class="opportunity-row">
        <span>${escapeHtml(item.symbol || "UNKNOWN")}</span>
        <span>${escapeHtml(item.asset_class || "UNKNOWN")}</span>
        <span><em class="side-badge ${String(item.side || "").toLowerCase()}">${escapeHtml(item.side || "WATCH")}</em></span>
        <span>${escapeHtml(item.signal || "WATCH")}</span>
        <span>${numberValue(item.score)}</span>
        <span>${pct(item.probability)}</span>
        <span>${escapeHtml(item.status || "MONITOR_ONLY")}</span>
        <span>${escapeHtml(item.opportunity_explanation || item.reason || "")}</span>
      </div>
    `).join("")}
  `;
}

async function refreshMarketOpportunities() {
  const response = await fetch("/api/v1/frontend-state", { cache: "no-store" });
  renderMarketOpportunitySnapshot(await response.json());
}

document.querySelector("[data-refresh-market-opportunities]").addEventListener("click", refreshMarketOpportunities);
refreshMarketOpportunities().catch(() => undefined);
"""


def _broker_page() -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="#111820">
  <title>CSS Broker Control Center</title>
  <style>{_css()}</style>
</head>
<body><div style="background-color:#ffebee;color:#b71c1c;text-align:center;padding:8px;font-weight:bold;font-size:0.85em;border-bottom:1px solid #b71c1c;" aria-label="Risk Warning">Trading involves substantial risk. Loss of capital may occur. Past performance does not guarantee future results.</div>
  <main class="shell">
    <header class="topbar">
      <div class="brand-lockup">
        <div class="brand-mark" aria-hidden="true">CSS</div>
        <div>
          <p class="eyebrow">Capital Strata Systems</p>
          <h1>Broker Control Center</h1>
        </div>
      </div>
      <section class="status-strip" aria-label="System status">
        <span id="broker-mode">System PAPER</span>
        <span id="broker-engine">Engine SAFE</span>
        <span id="broker-session">Session pending</span>
        <span id="broker-updated">Snapshot pending</span>
      </section>
    </header>
    {_app_nav("broker")}

    <section class="control-row" aria-label="Broker controls">
      <button type="button" data-refresh-broker>Refresh</button>
      <span>DashboardState broker contract</span>
      <span>Read-only readiness view</span>
      <span>Broker secrets are never displayed</span>
    </section>

    <section class="metric-band" aria-label="Broker metrics">
      <article>
        <strong>Selected Broker</strong>
        <span data-broker-value="broker.selected_broker">NONE</span>
      </article>
      <article>
        <strong>Broker Mode</strong>
        <span data-broker-value="broker.broker_mode">paper</span>
      </article>
      <article>
        <strong>Resolved Mode</strong>
        <span id="broker-resolved-mode">paper</span>
      </article>
      <article>
        <strong>Connected</strong>
        <span data-broker-bool="broker.connected">NO</span>
      </article>
      <article>
        <strong>Live Trading</strong>
        <span data-broker-bool="broker.live_trading_enabled">NO</span>
      </article>
      <article>
        <strong>Account Mode</strong>
        <span data-broker-value="account_summary.account_mode">paper</span>
      </article>
    </section>

    <section class="broker-workspace">
      <article class="panel broker-main">
        <div class="panel-head">
          <h2>Broker Readiness</h2>
          <span id="broker-readiness-state">PAPER SAFE</span>
        </div>
        <div class="kv-grid two">
          <div><strong>Selected Broker</strong><span data-broker-value="broker.selected_broker">NONE</span></div>
          <div><strong>Broker Mode</strong><span data-broker-value="broker.broker_mode">paper</span></div>
          <div><strong>Connected</strong><span data-broker-bool="broker.connected">NO</span></div>
          <div><strong>Live Trading Enabled</strong><span data-broker-bool="broker.live_trading_enabled">NO</span></div>
          <div><strong>Last Heartbeat</strong><span data-broker-value="broker.last_heartbeat">NONE</span></div>
          <div><strong>Account Broker</strong><span data-broker-value="account_summary.broker">NONE</span></div>
          <div><strong>API Health</strong><span data-broker-value="broker.api_health">UNKNOWN</span></div>
          <div><strong>Reconnect State</strong><span data-broker-value="broker.reconnect_state">NONE</span></div>
          <div><strong>Supported Assets</strong><span data-broker-value="broker.supported_assets">UNKNOWN</span></div>
          <div><strong>Broker Latency</strong><span id="broker-latency">-- ms</span></div>
          <div><strong>Account Readiness</strong><span data-broker-value="account_summary.account_readiness">UNKNOWN</span></div>
        </div>
        <div id="missing-credential-warning" style="display: none; background: var(--danger); color: #fff; padding: 10px; margin-top: 15px; font-weight: bold; text-align: center;">
          WARNING: Broker credentials missing. Trade execution disabled.
        </div>
      </article>

      <aside class="broker-side">
        <article class="panel compact-panel">
          <div class="panel-head">
            <h2>Mode Resolution</h2>
            <span id="broker-mode-state">PAPER</span>
          </div>
          <div class="toggle-grid">
            <span id="broker-session-live">Session Live</span>
            <span id="broker-mode-live">Broker Live</span>
            <span id="broker-connection-ready">Connected</span>
            <span id="broker-live-ready">Live Orders</span>
          </div>
        </article>

        <article class="panel compact-panel">
          <div class="panel-head">
            <h2>Safety Boundary</h2>
            <span>READ ONLY</span>
          </div>
          <ul class="compact-list">
            <li>No credential values are rendered.</li>
            <li>No direct broker calls run from this web view.</li>
            <li>Live mode requires session and broker mode agreement.</li>
          </ul>
        </article>
      </aside>
    </section>
  </main>

  <script>{_broker_script()}</script>
</body>
</html>"""


def _broker_script() -> str:
    return """
const brokerState = { payload: null, sections: {} };

function getValue(path) {
  const [section, key] = path.split(".");
  return brokerState.sections?.[section]?.[key];
}

function formatBrokerValue(value) {
  if (value === true) return "YES";
  if (value === false) return "NO";
  if (value === null || value === undefined || value === "") return "NONE";
  return String(value);
}

function setFlag(id, value) {
  const node = document.getElementById(id);
  node.classList.toggle("on", Boolean(value));
  node.classList.toggle("off", !Boolean(value));
}

function renderBrokerSnapshot(payload) {
  brokerState.payload = payload;
  brokerState.sections = payload.sections || {};
  const session = payload.session || {};
  const broker = brokerState.sections.broker || {};
  const account = brokerState.sections.account_summary || {};
  const resolvedMode = String(payload.resolved_mode || session.resolved_mode || "paper").toUpperCase();
  const sessionLive = String(session.live_or_paper || "").toLowerCase() === "live";
  const brokerLive = String(broker.broker_mode || "").toLowerCase() === "live";
  const liveReady = Boolean(broker.live_trading_enabled);

  document.getElementById("broker-mode").textContent = `System ${resolvedMode}`;
  document.getElementById("broker-engine").textContent = `Engine ${session.engine_mode || "SAFE"}`;
  document.getElementById("broker-session").textContent = `Session ${payload.session_id || session.session_id || "pending"}`;
  document.getElementById("broker-updated").textContent = `Updated ${payload.generated_at || "pending"}`;
  document.getElementById("broker-resolved-mode").textContent = resolvedMode;
  document.getElementById("broker-mode-state").textContent = resolvedMode;
  document.getElementById("broker-readiness-state").textContent = resolvedMode === "LIVE" && liveReady ? "LIVE READY" : "PAPER SAFE";

  document.querySelectorAll("[data-broker-value]").forEach((node) => {
    node.textContent = formatBrokerValue(getValue(node.getAttribute("data-broker-value")));
  });
  document.querySelectorAll("[data-broker-bool]").forEach((node) => {
    node.textContent = getValue(node.getAttribute("data-broker-bool")) ? "YES" : "NO";
  });

  setFlag("broker-session-live", sessionLive);
  setFlag("broker-mode-live", brokerLive);
  setFlag("broker-connection-ready", broker.connected);
  setFlag("broker-live-ready", liveReady);

  const latency = broker.latency_ms;
  document.getElementById("broker-latency").textContent = latency !== undefined && latency !== null ? `${latency} ms` : "-- ms";
  document.getElementById("missing-credential-warning").style.display = Boolean(broker.missing_credentials) ? "block" : "none";
}

async function refreshBroker() {
  const response = await fetch("/api/v1/frontend-state", { cache: "no-store" });
  renderBrokerSnapshot(await response.json());
}

document.querySelector("[data-refresh-broker]").addEventListener("click", refreshBroker);
refreshBroker().catch(() => undefined);
"""



def _margin_page() -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="#111820">
  <title>CSS Margin Visibility</title>
  <style>{_css()}</style>
</head>
<body><div style="background-color:#ffebee;color:#b71c1c;text-align:center;padding:8px;font-weight:bold;font-size:0.85em;border-bottom:1px solid #b71c1c;" aria-label="Risk Warning">Trading involves substantial risk. Loss of capital may occur. Past performance does not guarantee future results.</div>
  <main class="shell">
    <header class="topbar">
      <div class="brand-lockup">
        <div class="brand-mark" aria-hidden="true">CSS</div>
        <div>
          <p class="eyebrow">Capital Strata Systems</p>
          <h1>Canonical Margin Visibility</h1>
        </div>
      </div>
      <section class="status-strip" aria-label="System status">
        <span id="margin-state-header">State PENDING</span>
      </section>
    </header>
    {_app_nav("margin")}

    <section class="control-row" aria-label="Margin controls">
      <button type="button" data-refresh-margin>Refresh</button>
      <span>Read-only margin visibility layer</span>
      <span>No execution modifications</span>
    </section>

    <section class="dashboard-grid">
      <article class="panel wide">
        <div class="panel-head">
          <h2>Margin Snapshot</h2>
          <span id="margin-timestamp">Pending</span>
        </div>
        <div id="margin-data-container" class="kv-grid two">
          <div><strong>Broker</strong><span id="margin-broker">--</span></div>
          <div><strong>Account ID</strong><span id="margin-account-id">--</span></div>
          <div><strong>Equity</strong><span id="margin-equity">--</span></div>
          <div><strong>Cash</strong><span id="margin-cash">--</span></div>
          <div><strong>Buying Power</strong><span id="margin-buying-power">--</span></div>
          <div><strong>Margin Used</strong><span id="margin-margin-used">--</span></div>
          <div><strong>Margin Available</strong><span id="margin-margin-available">--</span></div>
          <div><strong>Maintenance Margin</strong><span id="margin-maintenance-margin">--</span></div>
          <div><strong>Initial Margin</strong><span id="margin-initial-margin">--</span></div>
          <div><strong>Margin Ratio</strong><span id="margin-margin-ratio">--</span></div>
          <div><strong>Margin State</strong><span id="margin-margin-state" style="font-weight:bold;">--</span></div>
        </div>
        <div id="margin-error" style="display:none; color:#ff4d4f; padding:20px; font-weight:bold; font-size:18px;">DATA UNAVAILABLE</div>
      </article>
    </section>
  </main>
  <script>
    function money(val) {{
      return new Intl.NumberFormat("en-US", {{style: "currency", currency: "USD"}}).format(Number(val||0));
    }}
    async function refreshMargin() {{
      try {{
        const response = await fetch("/api/v1/margin-snapshot", {{ cache: "no-store" }});
        const data = await response.json();
        const container = document.getElementById("margin-data-container");
        const errorDiv = document.getElementById("margin-error");
        
        if (!data.ok) {{
          container.style.display = "none";
          errorDiv.style.display = "block";
          document.getElementById("margin-state-header").textContent = "DATA UNAVAILABLE";
          document.getElementById("margin-timestamp").textContent = "DATA UNAVAILABLE";
        }} else {{
          container.style.display = "grid";
          errorDiv.style.display = "none";
          document.getElementById("margin-broker").textContent = data.broker;
          document.getElementById("margin-account-id").textContent = data.account_id;
          document.getElementById("margin-equity").textContent = money(data.equity);
          document.getElementById("margin-cash").textContent = money(data.cash);
          document.getElementById("margin-buying-power").textContent = money(data.buying_power);
          document.getElementById("margin-margin-used").textContent = money(data.margin_used);
          document.getElementById("margin-margin-available").textContent = money(data.margin_available);
          document.getElementById("margin-maintenance-margin").textContent = money(data.maintenance_margin);
          document.getElementById("margin-initial-margin").textContent = money(data.initial_margin);
          document.getElementById("margin-margin-ratio").textContent = Number(data.margin_ratio).toFixed(4);
          
          const stateEl = document.getElementById("margin-margin-state");
          stateEl.textContent = data.margin_state;
          const stateColors = {{
            "NORMAL": "#4caf50",
            "WARNING": "#ff9800",
            "RESTRICTED": "#ff5722",
            "CRITICAL": "#f44336",
            "LIQUIDATION_RISK": "#b71c1c"
          }};
          stateEl.style.color = stateColors[data.margin_state] || "#ffffff";
          
          document.getElementById("margin-state-header").textContent = `State ${{data.margin_state}}`;
          document.getElementById("margin-timestamp").textContent = data.timestamp;
        }}
      }} catch (err) {{
        document.getElementById("margin-data-container").style.display = "none";
        document.getElementById("margin-error").style.display = "block";
      }}
    }}
    document.querySelector("[data-refresh-margin]").addEventListener("click", refreshMargin);
    refreshMargin().catch(() => undefined);
  </script>
</body>
</html>"""


def _css() -> str:
    return """
:root {
  color-scheme: dark;
  --bg: #101316;
  --panel: #171d22;
  --panel-2: #1d252a;
  --ink: #eef5f4;
  --muted: #9cafb2;
  --line: #2d3a40;
  --teal: #38a6a0;
  --gold: #d39b32;
  --blue: #5d8fb8;
  --danger: #df5b52;
  --ok: #70b870;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--ink);
  font-family: "Segoe UI", Arial, sans-serif;
}
.shell {
  width: min(1500px, 100%);
  margin: 0 auto;
  padding: 20px;
}
.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 18px;
  padding: 14px 0 18px;
}
.brand-lockup {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}
.brand-mark {
  width: 58px;
  height: 58px;
  display: grid;
  place-items: center;
  border: 2px solid var(--teal);
  color: #fff;
  font-weight: 800;
  letter-spacing: 0;
  flex: 0 0 auto;
}
.eyebrow {
  margin: 0 0 3px;
  color: var(--muted);
  font-size: 12px;
  text-transform: uppercase;
}
h1, h2, p { margin-top: 0; }
h1 {
  margin-bottom: 0;
  font-size: 28px;
  line-height: 1.1;
  letter-spacing: 0;
}
h2 {
  font-size: 16px;
  margin: 0;
  letter-spacing: 0;
}
.status-strip,
.control-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.status-strip span,
.control-row span {
  border: 1px solid var(--line);
  background: var(--panel);
  color: var(--ink);
  padding: 8px 10px;
  font-size: 12px;
  font-weight: 700;
}
.control-row {
  align-items: center;
  margin-bottom: 14px;
}
.app-nav {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}
.app-nav a {
  border: 1px solid var(--line);
  background: var(--panel);
  color: var(--ink);
  padding: 8px 11px;
  text-decoration: none;
  font-size: 13px;
  font-weight: 800;
}
.app-nav a.active {
  border-color: var(--teal);
  color: var(--teal);
  background: #14292c;
}
button {
  min-height: 36px;
  border: 1px solid var(--teal);
  background: var(--teal);
  color: #06100f;
  padding: 7px 13px;
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
}
.metric-band {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}
.metric-band article,
.panel {
  border: 1px solid var(--line);
  background: var(--panel);
}
.metric-band article {
  min-height: 86px;
  padding: 13px;
}
.metric-band strong,
.kv-grid strong,
.signal-grid strong {
  display: block;
  color: var(--muted);
  font-size: 12px;
  margin-bottom: 6px;
}
.metric-band span {
  font-size: 20px;
  font-weight: 800;
}
.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}
.panel {
  min-height: 248px;
  padding: 14px;
}
.panel.wide {
  grid-column: span 2;
}
.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  border-bottom: 1px solid var(--line);
  padding-bottom: 10px;
  margin-bottom: 12px;
}
.panel-head > span {
  border: 1px solid var(--line);
  background: var(--panel-2);
  padding: 5px 8px;
  color: var(--gold);
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
}
.kv-grid,
.signal-grid {
  display: grid;
  gap: 9px;
}
.kv-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.kv-grid.two {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.signal-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}
.kv-grid div,
.signal-grid div {
  border: 1px solid var(--line);
  background: var(--panel-2);
  padding: 10px;
  min-width: 0;
}
.kv-grid span,
.signal-grid span {
  display: block;
  font-size: 14px;
  font-weight: 800;
  overflow-wrap: anywhere;
}
.table {
  overflow-x: auto;
}
.row {
  display: grid;
  grid-template-columns: 1fr 70px 100px 110px 100px;
  gap: 8px;
  min-width: 540px;
  border-bottom: 1px solid var(--line);
  padding: 9px 0;
}
.row.head {
  color: var(--muted);
  font-size: 12px;
  text-transform: uppercase;
  font-weight: 800;
}
.row span {
  overflow-wrap: anywhere;
  font-weight: 700;
}
.toggle-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}
.toggle-grid span {
  border: 1px solid var(--line);
  padding: 10px;
  font-size: 13px;
  font-weight: 800;
}
.toggle-grid span.on {
  border-color: rgba(112, 184, 112, 0.5);
  color: var(--ok);
}
.toggle-grid span.off {
  border-color: rgba(223, 91, 82, 0.5);
  color: var(--danger);
}
.panel-note {
  margin: 12px 0 0;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.35;
}
.compact-list {
  margin: 12px 0 0;
  padding-left: 17px;
  color: var(--muted);
  font-weight: 700;
}
.empty-state {
  border: 1px dashed var(--line);
  color: var(--muted);
  padding: 14px;
  font-weight: 700;
}
.positions-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(320px, 0.8fr);
  gap: 12px;
}
.trade-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 12px;
}
.execution-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1.65fr) minmax(320px, 0.75fr);
  gap: 12px;
}
.risk-governance-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(340px, 0.8fr);
  gap: 12px;
}
.market-opportunity-workspace {
  display: grid;
  grid-template-columns: minmax(0, 0.95fr) minmax(0, 1.05fr);
  gap: 12px;
}
.broker-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(340px, 0.8fr);
  gap: 12px;
}
.positions-main {
  min-height: 520px;
}
.trade-main {
  min-height: 560px;
}
.execution-main {
  min-height: 520px;
}
.risk-main {
  min-height: 460px;
}
.market-main,
.opportunity-main {
  min-height: 320px;
}
.broker-main {
  min-height: 360px;
}
.positions-side {
  display: grid;
  gap: 12px;
  align-content: start;
}
.execution-side {
  display: grid;
  gap: 12px;
  align-content: start;
}
.risk-governance-side {
  display: grid;
  gap: 12px;
  align-content: start;
}
.broker-side {
  display: grid;
  gap: 12px;
  align-content: start;
}
.compact-panel {
  min-height: 0;
}
.position-table,
.trade-table,
.execution-table,
.opportunity-table,
.summary-table {
  overflow-x: auto;
}
.trade-controls input,
.trade-controls select {
  min-height: 36px;
  border: 1px solid var(--line);
  background: var(--panel);
  color: var(--ink);
  padding: 7px 10px;
  font-size: 13px;
  font-weight: 700;
}
.watch-only-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--line);
  background: var(--panel);
  color: var(--ink);
  padding: 8px 10px;
  font-size: 12px;
  font-weight: 700;
}
.position-row {
  display: grid;
  grid-template-columns: 120px 100px 90px 90px 120px 120px 120px 120px;
  gap: 8px;
  min-width: 880px;
  border-bottom: 1px solid var(--line);
  padding: 10px 0;
  align-items: center;
}
.position-head {
  color: var(--muted);
  font-size: 12px;
  text-transform: uppercase;
  font-weight: 800;
}
.trade-row {
  display: grid;
  grid-template-columns: 90px 110px 100px 110px 110px 110px 110px 90px 170px 85px;
  gap: 8px;
  min-width: 1180px;
  border-bottom: 1px solid var(--line);
  padding: 10px 0;
  align-items: center;
}
.trade-head {
  color: var(--muted);
  font-size: 12px;
  text-transform: uppercase;
  font-weight: 800;
}
.execution-row {
  display: grid;
  grid-template-columns: 210px 120px 90px 80px 80px 120px 180px 90px 110px 90px;
  gap: 8px;
  min-width: 1250px;
  border-bottom: 1px solid var(--line);
  padding: 10px 0;
  align-items: center;
}
.execution-head {
  color: var(--muted);
  font-size: 12px;
  text-transform: uppercase;
  font-weight: 800;
}
.opportunity-row {
  display: grid;
  grid-template-columns: 120px 100px 90px 120px 90px 110px 140px minmax(220px, 1fr);
  gap: 8px;
  min-width: 1060px;
  border-bottom: 1px solid var(--line);
  padding: 10px 0;
  align-items: center;
}
.opportunity-head {
  color: var(--muted);
  font-size: 12px;
  text-transform: uppercase;
  font-weight: 800;
}
.position-row span,
.trade-row span,
.execution-row span,
.opportunity-row span,
.summary-row span {
  overflow-wrap: anywhere;
  font-weight: 700;
}
.watch-btn {
  min-height: 28px;
  border: 1px solid var(--line);
  background: var(--panel-2);
  color: var(--ink);
  padding: 4px 8px;
  font-size: 11px;
  font-weight: 800;
}
.watch-btn.on {
  border-color: rgba(112, 184, 112, 0.5);
  color: var(--ok);
}
.watch-btn.off {
  border-color: rgba(223, 91, 82, 0.5);
  color: var(--danger);
}
.side-badge {
  display: inline-flex;
  border: 1px solid var(--line);
  padding: 4px 7px;
  font-style: normal;
  font-size: 12px;
  font-weight: 900;
}
.side-badge.long,
.side-badge.buy {
  border-color: rgba(112, 184, 112, 0.55);
  color: var(--ok);
}
.side-badge.short,
.side-badge.sell {
  border-color: rgba(223, 91, 82, 0.55);
  color: var(--danger);
}
.positive {
  color: var(--ok);
}
.negative {
  color: var(--danger);
}
.summary-row {
  display: grid;
  grid-template-columns: 1fr 76px 100px 100px;
  gap: 8px;
  border-bottom: 1px solid var(--line);
  padding: 9px 0;
}
.symbol-cloud {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.symbol-cloud span {
  border: 1px solid var(--line);
  background: var(--panel-2);
  padding: 7px 9px;
  font-size: 13px;
  font-weight: 800;
}
.breach-panel {
  margin-top: 14px;
  border: 1px solid var(--line);
  background: var(--panel-2);
  padding: 12px;
}
.breach-panel h3 {
  margin: 0 0 8px;
  font-size: 13px;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0;
}
@media (max-width: 1120px) {
  .metric-band,
  .dashboard-grid,
  .trade-workspace,
  .positions-workspace,
  .execution-workspace,
  .risk-governance-workspace,
  .market-opportunity-workspace,
  .broker-workspace {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 720px) {
  .shell { padding: 14px; }
  .topbar { align-items: flex-start; flex-direction: column; }
  .metric-band,
  .dashboard-grid,
  .trade-workspace,
  .positions-workspace,
  .execution-workspace,
  .risk-governance-workspace,
  .market-opportunity-workspace,
  .broker-workspace,
  .kv-grid,
  .kv-grid.two,
  .signal-grid {
    grid-template-columns: 1fr;
  }
  .panel.wide { grid-column: span 1; }
  h1 { font-size: 24px; }
}
"""


app = create_app()


__all__ = [
    "app",
    "create_app",
    "demo_dashboard_state_provider",
]
