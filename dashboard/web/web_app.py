from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse

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
        title="Capital Strata Systems Institutional Web Dashboard",
        version="0.1.0",
    )
    app.include_router(create_dashboard_state_router(provider))
    app.include_router(create_ws_router(provider))

    @app.get("/", include_in_schema=False)
    async def index() -> RedirectResponse:
        return RedirectResponse("/dashboard", status_code=303)

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard() -> HTMLResponse:
        return HTMLResponse(_dashboard_page())

    @app.get("/positions", response_class=HTMLResponse)
    async def positions() -> HTMLResponse:
        return HTMLResponse(_positions_page())

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
        ("execution", "/execution", "Execution"),
        ("risk_governance", "/risk-governance", "Risk & Governance"),
        ("market_opportunities", "/market-opportunities", "Market"),
        ("broker", "/broker", "Broker"),
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


def _dashboard_page() -> str:
    panel_ids = json.dumps(
        [
            "account_summary",
            "pnl_summary",
            "positions",
            "risk",
            "governance",
            "market",
            "execution",
            "broker",
            "opportunities",
        ]
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="#111820">
  <title>CSS Institutional Web Dashboard</title>
  <style>{_css()}</style>
</head>
<body>
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
      const [section, key] = path.split(".");
      return state.sections?.[section]?.[key];
    }}

    function formatField(path, value) {{
      if (["cash_balance", "total_equity", "buying_power", "margin_used", "available_margin", "net_pnl", "total_exposure", "daily_loss_limit", "total_execution_cost"].some((key) => path.endsWith(key))) {{
        return money(value);
      }}
      if (["win_rate_pct", "exposure_utilization_pct", "current_drawdown_pct"].some((key) => path.endsWith(key))) {{
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

    async function refresh() {{
      const response = await fetch("/api/v1/frontend-state", {{ cache: "no-store" }});
      render(await response.json());
    }}

    function connectSocket() {{
      const indicator = document.getElementById("status-ws");
      const protocol = location.protocol === "https:" ? "wss" : "ws";
      const socket = new WebSocket(`${{protocol}}://${{location.host}}/ws/v1/dashboard-state`);
      let lastSequence = -1;
      const deltaTypes = new Set([
        "dashboard_delta",
        "pnl_update",
        "position_update",
        "governance_alert",
        "execution_alert",
        "broker_status",
        "risk_update"
      ]);
      socket.addEventListener("open", () => {{ indicator.textContent = "WebSocket live"; }});
      socket.addEventListener("message", (event) => {{
        const message = JSON.parse(event.data);
        if (Number(message.sequence ?? -1) <= lastSequence && message.message_type !== "dashboard_snapshot") {{
          indicator.textContent = "WebSocket stale update ignored";
          return;
        }}
        if (message.message_type === "dashboard_snapshot") {{
          lastSequence = Number(message.sequence ?? lastSequence);
          render(message);
          return;
        }}
        if (deltaTypes.has(message.message_type)) {{
          lastSequence = Number(message.sequence ?? lastSequence);
          state.sections = {{ ...state.sections, ...(message.data || {{}}) }};
          render({{
            ...(state.payload || {{}}),
            generated_at: message.generated_at || state.payload?.generated_at,
            sequence: message.sequence ?? state.payload?.sequence,
            sections: state.sections
          }});
          return;
        }}
        if (message.message_type === "dashboard_heartbeat") {{
          lastSequence = Number(message.sequence ?? lastSequence);
          indicator.textContent = `WebSocket live · seq ${{message.sequence ?? "?"}}`;
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
  <meta name="theme-color" content="#111820">
  <title>CSS Professional Positions</title>
  <style>{_css()}</style>
</head>
<body>
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
  <meta name="theme-color" content="#111820">
  <title>CSS Execution History</title>
  <style>{_css()}</style>
</head>
<body>
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
  <meta name="theme-color" content="#111820">
  <title>CSS Risk & Governance Center</title>
  <style>{_css()}</style>
</head>
<body>
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


def _market_opportunities_page() -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="#111820">
  <title>CSS Market & Opportunity Center</title>
  <style>{_css()}</style>
</head>
<body>
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
          <span id="opportunity-count-badge">0 ITEMS</span>
        </div>
        <div class="opportunity-table" id="opportunity-table"></div>
      </article>
    </section>
  </main>

  <script>{_market_opportunities_script()}</script>
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
    target.innerHTML = `<div class="empty-state">No active opportunities</div>`;
    return;
  }
  target.innerHTML = `
    <div class="opportunity-row opportunity-head">
      <span>Symbol</span><span>Asset</span><span>Side</span><span>Signal</span><span>Score</span><span>Probability</span><span>Status</span><span>Reason</span>
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
        <span>${escapeHtml(item.reason || "")}</span>
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
<body>
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
.execution-table,
.opportunity-table,
.summary-table {
  overflow-x: auto;
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
.execution-row span,
.opportunity-row span,
.summary-row span {
  overflow-wrap: anywhere;
  font-weight: 700;
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
