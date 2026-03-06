"""
Capital Strata Systems
Autonomous Trading Engine v49

New in v49
----------
• top 5 opportunities
• ATR risk-based sizing
• trailing stop management
• portfolio-level risk governor
"""

from __future__ import annotations

import json
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests


COINBASE = "https://api.exchange.coinbase.com"

ACCOUNT_EQUITY = 1000.0
RISK_PER_TRADE = 0.01
MAX_PORTFOLIO_RISK = 0.05
MAX_OPEN_POSITIONS = 5

MIN_ASSET_PRICE = 0.50
MAX_TOKEN_SIZE = 500.0

TOP_MARKETS = 25
MAX_DISCOVERED_TO_RANK = 100

GRANULARITY = 900
LOOKBACK_DAYS = 20
CHUNK = 200
LOOP_INTERVAL = 900

STATE_DIR = Path("backend/state")
LOG_DIR = Path("audit_logs")
TRADE_HISTORY = LOG_DIR / "trade_history.json"

STATE_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

if not TRADE_HISTORY.exists():
    TRADE_HISTORY.write_text("[]")


@dataclass
class Candle:
    ts: int
    low: float
    high: float
    open: float
    close: float
    volume: float


def iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def ema(values: list[float], period: int) -> float:
    k = 2 / (period + 1)
    e = values[0]
    for v in values[1:]:
        e = v * k + e * (1 - k)
    return e


def atr(candles: list[Candle]) -> float:
    trs: list[float] = []
    prev = candles[0].close
    for c in candles[1:]:
        tr = max(
            c.high - c.low,
            abs(c.high - prev),
            abs(c.low - prev),
        )
        trs.append(tr)
        prev = c.close
    return statistics.mean(trs)


def vwap(candles: list[Candle]) -> float:
    pv = 0.0
    vol = 0.0
    for c in candles:
        typical = (c.high + c.low + c.close) / 3
        pv += typical * c.volume
        vol += c.volume
    return pv / vol


def discover_markets() -> list[str]:
    r = requests.get(f"{COINBASE}/products", timeout=15)
    products = r.json()

    markets: list[str] = []
    for p in products:
        if p.get("quote_currency") != "USD":
            continue
        if p.get("status") != "online":
            continue
        pid = p.get("id")
        if pid:
            markets.append(pid)

    return sorted(markets)[:MAX_DISCOVERED_TO_RANK]


def rank_liquidity(markets: list[str]) -> list[str]:
    liquidity: list[tuple[str, float]] = []

    for m in markets:
        try:
            r = requests.get(f"{COINBASE}/products/{m}/stats", timeout=6)
            vol = float(r.json()["volume"])
            liquidity.append((m, vol))
        except Exception:
            continue

    liquidity.sort(key=lambda x: x[1], reverse=True)
    return [x[0] for x in liquidity[:TOP_MARKETS]]


def fetch(product: str, start: datetime, end: datetime) -> list[Candle]:
    url = f"{COINBASE}/products/{product}/candles"

    candles: list[Candle] = []
    step = GRANULARITY * CHUNK
    cursor = start

    while cursor < end:
        chunk_end = min(cursor + timedelta(seconds=step), end)

        r = requests.get(
            url,
            params={
                "start": iso(cursor),
                "end": iso(chunk_end),
                "granularity": GRANULARITY,
            },
            timeout=15,
        )

        rows = r.json()

        for row in rows:
            ts, low, high, open_, close, vol = row
            candles.append(
                Candle(
                    ts=int(ts),
                    low=float(low),
                    high=float(high),
                    open=float(open_),
                    close=float(close),
                    volume=float(vol),
                )
            )

        cursor = chunk_end

    uniq = {c.ts: c for c in candles}
    return sorted(uniq.values(), key=lambda x: x.ts)


def get_price(asset: str) -> float | None:
    try:
        r = requests.get(f"{COINBASE}/products/{asset}/ticker", timeout=6)
        return float(r.json()["price"])
    except Exception:
        return None


def position_files() -> list[Path]:
    return list(STATE_DIR.glob("pos_*.json"))


def open_position_files() -> list[Path]:
    files: list[Path] = []
    for f in position_files():
        try:
            data = json.loads(f.read_text())
        except Exception:
            continue
        if data.get("status") == "OPEN":
            files.append(f)
    return files


def has_open_position(asset: str) -> bool:
    fname = asset.replace("-", "_")
    path = STATE_DIR / f"pos_{fname}.json"

    if not path.exists():
        return False

    try:
        data = json.loads(path.read_text())
    except Exception:
        return False

    return data.get("status") == "OPEN"


def save_position(asset: str, trade: dict) -> None:
    fname = asset.replace("-", "_")
    path = STATE_DIR / f"pos_{fname}.json"

    trade["status"] = "OPEN"
    path.write_text(json.dumps(trade, indent=2))


def record_trade(trade: dict) -> None:
    try:
        hist = json.loads(TRADE_HISTORY.read_text())
    except Exception:
        hist = []

    hist.append(trade)
    TRADE_HISTORY.write_text(json.dumps(hist, indent=2))


