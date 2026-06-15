from __future__ import annotations

"""
Live Manual FX Runner (PERSONAL MODULE)

Flow:
- Load config.json
- Fetch live prices from OANDA
- Apply simple VWAP-distance trigger (personal baseline)
- Create trade ticket
- REQUIRE explicit human confirmation ("YES")
- Send order to OANDA (market)

Safety:
- Manual-confirm only
- Respects config risk flags
- No background loops; single-run execution
"""
import sys
sys.exit("NON-CANONICAL RETIREMENT CANDIDATE: Use run_css.py instead.")

import json
import os
import sys
import time
from typing import Dict, Any

from broker_oanda import OandaConfig, OandaClient
from trade_ticket import TradeTicket, ManualTradeGate


# -------------------------
# Helpers
# -------------------------

def load_config(path: str = "config.json") -> Dict[str, Any]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def ensure_dir(p: str) -> None:
    d = os.path.dirname(p)
    if d:
        os.makedirs(d, exist_ok=True)

def pip_value(instrument: str) -> float:
    # Simple heuristic for majors
    return 0.01 if instrument.endswith("_JPY") else 0.0001


# -------------------------
# Strategy (baseline)
# -------------------------

def vwap_distance_signal(price: float, vwap: float, epsilon: float) -> str:
    """
    Returns: 'buy', 'sell', or ''
    """
    if abs(price - vwap) < epsilon:
        return ""
    return "buy" if price < vwap else "sell"


# -------------------------
# Main
# -------------------------

def main() -> int:
    cfg = load_config("config.json")

    # ---- system / risk gates ----
    if not cfg["risk"].get("trading_enabled", False):
        print("Trading is DISABLED in config.json (risk.trading_enabled=false).")
        print("Set it to true when you are ready to trade.")
        return 0

    if cfg["risk"].get("kill_switch", False):
        print("KILL SWITCH is ON. Aborting.")
        return 0

    # ---- broker ----
    o_cfg = OandaConfig(
        environment=cfg["oanda"]["environment"],
        api_url_practice=cfg["oanda"]["api_url_practice"],
        api_url_live=cfg["oanda"]["api_url_live"],
        account_id_env=cfg["oanda"]["account_id_env"],
        token_env=cfg["oanda"]["token_env"],
    )
    client = OandaClient(o_cfg)

    instruments = cfg["instruments"]["enabled"]
    instruments_csv = ",".join(instruments)

    # ---- pricing ----
    pricing = client.get_prices(instruments_csv)
    prices = {}

    for p in pricing.get("prices", []):
        inst = p["instrument"]
        bids = p.get("bids", [])
        asks = p.get("asks", [])
        if not bids or not asks:
            continue
        mid = (float(bids[0]["price"]) + float(asks[0]["price"])) / 2.0
        prices[inst] = mid

    if not prices:
        print("No prices received.")
        return 0

    # ---- baseline VWAP (simple proxy: last price) ----
    # Personal module: we approximate VWAP with current mid for first live version
    # This will be replaced with rolling VWAP in next iteration
    accuracy_mode = cfg["strategy"]["accuracy_mode"]
    mode_cfg = cfg["strategy"]["modes"][accuracy_mode]
    epsilon = mode_cfg["epsilon_gate"]

    # ---- logging ----
    ensure_dir(cfg["logging"]["prices_log"])
    with open(cfg["logging"]["prices_log"], "a", encoding="utf-8") as f:
        f.write(json.dumps(prices) + "\n")

    # ---- pick first signalable instrument ----
    chosen = None
    side = ""

    for inst, price in prices.items():
        vwap = price  # placeholder proxy
        s = vwap_distance_signal(price, vwap, epsilon)
        if s:
            chosen = inst
            side = s
            break

    if not chosen:
        print("No signal met epsilon threshold. No trade.")
        return 0

    units = int(cfg["risk"]["default_units"])
    if units > int(cfg["risk"]["max_units"]):
        units = int(cfg["risk"]["max_units"])

    pv = pip_value(chosen)
    sl = None
    tp = None

    if cfg["risk"].get("require_sl_tp", False):
        sl_pips = cfg["risk"]["default_sl_pips"]
        tp_pips = cfg["risk"]["default_tp_pips"]
        if side == "buy":
            sl = prices[chosen] - sl_pips * pv
            tp = prices[chosen] + tp_pips * pv
        else:
            sl = prices[chosen] + sl_pips * pv
            tp = prices[chosen] - tp_pips * pv

    # ---- trade ticket ----
    ensure_dir(cfg["logging"]["tickets_log"])
    gate = ManualTradeGate(cfg["logging"]["tickets_log"])

    ticket = TradeTicket(
        instrument=chosen,
        side=side,
        units=units,
        price_snapshot=prices[chosen],
        stop_loss=sl,
        take_profit=tp,
        reason=f"VWAP-distance baseline ({accuracy_mode})"
    )

    if not gate.present_and_confirm(ticket):
        return 0

    # ---- send order ----
    ensure_dir(cfg["logging"]["orders_log"])
    try:
        resp = client.place_market_order(
            instrument=chosen,
            units=units,
            side=side,
            stop_loss_price=sl,
            take_profit_price=tp
        )
        with open(cfg["logging"]["orders_log"], "a", encoding="utf-8") as f:
            f.write(json.dumps(resp) + "\n")
        print("Order sent successfully.")
    except Exception as e:
        print(f"Order failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())