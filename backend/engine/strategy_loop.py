import json
import os
import time
from datetime import datetime, timezone

from backend.execution.coinbase_executor import CoinbaseExecutor, OrderIntent


PRODUCT_ID = "BTC-USDC"

VWAP_WINDOW = 40
ENTRY_BPS = 25
EXIT_BPS = 4

TP_BPS = 40
SL_BPS = 20

BUY_QUOTE_SIZE = 2.0

STATE_FILE = "backend/state/spot_position.json"
JOURNAL_FILE = "audit_logs/trades.jsonl"

GRANULARITY = "FIFTEEN_MINUTE"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def load_state():
    if not os.path.exists(STATE_FILE):
        return None

    with open(STATE_FILE) as f:
        return json.load(f)


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def log_trade(event):

    os.makedirs(os.path.dirname(JOURNAL_FILE), exist_ok=True)

    with open(JOURNAL_FILE, "a") as f:
        f.write(json.dumps(event) + "\n")


def normalize_candles(resp):

    if not resp:
        return []

    if isinstance(resp, dict):
        candles = resp.get("candles", [])
    else:
        candles = resp

    return candles


def calc_vwap(candles):

    closes = []

    for c in candles[-VWAP_WINDOW:]:
        closes.append(float(c["close"]))

    if not closes:
        return None

    return sum(closes) / len(closes)


def run_loop():

    executor = CoinbaseExecutor()

    print("Strategy loop started (VWAP Rotation | Target Allocation | Spot Safe | TP/SL | Vol-Adaptive Entry).")

    while True:

        bba = executor.get_best_bid_ask(PRODUCT_ID)

        if not bba:
            print("NO_BBA — skipping tick")
            time.sleep(10)
            continue

        bid = bba["bid"]
        ask = bba["ask"]
        mid = (bid + ask) / 2

        candles_resp = executor.get_candles(product_id=PRODUCT_ID, granularity=GRANULARITY)

        candles = normalize_candles(candles_resp)

        if not candles or len(candles) < VWAP_WINDOW:
            print("NO_CANDLES — skipping tick")
            time.sleep(10)
            continue

        vwap = calc_vwap(candles)

        dev = (mid - vwap) / vwap * 10000

        state = load_state()

        print(f"mid={mid:.2f} vwap={vwap:.2f} dev={dev:.2f}bps")

        # -------------------------------------------------
        # NO POSITION -> ENTRY
        # -------------------------------------------------

        if state is None:

            if dev <= -ENTRY_BPS:

                intent = OrderIntent(
                    product_id=PRODUCT_ID,
                    side="BUY",
                    order_type="MARKET",
                    quote_size=str(BUY_QUOTE_SIZE)
                )

                resp = executor.create_order(intent)

                entry_price = ask

                position = {
                    "entry_price": entry_price,
                    "size_usd": BUY_QUOTE_SIZE,
                    "timestamp": utc_now()
                }

                save_state(position)

                log_trade({
                    "event": "BUY",
                    "price": entry_price,
                    "timestamp": utc_now(),
                    "vwap": vwap
                })

                print("BUY EXECUTED (paper)", entry_price)

        # -------------------------------------------------
        # POSITION OPEN -> EXIT
        # -------------------------------------------------

        else:

            entry = state["entry_price"]

            pnl_bps = (mid - entry) / entry * 10000

            if pnl_bps >= TP_BPS:

                intent = OrderIntent(
                    product_id=PRODUCT_ID,
                    side="SELL",
                    order_type="MARKET",
                    base_size=None
                )

                executor.create_order(intent)

                log_trade({
                    "event": "TP",
                    "price": bid,
                    "entry": entry,
                    "pnl_bps": pnl_bps,
                    "timestamp": utc_now()
                })

                os.remove(STATE_FILE)

                print("TAKE PROFIT", pnl_bps)

            elif pnl_bps <= -SL_BPS:

                intent = OrderIntent(
                    product_id=PRODUCT_ID,
                    side="SELL",
                    order_type="MARKET",
                    base_size=None
                )

                executor.create_order(intent)

                log_trade({
                    "event": "STOP LOSS",
                    "price": bid,
                    "entry": entry,
                    "pnl_bps": pnl_bps,
                    "timestamp": utc_now()
                })

                os.remove(STATE_FILE)

                print("STOP LOSS", pnl_bps)

        time.sleep(10)