def close_position(file_path: Path, price: float) -> None:
    data = json.loads(file_path.read_text())

    pnl = (price - data["entry"]) * data["size"]

    data["exit_price"] = price
    data["exit_time"] = datetime.now(timezone.utc).isoformat()
    data["pnl"] = pnl
    data["status"] = "CLOSED"

    file_path.write_text(json.dumps(data, indent=2))
    record_trade(data)

    print("POSITION CLOSED", data["asset"], "PnL:", round(pnl, 4))


def open_portfolio_risk() -> float:
    total_risk = 0.0

    for f in open_position_files():
        try:
            data = json.loads(f.read_text())
            entry = float(data["entry"])
            stop = float(data["stop"])
            size = float(data["size"])
            trade_risk = max(0.0, (entry - stop) * size)
            total_risk += trade_risk
        except Exception:
            continue

    return total_risk


def open_portfolio_risk_pct() -> float:
    return open_portfolio_risk() / ACCOUNT_EQUITY


def monitor_positions() -> None:
    for f in open_position_files():
        data = json.loads(f.read_text())
        asset = data["asset"]

        price = get_price(asset)
        if price is None:
            continue

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=3)
        candles = fetch(asset, start, end)

        if len(candles) < 20:
            continue

        closes = [c.close for c in candles]
        ema10 = ema(closes[-10:], 10)
        atr_val = atr(candles[-20:])

        trail = ema10 - atr_val
        data["stop"] = max(float(data["stop"]), float(trail))

        if price <= data["stop"]:
            close_position(f, price)
        else:
            f.write_text(json.dumps(data, indent=2))


def score_asset(asset: str, candles: list[Candle]) -> float:
    closes = [c.close for c in candles]

    v = vwap(candles[-30:])
    atr_val = atr(candles[-20:])

    spread = abs(closes[-1] - v) / v
    momentum = abs(closes[-1] - closes[-20]) / closes[-20]
    volatility = atr_val / closes[-1]

    return spread + momentum + volatility


def build_trade(asset: str, candles: list[Candle], weight: float) -> dict | None:
    price = candles[-1].close
    atr_val = atr(candles[-20:])

    stop = price - atr_val * 2
    stop_distance = price - stop

    if stop_distance <= 0:
        return None

    risk_budget = ACCOUNT_EQUITY * RISK_PER_TRADE
    size = risk_budget / stop_distance
    size = min(size, MAX_TOKEN_SIZE)

    trade = {
        "asset": asset,
        "strategy": "MULTI",
        "entry": price,
        "stop": stop,
        "size": size,
        "weight": weight,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return trade


def execute_trade(asset: str, trade: dict) -> None:
    print("TRADE SIGNAL", trade)
    save_position(asset, trade)


def run_cycle() -> None:
    print("\n==============================")
    print("CSS AUTONOMOUS ENGINE v49")
    print(datetime.now(timezone.utc))
    print("==============================\n")

    monitor_positions()

    open_count = len(open_position_files())
    current_risk_pct = open_portfolio_risk_pct()

    print("Open positions:", open_count)
    print("Portfolio risk %:", round(current_risk_pct * 100, 2))

    if open_count >= MAX_OPEN_POSITIONS:
        print("Portfolio position limit reached")
        return

    if current_risk_pct >= MAX_PORTFOLIO_RISK:
        print("Portfolio risk limit reached")
        return

    markets = discover_markets()
    liquid = rank_liquidity(markets)

    scored: list[dict] = []

    for asset in liquid:
        if has_open_position(asset):
            continue

        price = get_price(asset)
        if price is None or price < MIN_ASSET_PRICE:
            continue

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=LOOKBACK_DAYS)
        candles = fetch(asset, start, end)

        if len(candles) < 80:
            continue

        score = score_asset(asset, candles)

        scored.append(
            {
                "asset": asset,
                "candles": candles,
                "score": score,
            }
        )

    scored.sort(key=lambda x: x["score"], reverse=True)

    slots = MAX_OPEN_POSITIONS - open_count
    selected = scored[:slots]

    if not selected:
        print("No new qualified opportunities")
        return

    total_score = sum(x["score"] for x in selected)

    for s in selected:
        weight = s["score"] / total_score if total_score > 0 else 1 / len(selected)
        trade = build_trade(s["asset"], s["candles"], weight)

        if trade is None:
            continue

        projected_risk = open_portfolio_risk() + max(
            0.0, (trade["entry"] - trade["stop"]) * trade["size"]
        )
        projected_risk_pct = projected_risk / ACCOUNT_EQUITY

        if projected_risk_pct > MAX_PORTFOLIO_RISK:
            print(
                "SKIP",
                s["asset"],
                "- projected portfolio risk too high:",
                round(projected_risk_pct * 100, 2),
                "%"
            )
            continue

        execute_trade(s["asset"], trade)


def main() -> None:
    print("\nCSS AUTONOMOUS ENGINE v49 STARTED\n")

    while True:
        run_cycle()
        print("\nSleeping 15 minutes...\n")
        time.sleep(LOOP_INTERVAL)


if __name__ == "__main__":
    main()