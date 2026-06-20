import sys

code = """
def _trade_status_page(user_ctx: Dict[str, Any], session: Dict[str, Any]) -> str:
    load_local_env()
    
    active_sessions = SessionRuntimeService().get_active_sessions()
    
    if not active_sessions:
        return _page(
            "Trade Status",
            f'''
            <main class="dashboard-shell">
              {_header("Trade Status Summary", user_ctx, "trade-status")}
              {_identity_strip(user_ctx, "Status: Disconnected")}
              <section class="data-panel" aria-label="Disconnected Status">
                <h2>Ledger Data</h2>
                <div class="alert error">DATA UNAVAILABLE: No active CSS runtime session found. Cannot load canonical state.</div>
              </section>
            </main>
            '''
        )
        
    session_id = active_sessions[0]["session_id"]
    snapshot = PnlRuntimeService().get_latest_snapshot(session_id)
    trades = TradeRuntimeService().get_all_session_trades(session_id)
    
    if not snapshot:
        snapshot = {}
        
    trades_html = ""
    for t in trades:
        tid = html.escape(str(t.get("trade_id", "UNKNOWN")))
        sym = html.escape(str(t.get("symbol", "N/A")))
        side = html.escape(str(t.get("direction", "N/A")))
        status = html.escape(str(t.get("status", "UNKNOWN")).upper())
        qty = html.escape(str(t.get("quantity", "0.0")))
        entry = html.escape(str(t.get("entry_price", "0.0")))
        pnl = html.escape(str(t.get("realized_pnl", "0.0")))
        broker = html.escape(str(t.get("broker_name", "UNKNOWN")))
        tstamp = html.escape(str(t.get("opened_at", "")))
        
        trades_html += f'''
        <tr class="trade-row">
          <td><span class="muted">{tstamp[:19] if tstamp else ''}</span><br>{tid[:8]}</td>
          <td><strong>{sym}</strong><br>{side} {qty}</td>
          <td>{entry}<br><span class="muted">{broker}</span></td>
          <td>{status}<br>{pnl}</td>
        </tr>
        '''
        
    if not trades_html:
        trades_html = '<tr><td colspan="4" class="muted center">No canonical trades recorded for this session.</td></tr>'

    return _page(
        "Trade Status",
        f'''
        <main class="dashboard-shell">
          {_header("Trade Status Summary", user_ctx, "trade-status")}
          {_identity_strip(user_ctx, "Status: Canonical")}
          <section class="metric-grid" aria-label="Account Balances">
            <article><strong>Equity</strong><span>{snapshot.get("equity", "DATA UNAVAILABLE")}</span></article>
            <article><strong>Available Cash</strong><span>{snapshot.get("available_cash", "DATA UNAVAILABLE")}</span></article>
            <article><strong>Buying Power</strong><span>{snapshot.get("available_cash", "DATA UNAVAILABLE")}</span></article>
            <article><strong>Open PnL</strong><span>{snapshot.get("unrealized_pnl", "DATA UNAVAILABLE")}</span></article>
            <article><strong>Realized PnL</strong><span>{snapshot.get("realized_pnl", "DATA UNAVAILABLE")}</span></article>
            <article><strong>Total PnL</strong><span>{snapshot.get("net_pnl", "DATA UNAVAILABLE")}</span></article>
            <article><strong>Open Trades</strong><span>{snapshot.get("open_positions", "DATA UNAVAILABLE")}</span></article>
            <article><strong>Winning Trades</strong><span>{snapshot.get("winning_positions", "DATA UNAVAILABLE")}</span></article>
            <article><strong>Losing Trades</strong><span>{snapshot.get("losing_positions", "DATA UNAVAILABLE")}</span></article>
          </section>
          
          <section class="data-panel" aria-label="Trade List">
            <h2>Canonical Trade Ledger</h2>
            <div class="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Time / ID</th>
                    <th>Asset / Side</th>
                    <th>Entry / Broker</th>
                    <th>Status / PnL</th>
                  </tr>
                </thead>
                <tbody>
                  {trades_html}
                </tbody>
              </table>
            </div>
          </section>
        </main>
        ''',
    )
"""

with open("dashboard/mobile/mobile_app.py", "a", encoding="utf-8") as f:
    f.write("\n" + code)
