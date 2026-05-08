(function () {
  "use strict";

  const SAMPLE_STATE = window.CSS_IBKR_SAMPLE_STATE || {};
  const API_PATH = "/api/v1/dashboard-state";
  let latestState = SAMPLE_STATE;

  function byId(id) {
    return document.getElementById(id);
  }

  function setText(id, value) {
    const node = byId(id);
    if (node) node.textContent = String(value);
  }

  function money(value) {
    const number = Number(value || 0);
    return number.toLocaleString("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
  }

  function pct(value) {
    const number = Number(value || 0);
    return number.toFixed(2) + "%";
  }

  function safe(object, path, fallback) {
    return path.reduce((current, key) => {
      if (current && Object.prototype.hasOwnProperty.call(current, key)) {
        return current[key];
      }
      return undefined;
    }, object) ?? fallback;
  }

  function loadApiBase() {
    const stored = sessionStorage.getItem("css_api_base_url")
      || sessionStorage.getItem("rea_api_base_url")
      || "http://127.0.0.1:8000";
    const input = byId("api-base");
    if (input) input.value = stored.replace(/\/+$/, "");
    return stored.replace(/\/+$/, "");
  }

  async function fetchDashboardState() {
    const baseUrl = loadApiBase();
    const token = sessionStorage.getItem("rea_session_token")
      || sessionStorage.getItem("session_token")
      || "";
    const headers = { "Accept": "application/json" };
    if (token) headers.Authorization = "Bearer " + token;

    try {
      const response = await fetch(baseUrl + API_PATH, { headers });
      if (!response.ok) throw new Error("HTTP " + response.status);
      const data = await response.json();
      setText("state-source", "DashboardState API bridge");
      return data;
    } catch (error) {
      setText("state-source", "Shadow sample state");
      return SAMPLE_STATE;
    }
  }

  function renderHeader(state) {
    setText("resolved-mode", state.resolved_mode || "paper");
    setText("broker-mode", state.broker_mode || "paper");
    setText("engine-mode", state.engine_mode || safe(state, ["session", "engine_mode"], "SAFE"));
    setText("orders-state", state.shadow_mode ? "shadow" : "governed");
  }

  function renderAccount(state) {
    const account = state.account_summary || {};
    setText("account-broker", account.broker || safe(state, ["broker_summary", "selected_broker"], "NONE"));
    setText("total-equity", money(account.total_equity));
    setText("cash-balance", money(account.cash_balance));
    setText("buying-power", money(account.buying_power));
    setText("available-margin", money(account.available_margin));
  }

  function renderPnl(state) {
    const pnl = state.pnl_summary || {};
    setText("pnl-source", state.pnl_source ? "canonical bridge" : "presentation");
    setText("realized-pnl", money(pnl.realized_pnl));
    setText("unrealized-pnl", money(pnl.unrealized_pnl));
    setText("net-pnl", money(pnl.net_pnl));
    setText("win-rate", pct(pnl.win_rate));
  }

  function renderBroker(state) {
    const broker = state.broker_summary || {};
    setText("broker-connected", broker.connected ? "online" : "offline");
    setText("selected-broker", broker.selected_broker || "NONE");
    setText("broker-mode-detail", broker.broker_mode || "paper");
    setText("live-trading-enabled", String(Boolean(broker.live_trading_enabled)));
    setText("last-heartbeat", broker.last_heartbeat || "none");
  }

  function renderPositions(state) {
    const body = byId("positions-body");
    if (!body) return;

    const positions = Array.isArray(state.positions) ? state.positions : [];
    setText("open-position-count", safe(state, ["open_positions", "total"], positions.length) + " open");

    body.innerHTML = "";
    if (positions.length === 0) {
      const row = document.createElement("tr");
      row.innerHTML = "<td colspan=\"6\">No positions in current dashboard state</td>";
      body.appendChild(row);
      return;
    }

    positions.forEach((position) => {
      const row = document.createElement("tr");
      const pnlClass = Number(position.unrealized_pnl || 0) >= 0 ? "positive" : "negative";
      row.innerHTML = [
        "<td>" + String(position.symbol || "") + "</td>",
        "<td>" + String(position.asset_class || "") + "</td>",
        "<td>" + String(position.side || "") + "</td>",
        "<td>" + String(position.qty || 0) + "</td>",
        "<td>" + money(position.mark_price) + "</td>",
        "<td class=\"" + pnlClass + "\">" + money(position.unrealized_pnl) + "</td>"
      ].join("");
      body.appendChild(row);
    });
  }

  function renderRisk(state) {
    const risk = state.risk_summary || {};
    setText("risk-state", risk.risk_state || "UNKNOWN");
    setText("gate-status", risk.gate_status || "UNKNOWN");

    const container = byId("risk-bars");
    if (!container) return;
    const bands = Array.isArray(state.risk_bands) ? state.risk_bands : [
      { label: "Drawdown", value: risk.current_drawdown_pct || 0, limit: risk.max_drawdown_pct || 1 },
      { label: "Exposure", value: risk.exposure_utilization_pct || 0, limit: 100 },
      { label: "Positions", value: safe(state, ["open_positions", "total"], 0), limit: risk.position_limit || 1 }
    ];

    container.innerHTML = "";
    bands.forEach((band) => {
      const value = Number(band.value || 0);
      const limit = Math.max(Number(band.limit || 1), 1);
      const utilization = Math.min(100, Math.max(0, (value / limit) * 100));
      const fillClass = utilization > 85 ? "bad" : utilization > 65 ? "warn" : "";
      const wrapper = document.createElement("div");
      wrapper.innerHTML = [
        "<div class=\"status-row\"><span>" + String(band.label) + "</span><strong>" + value.toFixed(2) + " / " + limit.toFixed(2) + "</strong></div>",
        "<div class=\"bar\"><div class=\"bar-fill " + fillClass + "\" style=\"width:" + utilization.toFixed(2) + "%\"></div></div>"
      ].join("");
      container.appendChild(wrapper);
    });
  }

  function renderGovernance(state) {
    const governance = state.governance_summary || {};
    setText("governance-enabled", String(Boolean(governance.governance_enabled)));
    setText("session-locked", String(Boolean(governance.session_locked)));
    setText("defensive-mode", String(Boolean(governance.defensive_mode_active)));
    setText("audit-enabled", String(Boolean(governance.audit_enabled)));
  }

  function renderMarket(state) {
    const market = state.market_summary || {};
    setText("regime-state", market.regime_state || "UNKNOWN");
    setText("trend-state", market.trend_state || "UNKNOWN");
    setText("volatility-state", market.volatility_state || "UNKNOWN");
    setText("liquidity-state", market.liquidity_state || "UNKNOWN");
    setText("vwap-state", market.vwap_state || "UNKNOWN");
  }

  function renderExecution(state) {
    const execution = state.execution_summary || {};
    setText("execution-state", execution.execution_state || "UNKNOWN");
    setText("accepted-trades", execution.accepted_trade_count || 0);
    setText("rejected-trades", execution.rejected_trade_count || 0);
    setText("pending-trades", execution.pending_trade_count || 0);
    setText("total-execution-cost", money(execution.total_execution_cost));
  }

  function renderOpportunities(state) {
    const container = byId("opportunity-list");
    if (!container) return;
    container.innerHTML = "";
    (state.opportunities || []).forEach((item) => {
      const node = document.createElement("div");
      node.className = "opportunity";
      node.innerHTML = [
        "<strong>" + String(item.symbol || "") + " | " + String(item.asset_class || "") + " | Score " + String(item.score || 0) + "</strong>",
        "<p>" + String(item.signal || "") + "</p>"
      ].join("");
      container.appendChild(node);
    });
  }

  function renderAlerts(state) {
    const container = byId("alerts-list");
    if (!container) return;
    const alerts = state.alerts || [];
    setText("alert-count", alerts.length);
    container.innerHTML = "";
    alerts.forEach((alert) => {
      const node = document.createElement("div");
      node.className = "alert";
      node.innerHTML = [
        "<strong>" + String(alert.title || alert.level || "Alert") + "</strong>",
        "<p>" + String(alert.detail || "") + "</p>"
      ].join("");
      container.appendChild(node);
    });
  }

  function drawEquity(state) {
    const canvas = byId("equity-chart");
    if (!canvas || !canvas.getContext) return;
    const values = state.equity_series || [];
    const ctx = canvas.getContext("2d");
    const width = canvas.width;
    const height = canvas.height;
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = "#0b0f0d";
    ctx.fillRect(0, 0, width, height);
    ctx.strokeStyle = "#27302c";
    ctx.lineWidth = 1;
    for (let i = 1; i < 4; i += 1) {
      const y = (height / 4) * i;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }
    if (values.length < 2) return;
    const min = Math.min.apply(null, values);
    const max = Math.max.apply(null, values);
    const range = Math.max(max - min, 1);
    ctx.strokeStyle = "#40d67d";
    ctx.lineWidth = 3;
    ctx.beginPath();
    values.forEach((value, index) => {
      const x = (width / (values.length - 1)) * index;
      const y = height - ((value - min) / range) * (height - 24) - 12;
      if (index === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
  }

  function render(state) {
    latestState = state;
    renderHeader(state);
    renderAccount(state);
    renderPnl(state);
    renderBroker(state);
    renderPositions(state);
    renderRisk(state);
    renderGovernance(state);
    renderMarket(state);
    renderExecution(state);
    renderOpportunities(state);
    renderAlerts(state);
    drawEquity(state);
  }

  function bindControls() {
    const save = byId("save-api-base");
    if (save) {
      save.addEventListener("click", () => {
        const input = byId("api-base");
        const value = input ? input.value.replace(/\/+$/, "") : "http://127.0.0.1:8000";
        sessionStorage.setItem("css_api_base_url", value);
        setText("action-status", "API base saved");
      });
    }

    const refresh = byId("refresh-state");
    if (refresh) {
      refresh.addEventListener("click", async () => {
        setText("action-status", "Refreshing state");
        render(await fetchDashboardState());
        setText("action-status", "State refreshed");
      });
    }

    const stage = byId("stage-shadow-ticket");
    if (stage) {
      stage.addEventListener("click", () => {
        const mode = latestState.resolved_mode || "paper";
        setText("action-status", "Shadow ticket staged in " + mode + " mode; no order sent");
      });
    }
  }

  document.addEventListener("DOMContentLoaded", async () => {
    bindControls();
    setText("state-source", "Shadow sample state");
    render(SAMPLE_STATE);
    render(await fetchDashboardState());
  });
}());
