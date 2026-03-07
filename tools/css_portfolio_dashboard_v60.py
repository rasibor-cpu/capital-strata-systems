import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]

PAPER_FILE = PROJECT_ROOT / "audit_logs" / "paper_trades.jsonl"
OPEN_FILE = PROJECT_ROOT / "audit_logs" / "open_trades.json"

STARTING_CAPITAL = 200
RISK_PER_TRADE = 2

REFRESH_SECONDS = 20
MAX_PRODUCTS = 40
TOP_DISPLAY = 5

READY_SCORE = 75
WATCH_SCORE = 60

MIN_PRICE = 0.25
MAX_POSITION_PCT = 0.20
MIN_VOLUME_24H = 5_000_000

TRADE_COOLDOWN_MINUTES = 15

COINBASE_PRODUCTS = "https://api.exchange.coinbase.com/products"
COINBASE_TICKER = "https://api.exchange.coinbase.com/products/{}/ticker"
COINBASE_STATS = "https://api.exchange.coinbase.com/products/{}/stats"
COINBASE_CANDLES = "https://api.exchange.coinbase.com/products/{}/candles?granularity=900"

session = requests.Session()


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def fetch_json(url):
    try:
        r = session.get(url, timeout=5)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None


def load_open_trades():

    if not OPEN_FILE.exists():
        return []

    try:
        with open(OPEN_FILE, "r") as f:
            return json.load(f)
    except:
        return []


def save_open_trades(trades):

    OPEN_FILE.parent.mkdir(exist_ok=True)

    with open(OPEN_FILE, "w") as f:
        json.dump(trades, f, indent=2)


def log_closed_trade(trade):

    PAPER_FILE.parent.mkdir(exist_ok=True)

    with open(PAPER_FILE, "a") as f:
        f.write(json.dumps(trade) + "\n")


def discover_products():

    payload = fetch_json(COINBASE_PRODUCTS)

    products = []

    if isinstance(payload, list):

        for p in payload:

            pid = p.get("id")

            if pid and pid.endswith("-USD"):
                products.append(pid)

    return sorted(products)[:MAX_PRODUCTS]


def price(product):

    data = fetch_json(COINBASE_TICKER.format(product))

    if isinstance(data, dict):

        try:
            return float(data["price"])
        except:
            return None

    return None


def volume_24h(product):

    stats = fetch_json(COINBASE_STATS.format(product))

    if isinstance(stats, dict):

        try:
            volume = float(stats["volume"])
            price_est = float(stats["last"])
            return volume * price_est
        except:
            return 0

    return 0


def candles(product):

    data = fetch_json(COINBASE_CANDLES.format(product))

    if not isinstance(data, list):
        return []

    data.sort(key=lambda x: x[0])

    return data


def vwap(c):

    pv = 0
    vol = 0

    for row in c:

        low = float(row[1])
        high = float(row[2])
        close = float(row[4])
        volume = float(row[5])

        tp = (low + high + close) / 3

        pv += tp * volume
        vol += volume

    if vol == 0:
        return None

    return pv / vol


def trend(c):

    closes = [float(x[4]) for x in c]

    if len(closes) < 10:
        return "NEUTRAL"

    sma5 = sum(closes[-5:]) / 5
    sma10 = sum(closes[-10:]) / 10

    last = closes[-1]

    if last > sma5 > sma10:
        return "BULLISH"

    if last < sma5 < sma10:
        return "BEARISH"

    return "NEUTRAL"


def score(spread, trend):

    s = abs(spread)

    if s > 900:
        spread_score = 60
    elif s > 700:
        spread_score = 50
    elif s > 500:
        spread_score = 40
    else:
        spread_score = 30

    trend_score = 0

    if spread < 0:
        if trend == "BULLISH":
            trend_score = 30
        elif trend == "NEUTRAL":
            trend_score = 20
    else:
        if trend == "BEARISH":
            trend_score = 30
        elif trend == "NEUTRAL":
            trend_score = 20

    return min(100, spread_score + trend_score)


def readiness(score):

    if score >= READY_SCORE:
        return "READY"

    if score >= WATCH_SCORE:
        return "WATCH"

    return "IGNORE"


