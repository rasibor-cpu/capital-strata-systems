from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI
from fastapi.responses import HTMLResponse


PROJECT_ROOT = Path(__file__).resolve().parents[1]

STATE_DIR = PROJECT_ROOT / "backend" / "state"
AUDIT_DIR = PROJECT_ROOT / "audit_logs"

SPOT_FILE = STATE_DIR / "spot_position.json"
ACCOUNT_FILE = STATE_DIR / "account_state.json"
TRADES_FILE = AUDIT_DIR / "trades.jsonl"

app = FastAPI(title="CSS Mobile Dashboard")


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    return rows


def safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def money(v: float) -> str:
    sign = "-" if v < 0 else ""
    return f"{sign}${abs(v):,.2f}"


def compute() -> Dict[str, Any]:
    spot = read_json(SPOT_FILE)
    acct = read_json(ACCOUNT_FILE)
    trades = read_jsonl(TRADES_FILE)

    positions = spot.get("positions", [])
    if not isinstance(positions, list):
        positions = []

    cash = safe_float(
        acct.get("cash")
        or acct.get("cash_usd")
        or acct.get("available_cash")
        or 0
    )

    market = 0.0
    unreal = 0.0
    normalized_positions: List[Dict[str, Any]] = []

    for p in positions:
        asset = str(p.get("asset") or p.get("symbol") or "UNKNOWN")
        value = safe_float(p.get("market_value"))
        if value == 0.0:
            qty = safe_float(p.get("quantity") or p.get("qty"))
            px = safe_float(p.get("current_price") or p.get("price"))
            value = qty * px

        upnl = safe_float(p.get("unrealized_pnl"))
        market += value
        unreal += upnl

        normalized_positions.append(
            {
                "asset": asset,
                "market_value": value,
                "unrealized_pnl": upnl,
            }
        )

    normalized_positions.sort(key=lambda x: abs(x["market_value"]), reverse=True)

    realized = 0.0
    fees = 0.0
    normalized_trades: List[Dict[str, Any]] = []

    for t in trades:
        asset = str(t.get("asset") or t.get("symbol") or "UNKNOWN")
        gross = safe_float(t.get("realized_pnl") or t.get("pnl"))
        fee = safe_float(t.get("fee") or t.get("fees"))
        net = gross - fee

        realized += gross
        fees += fee

        normalized_trades.append(
            {
                "asset": asset,
                "net_pnl": net,
            }
        )

    realized_net = realized - fees
    equity = cash + market
    pnl = realized_net + unreal

    return {
        "cash": cash,
        "market": market,
        "equity": equity,
        "realized": realized_net,
        "unreal": unreal,
        "pnl": pnl,
        "positions": normalized_positions[:4],
        "trades": normalized_trades[-3:],
    }


@app.get("/api/mobile")
def mobile_api() -> Dict[str, Any]:
    return compute()


@app.get("/", response_class=HTMLResponse)
def mobile_home() -> str:
    data = compute()

    positions_html = "".join(
        f"""
        <div class="row">
          <div>
            <div class="asset">{p['asset']}</div>
            <div class="sub">UPnL {money(p['unrealized_pnl'])}</div>
          </div>
          <div class="value">{money(p['market_value'])}</div>
        </div>
        """
        for p in data["positions"]
    ) or '<div class="empty">No open positions</div>'

    trades_html = "".join(
        f"""
        <div class="row">
          <div class="asset">{t['asset']}</div>
          <div class="value">{money(t['net_pnl'])}</div>
        </div>
        """
        for t in data["trades"]
    ) or '<div class="empty">No trades</div>'

    return f"""
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <meta http-equiv="refresh" content="30">
      <title>CSS Mobile Dashboard</title>
      <style>
        body {{
          margin: 0;
          background: #000;
          color: #f5d67b;
          font-family: Arial, sans-serif;
        }}
        .wrap {{
          max-width: 420px;
          margin: 0 auto;
          padding: 14px;
        }}
        .title {{
          font-size: 20px;
          font-weight: 700;
          margin-bottom: 4px;
        }}
        .time {{
          font-size: 12px;
          color: #d7c07a;
          margin-bottom: 14px;
        }}
        .card {{
          border: 1px solid #7a6422;
          border-radius: 12px;
          padding: 12px;
          margin-bottom: 12px;
          background: #0a0a0a;
        }}
        .card h3 {{
          margin: 0 0 10px 0;
          font-size: 15px;
        }}
        .metric {{
          display: flex;
          justify-content: space-between;
          margin: 6px 0;
          font-size: 15px;
        }}
        .row {{
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 8px 0;
          border-top: 1px solid #2b2410;
        }}
        .row:first-of-type {{
          border-top: none;
          padding-top: 0;
        }}
        .asset {{
          font-weight: 700;
          font-size: 14px;
        }}
        .sub {{
          font-size: 12px;
          color: #d7c07a;
          margin-top: 2px;
        }}
        .value {{
          font-weight: 700;
          font-size: 14px;
        }}
        .empty {{
          color: #d7c07a;
          font-size: 13px;
        }}
      </style>
    </head>
    <body>
      <div class="wrap">
        <div class="title">CSS Mobile Dashboard</div>
        <div class="time">Auto-refresh 30s</div>

        <div class="card">
          <h3>Balance</h3>
          <div class="metric"><span>Cash</span><span>{money(data["cash"])}</span></div>
          <div class="metric"><span>Position Value</span><span>{money(data["market"])}</span></div>
          <div class="metric"><span>Equity</span><span>{money(data["equity"])}</span></div>
          <div class="metric"><span>Net P&amp;L</span><span>{money(data["pnl"])}</span></div>
          <div class="metric"><span>R / U</span><span>{money(data["realized"])} / {money(data["unreal"])}</span></div>
        </div>

        <div class="card">
          <h3>Top Positions</h3>
          {positions_html}
        </div>

        <div class="card">
          <h3>Last Trades</h3>
          {trades_html}
        </div>
      </div>
    </body>
    </html>
    """ 