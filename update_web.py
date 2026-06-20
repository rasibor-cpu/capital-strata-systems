import os
import re

def update_web_app():
    path = "dashboard/web/web_app.py"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Add /margin to nav
    nav_pattern = r'(\("broker", "/broker", "Broker"\),\s*)]'
    if '("margin", "/margin", "Margin")' not in content:
        content = re.sub(nav_pattern, r'\1\n        ("margin", "/margin", "Margin"),\n    ]', content)

    # 2. Add routes
    routes_insertion = """    @app.get("/broker", response_class=HTMLResponse)
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
"""
    
    if "def margin_view()" not in content:
        content = content.replace("""    @app.get("/broker", response_class=HTMLResponse)
    async def broker() -> HTMLResponse:
        return HTMLResponse(_broker_page())""", routes_insertion)

    # 3. Add _margin_page()
    margin_page_code = '''
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
'''

    if "def _margin_page() -> str:" not in content:
        content = content.replace("def _css() -> str:", margin_page_code + "\n\ndef _css() -> str:")

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


if __name__ == "__main__":
    update_web_app()
