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
@media (max-width: 1120px) {
  .metric-band,
  .dashboard-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 720px) {
  .shell { padding: 14px; }
  .topbar { align-items: flex-start; flex-direction: column; }
  .metric-band,
  .dashboard-grid,
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
