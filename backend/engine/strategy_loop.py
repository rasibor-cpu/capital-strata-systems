from __future__ import annotations

import os
import time
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.execution.coinbase_executor import CoinbaseExecutor, OrderIntent
from backend.adapters.coinbase_adapter import CoinbaseAdapter
from backend.risk.trading_safety import TradingSafety
from backend.strategy.vwap_mean_reversion import (
    VWAPConfig,
    compute_vwap_from_candles,
)

STATE_FILE = "backend/state/spot_position.json"


def load_position():
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
                return json.load(f)
    except:
        pass
    return None


def save_position(data):
    with open(STATE_FILE, "w") as f:
        json.dump(data, f)


def clear_position():
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)


def _env(name: str, default: str) -> str:
    v = os.getenv(name)
    return default if v is None else str(v).strip()


def _as_float(x, d):
    try:
        return float(x)
    except:
        return d


def _safe_float(x):
    try:
        return float(x)
    except:
        return None


def extract_balance(accounts, currency):
    try:
        for a in accounts.get("accounts", []):
            if a.get("currency") == currency:
                return float(a["available_balance"]["value"])
    except:
        pass
    return 0.0


def run_loop():

    executor = CoinbaseExecutor()
    adapter = CoinbaseAdapter()
    safety = TradingSafety()

    product_id = _env("PRODUCT_ID", "BTC-USDC")

    TP_BPS = _as_float(_env("TP_BPS", "40"), 40)
    SL_BPS = _as_float(_env("SL_BPS", "20"), 20)

    ENTRY_BPS = _as_float(_env("VWAP_ENTRY_BPS", "25"), 25)
    EXIT_BPS = _as_float(_env("VWAP_EXIT_BPS", "4"), 4)

    BUY_SIZE = _as_float(_env("BUY_QUOTE_SIZE_USD", "2"), 2)

    TARGET = _as_float(_env("TARGET_BTC_PCT", "0.30"), 0.30)
    BUFFER = _as_float(_env("ALLOC_BUFFER_PCT", "0.03"), 0.03)

    print("\nVWAP Rotation Engine Running")

    while True:

        try:

            if safety.kill_switch_active():
                print("KILL SWITCH ACTIVE")
                time.sleep(5)
                continue

            bba = executor.get_best_bid_ask(product_id)

            bid = bba["bid"]
            ask = bba["ask"]

            mid = (bid + ask) / 2

            candles = executor.get_candles(product_id, "FIFTEEN_MINUTE")

            vwap = compute_vwap_from_candles(candles["candles"], 40)

            dev_bps = ((mid - vwap) / vwap) * 10000

            accounts = adapter.get_accounts()

            usdc = extract_balance(accounts, "USDC")
            btc = extract_balance(accounts, "BTC")

            btc_value = btc * mid
            total = usdc + btc_value
            btc_pct = btc_value / total if total > 0 else 0

            position = load_position()

            # ------------------------------
            # POSITION MANAGEMENT
            # ------------------------------

            if position:

                entry = position["entry_price"]
                size = position["btc_size"]

                pnl_bps = ((mid - entry) / entry) * 10000

                if pnl_bps >= TP_BPS:
                    print("TP HIT", pnl_bps)

                    executor.create_order(
                        OrderIntent(
                            product_id=product_id,
                            side="SELL",
                            order_type="MARKET",
                            base_size=str(size),
                        )
                    )

                    clear_position()
                    time.sleep(10)
                    continue

                if pnl_bps <= -SL_BPS:
                    print("STOP LOSS", pnl_bps)

                    executor.create_order(
                        OrderIntent(
                            product_id=product_id,
                            side="SELL",
                            order_type="MARKET",
                            base_size=str(size),
                        )
                    )

                    clear_position()
                    time.sleep(10)
                    continue

                if dev_bps >= -EXIT_BPS:
                    print("VWAP EXIT")

                    executor.create_order(
                        OrderIntent(
                            product_id=product_id,
                            side="SELL",
                            order_type="MARKET",
                            base_size=str(size),
                        )
                    )

                    clear_position()
                    time.sleep(10)
                    continue

            # ------------------------------
            # ENTRY LOGIC
            # ------------------------------

            under_target = btc_pct < (TARGET - BUFFER)
            over_target = btc_pct > (TARGET + BUFFER)

            cheap = dev_bps <= -ENTRY_BPS
            rich = dev_bps >= ENTRY_BPS

            action = "HOLD"

            if under_target and cheap:
                action = "BUY"

            elif over_target and rich:
                action = "SELL"

            print(
                f"mid={mid:.2f} vwap={vwap:.2f} dev={dev_bps:.2f}bps "
                f"USDC={usdc:.2f} BTC={btc:.6f} BTC%={btc_pct:.2%} -> {action}"
            )

            if action == "BUY":

                result = executor.create_order(
                    OrderIntent(
                        product_id=product_id,
                        side="BUY",
                        order_type="MARKET",
                        quote_size=str(BUY_SIZE),
                    )
                )

                btc_bought = BUY_SIZE / mid

                save_position(
                    {
                        "entry_price": mid,
                        "btc_size": btc_bought,
                        "time": datetime.now(timezone.utc).isoformat(),
                    }
                )

            elif action == "SELL" and btc > 0:

                executor.create_order(
                    OrderIntent(
                        product_id=product_id,
                        side="SELL",
                        order_type="MARKET",
                        base_size=str(btc * 0.25),
                    )
                )

        except Exception as e:
            print("ENGINE ERROR:", e)

        time.sleep(10)


def main():
    run_loop()


if __name__ == "__main__":
    main()