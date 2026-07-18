(function () {
  "use strict";

  const state = window.CSS_IBKR_SAMPLE_STATE || {};
  let activeScreen = "home";

  function byId(id) {
    return document.getElementById(id);
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

  function setHeader() {
    byId("mobile-mode").textContent = state.resolved_mode || "paper";
    byId("mobile-engine").textContent = state.engine_mode || "SAFE";
    byId("mobile-orders").textContent = state.shadow_mode ? "shadow" : "governed";
  }

  function card(title, body) {
    return "<article class=\"mobile-card\"><h2>" + title + "</h2><div class=\"panel-body\">" + body + "</div></article>";
  }

  function statusRow(label, value) {
    return "<div class=\"status-row\"><span>" + label + "</span><strong>" + value + "</strong></div>";
  }

  function renderHome() {
    const account = state.account_summary || {};
    const pnl = state.pnl_summary || {};
    return [
      card("Home Screen", [
        statusRow("Total Equity", money(account.total_equity)),
        statusRow("Cash Balance", money(account.cash_balance)),
        statusRow("Net PnL", money(pnl.net_pnl)),
        statusRow("Open Positions", String((state.open_positions || {}).total || 0))
      ].join("")),
      card("System Status", [
        statusRow("Resolved Mode", state.resolved_mode || "paper"),
        statusRow("Broker Mode", state.broker_mode || "paper"),
        statusRow("Engine Mode", state.engine_mode || "SAFE"),
        statusRow("Shadow Mode", String(Boolean(state.shadow_mode)))
      ].join(""))
    ].join("");
  }

  function renderPositions() {
    const rows = (state.positions || []).map((position) => card(
      String(position.symbol || "Position"),
      [
        statusRow("Class", String(position.asset_class || "")),
        statusRow("Side", String(position.side || "")),
        statusRow("Qty", String(position.qty || 0)),
        statusRow("Unrealized PnL", money(position.unrealized_pnl))
      ].join("")
    ));
    return rows.join("") || card("Position Screen", statusRow("Positions", "None"));
  }

  function renderExecution() {
    const execution = state.execution_summary || {};
    return [
      card("Execution Screen", [
        statusRow("Execution State", execution.execution_state || "UNKNOWN"),
        statusRow("Accepted", String(execution.accepted_trade_count || 0)),
        statusRow("Rejected", String(execution.rejected_trade_count || 0)),
        statusRow("Pending", String(execution.pending_trade_count || 0)),
        statusRow("Orders", "Shadow only")
      ].join("")),
      card("Ticket Control", "<button class=\"primary-action\" type=\"button\" id=\"mobile-stage-ticket\">Stage Ticket</button><span class=\"pill\" id=\"mobile-ticket-status\">No order sent</span>")
    ].join("");
  }

  function renderRisk() {
    const risk = state.risk_summary || {};
    return card("Risk Screen", [
      statusRow("Risk State", risk.risk_state || "UNKNOWN"),
      statusRow("Gate Status", risk.gate_status || "UNKNOWN"),
      statusRow("Exposure", money(risk.total_exposure)),
      statusRow("Drawdown", Number(risk.current_drawdown_pct || 0).toFixed(2) + "%"),
      statusRow("Position Limit", String(risk.position_limit || 0))
    ].join(""));
  }

  function renderAlerts() {
    const alerts = state.alerts || [];
    return alerts.map((alert) => card("Alerts Center", [
      statusRow("Level", String(alert.level || "info")),
      statusRow("Title", String(alert.title || "")),
      "<p>" + String(alert.detail || "") + "</p>"
    ].join(""))).join("");
  }

  function render() {
    const content = byId("mobile-content");
    const renderers = {
      home: renderHome,
      positions: renderPositions,
      execution: renderExecution,
      risk: renderRisk,
      alerts: renderAlerts
    };
    content.innerHTML = renderers[activeScreen]();
    const stage = byId("mobile-stage-ticket");
    if (stage) {
      stage.addEventListener("click", () => {
        byId("mobile-ticket-status").textContent = "Shadow ticket staged; no order sent";
      });
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    setHeader();
    render();
    document.querySelectorAll("[data-screen]").forEach((button) => {
      button.addEventListener("click", () => {
        activeScreen = button.getAttribute("data-screen") || "home";
        document.querySelectorAll("[data-screen]").forEach((item) => {
          item.classList.remove("active");
          item.removeAttribute("aria-current");
        });
        button.classList.add("active");
        button.setAttribute("aria-current", "page");
        render();
      });
    });
  });
}());