def generate_trade(product, price_now, vwap_val, spread, direction):

    target = vwap_val

    distance = abs(price_now - vwap_val)

    stop = price_now + distance * 1.5 if direction == "SHORT" else price_now - distance * 1.5

    stop_distance = abs(price_now - stop)

    if stop_distance < price_now * 0.005:
        return None

    size = RISK_PER_TRADE / stop_distance

    position_value = size * price_now

    max_position = STARTING_CAPITAL * MAX_POSITION_PCT

    if position_value > max_position:

        size = max_position / price_now
        position_value = max_position

    trade = {

        "asset": product,
        "direction": direction,
        "entry": price_now,
        "target": target,
        "stop": stop,
        "size": size,
        "open_time": datetime.utcnow().isoformat()
    }

    return trade


def update_open_trades():

    trades = load_open_trades()

    active = []

    closed = []

    for t in trades:

        current = price(t["asset"])

        if not current:
            active.append(t)
            continue

        if t["direction"] == "LONG":

            if current >= t["target"]:
                result = (t["target"] - t["entry"]) * t["size"]
                t["result"] = result
                t["exit"] = t["target"]
                closed.append(t)
                continue

            if current <= t["stop"]:
                result = (t["stop"] - t["entry"]) * t["size"]
                t["result"] = result
                t["exit"] = t["stop"]
                closed.append(t)
                continue

        if t["direction"] == "SHORT":

            if current <= t["target"]:
                result = (t["entry"] - t["target"]) * t["size"]
                t["result"] = result
                t["exit"] = t["target"]
                closed.append(t)
                continue

            if current >= t["stop"]:
                result = (t["entry"] - t["stop"]) * t["size"]
                t["result"] = result
                t["exit"] = t["stop"]
                closed.append(t)
                continue

        active.append(t)

    for c in closed:
        log_closed_trade(c)

    save_open_trades(active)

    return active, closed


def scan():

    products = discover_products()

    results = []

    new_trades = []

    for p in products:

        p_price = price(p)

        if not p_price or p_price < MIN_PRICE:
            continue

        liquidity = volume_24h(p)

        if liquidity < MIN_VOLUME_24H:
            continue

        c = candles(p)

        if not c:
            continue

        v = vwap(c)

        if not v:
            continue

        spread = ((p_price - v) / v) * 10000

        t = trend(c)

        s = score(spread, t)

        status = readiness(s)

        direction = "LONG" if spread < 0 else "SHORT"

        results.append((p, p_price, v, spread, t, s, status, direction))

        if status == "READY":

            trade = generate_trade(p, p_price, v, spread, direction)

            if trade:
                new_trades.append(trade)

    results.sort(key=lambda x: x[5], reverse=True)

    return results, new_trades


def dashboard():

    while True:

        results, new_trades = scan()

        active, closed = update_open_trades()

        if new_trades:

            active.extend(new_trades)

            save_open_trades(active)

        clear()

        print("========================================================")
        print(" CAPITAL STRATA SYSTEMS — TRADE LIFECYCLE ENGINE (v67)")
        print("========================================================")

        print("Time:", datetime.now())

        print("\nOPEN TRADES\n")

        if active:

            for t in active:

                current = price(t["asset"])

                pnl = (current - t["entry"]) * t["size"] if t["direction"] == "LONG" else (t["entry"] - current) * t["size"]

                print(
                    f"{t['direction']} {t['asset']} "
                    f"Entry {t['entry']:.4f} "
                    f"Current {current:.4f} "
                    f"Target {t['target']:.4f} "
                    f"PnL ${pnl:.2f}"
                )

        else:

            print("No open trades")

        print("\nRECENTLY CLOSED\n")

        for c in closed:

            print(
                f"{c['direction']} {c['asset']} "
                f"Exit {c['exit']:.4f} "
                f"Result ${c['result']:.2f}"
            )

        print("\nTOP OPPORTUNITIES\n")

        for i, r in enumerate(results[:TOP_DISPLAY], 1):

            p, price_now, vwap_val, spread, trend_dir, score_val, status, signal = r

            print(
                f"{i}. {p} Score {score_val} {status} "
                f"Price {price_now:.2f} VWAP {vwap_val:.2f} "
                f"Spread {spread:.1f}bps {trend_dir} {signal}"
            )

        print("\nPress Ctrl+C to stop")

        time.sleep(REFRESH_SECONDS)


if __name__ == "__main__":
    dashboard()