import os
import re

def update_mobile_app():
    path = "dashboard/mobile/mobile_app.py"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Add nav
    nav_pattern = r'(\("trade-status", "Trade Status", "/trade-status"\),\s*)'
    if '("margin", "Margin", "/margin")' not in content:
        content = re.sub(nav_pattern, r'\1\n        ("margin", "Margin", "/margin"),', content)

    # 2. Add routes
    routes_insertion = """@app.get("/broker", response_class=HTMLResponse)
async def broker_screen(request: Request):
    session = _get_session(request)
    if not session:
        return RedirectResponse("/login", status_code=303)

    return HTMLResponse(_broker_page(session["user_ctx"], session))


@app.get("/margin", response_class=HTMLResponse)
async def margin_screen(request: Request):
    session = _get_session(request)
    if not session:
        return RedirectResponse("/login", status_code=303)

    return HTMLResponse(_margin_page(session["user_ctx"], session))


@app.get("/api/margin-snapshot")
async def margin_api(request: Request):
    session = _get_session(request)
    if not session:
        return JSONResponse({"ok": False, "status": "AUTH_REQUIRED"})
    
    try:
        from dashboard.runtime.broker_credential_check import load_local_env
        load_local_env()
    except Exception:
        pass

    user_ctx = session["user_ctx"]
    try:
        payload = _mobile_dashboard_payload(user_ctx, session)
        def _m(v):
            return v if isinstance(v, dict) else {}
        broker_summary = _m(payload.get("broker_summary"))
        broker = str(broker_summary.get("selected_broker", "NONE")).upper()
        mode = str(broker_summary.get("broker_mode", "SIMULATED")).upper()
    except Exception:
        broker = "NONE"
        mode = "SIMULATED"
    
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
        return JSONResponse({"ok": False, "status": "DATA_UNAVAILABLE"})

    margin_state_val = getattr(snapshot, "margin_state", "UNKNOWN")
    if hasattr(margin_state_val, "value"):
        margin_state_val = margin_state_val.value
    else:
        margin_state_val = str(margin_state_val)

    return JSONResponse({
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
    })
"""
    
    if "async def margin_screen" not in content:
        orig = """@app.get("/broker", response_class=HTMLResponse)
async def broker_screen(request: Request):
    session = _get_session(request)
    if not session:
        return RedirectResponse("/login", status_code=303)

    return HTMLResponse(_broker_page(session["user_ctx"], session))"""
        content = content.replace(orig, routes_insertion)

    # 3. Add _margin_page()
    margin_page_code = '''
def _margin_page(user_ctx: Dict[str, Any], session: Dict[str, Any]) -> str:
    return _page(
        "Margin",
        f"""
        <main class="dashboard-shell">
          {_header("Margin Visibility", user_ctx, "margin")}
          {_identity_strip(user_ctx, "Margin Read-Only")}
          
          <section class="data-panel" aria-label="Margin Snapshot">
            <h2 id="margin-state-header">State PENDING</h2>
            <p class="muted" id="margin-timestamp">Pending</p>
            <div id="margin-data-container" class="metric-grid">
              <article><strong>Broker</strong><span id="margin-broker">--</span></article>
              <article><strong>Account ID</strong><span id="margin-account-id">--</span></article>
              <article><strong>Equity</strong><span id="margin-equity">--</span></article>
              <article><strong>Cash</strong><span id="margin-cash">--</span></article>
              <article><strong>Buying Power</strong><span id="margin-buying-power">--</span></article>
              <article><strong>Margin Used</strong><span id="margin-margin-used">--</span></article>
              <article><strong>Margin Available</strong><span id="margin-margin-available">--</span></article>
              <article><strong>Maintenance Margin</strong><span id="margin-maintenance-margin">--</span></article>
              <article><strong>Initial Margin</strong><span id="margin-initial-margin">--</span></article>
              <article><strong>Margin Ratio</strong><span id="margin-margin-ratio">--</span></article>
              <article><strong>Margin State</strong><span id="margin-margin-state" style="font-weight:bold;">--</span></article>
            </div>
            <div id="margin-error" style="display:none; color:#ff4d4f; padding:20px; font-weight:bold; font-size:18px;">DATA UNAVAILABLE</div>
            <button type="button" data-refresh-margin style="margin-top:20px;">Refresh Margin</button>
          </section>
        </main>
        <script>
          function money(val) {{
            return new Intl.NumberFormat("en-US", {{style: "currency", currency: "USD"}}).format(Number(val||0));
          }}
          async function refreshMargin() {{
            try {{
              const response = await fetch("/api/margin-snapshot", {{ cache: "no-store" }});
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
                stateEl.style.color = stateColors[data.margin_state] || "inherit";
                
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
        """
    )
'''

    if "def _margin_page" not in content:
        content = content.replace("def _audit_page(", margin_page_code + "\n\ndef _audit_page(")

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


if __name__ == "__main__":
    update_mobile_app()
