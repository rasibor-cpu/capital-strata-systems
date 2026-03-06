"""
Capital Strata Systems
Autonomous Trading Engine v40b

Faster liquidity-ranked autonomous engine

Improvements over v40
- progress visibility during liquidity ranking
- caps number of discovered markets ranked
- shorter request timeouts
- safer request handling
- still supports exit manager + portfolio governor
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

ACCOUNT_EQUITY = 1000
RISK_PER_TRADE = 0.01
MAX_OPEN_POSITIONS = 3

TOP_MARKETS = 15
MAX_DISCOVERED_TO_RANK = 80

GRANULARITY = 900
LOOKBACK_DAYS = 20
CHUNK = 200
LOOP_INTERVAL = 900

STATE_DIR = Path("backend/state")
LOG_DIR = Path("audit_logs/paper_trades")

STATE_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)


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


# -------------------------------------------------
# MARKET DISCOVERY
# -------------------------------------------------

def discover_markets() -> list[str]:
    print("Discovering Coinbase markets...")

    try:
        r = requests.get(f"{COINBASE}/products", timeout=15)
    except requests.RequestException as e:
        print("Market discovery request failed:", e)
        return []

    if r.status_code != 200:
        print("Market discovery failed with status:", r.status_code)
        return []

    markets: list[str] = []

    for p in r.json():
        try:
            if p.get("quote_currency") != "USD":
                continue
            if p.get("status") != "online":
                continue
            pid = p.get("id")
            if not pid:
                continue
            markets.append(pid)
        except Exception:
            continue

    markets = sorted(markets)

    print("Total USD markets discovered:", len(markets))

    capped = markets[:MAX_DISCOVERED_TO_RANK]
    print("Markets selected for liquidity ranking:", len(capped))

    return capped


# -------------------------------------------------
# LIQUIDITY RANKING
# -------------------------------------------------

def rank_liquidity(markets: list[str]) -> list[str]:
    liquidity: list[tuple[str, float]] = []

    print("Ranking liquidity...")

    total = len(markets)

    for i, m in enumerate(markets, start=1):
        try:
            r = requests.get(
                f"{COINBASE}/products/{m}/stats",
                timeout=6,
            )

            if r.status_code != 200:
                continue

            payload = r.json()
            vol_raw = payload.get("volume")

            if vol_raw is None:
                continue

            vol = float(vol_raw)
            liquidity.append((m, vol))

        except Exception:
            continue

        if i % 10 == 0 or i == total:
            print(f"Liquidity progress: {i}/{total}")

        time.sleep(0.03)

    liquidity = sorted(liquidity, key=lambda x: x[1], reverse=True)

    top = [x[0] for x in liquidity[:TOP_MARKETS]]

    print("Top liquid markets retained:", len(top))
    if top:
        print("Most liquid sample:", ", ".join(top[:5]))

    return top


# -------------------------------------------------
# DATA FETCH
# -------------------------------------------------

def fetch(product: str, start: datetime, end: datetime) -> list[Candle]:
    url = f"{COINBASE}/products/{product}/candles"

    candles: list[Candle] = []

    step = GRANULARITY * CHUNK
    cursor = start

    while cursor < end:
        chunk_end = min(cursor + timedelta(seconds=step), end)

        try:
            r = requests.get(
                url,
                params={
                    "start": iso(cursor),
                    "end": iso(chunk_end),
                    "granularity": GRANULARITY,
                },
                timeout=15,
            )
        except requests.RequestException:
            return []

        if r.status_code != 200:
            return []

        try:
            rows = r.json()
        except Exception:
            return []

        for row in rows:
            if not isinstance(row, list) or len(row) < 6:
                continue

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
        time.sleep(0.04)

    uniq = {c.ts: c for c in candles}
    return sorted(uniq.values(), key=lambda x: x.ts)


def get_price(asset: str) -> float | None:
    try:
        r = requests.get(
            f"{COINBASE}/products/{asset}/ticker",
            timeout=6,
        )
    except requests.RequestException:
        return None

    if r.status_code != 200:
        return None

    try:
        return float(r.json()["price"])
    except Exception:
        return None


# -------------------------------------------------
# INDICATORS
# -------------------------------------------------

def atr(candles: list[Candle]) -> float | None:
    if len(candles) < 2:
        return None

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

    if not trs:
        return None

    return statistics.mean(trs)


def vwap(candles: list[Candle]) -> float | None:
    pv = 0.0
    vol = 0.0

    for c in candles:
        typical = (c.high + c.low + c.close) / 3
        pv += typical * c.volume
        vol += c.volume

    if vol == 0:
        return None

    return pv / vol


# -------------------------------------------------
# POSITION MANAGEMENT
# -------------------------------------------------

def position_files() -> list[Path]:
    return list(STATE_DIR.glob("pos_*.json"))


def position_path(asset: str) -> Path:
    fname = asset.replace("-", "_")
    return STATE_DIR / f"pos_{fname}.json"


def has_open_position(asset: str) -> bool:
    path = position_path(asset)

    if not path.exists():
        return False

    try:
        data = json.loads(path.read_text())
    except Exception:
        return False

    return data.get("status") == "OPEN"


def open_position_count() -> int:
    count = 0

    for f in position_files():
        try:
            data = json.loads(f.read_text())
        except Exception:
            continue

        if data.get("status") == "OPEN":
            count += 1

    return count


def save_position(asset: str, trade: dict) -> None:
    path = position_path(asset)
    trade["status"] = "OPEN"
    path.write_text(json.dumps(trade, indent=2))


def close_position(file_path: Path, price: float) -> None:
    data = json.loads(file_path.read_text())

    entry = float(data["entry"])
    size = float(data["size"])
    pnl = (price - entry) * size

    data["exit_price"] = price
    data["exit_time"] = datetime.now(timezone.utc).isoformat()
    data["pnl"] = pnl
    data["status"] = "CLOSED"

    file_path.write_text(json.dumps(data, indent=2))

    log = LOG_DIR / f"closed_{file_path.name}"
    log.write_text(json.dumps(data, indent=2))

    print("POSITION CLOSED", data["asset"], "PnL:", round(pnl, 4))


def monitor_positions() -> None:
    for f in position_files():
        try:
            data = json.loads(f.read_text())
        except Exception:
            continue

        if data.get("status") != "OPEN":
            continue

        asset = data.get("asset")
        stop = data.get("stop")

        if not asset or stop is None:
            continue

        price = get_price(asset)
        if price is None:
            continue

        if price <= float(stop):
            print(asset, "STOP LOSS HIT")
            close_position(f, price)


# -------------------------------------------------
# OPPORTUNITY SCORING
# -------------------------------------------------

def score_asset(asset: str) -> dict | None:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=LOOKBACK_DAYS)

    candles = fetch(asset, start, end)

    if len(candles) < 80:
        return None

    price = candles[-1].close
    v = vwap(candles[-30:])

    if v is None:
        return None

    spread = abs((price - v) / v)

    recent_volume = sum(c.volume for c in candles[-20:])
    if recent_volume < 100:
        return None

    return {
        "asset": asset,
        "candles": candles,
        "score": spread,
    }


# -------------------------------------------------
# TRADE EXECUTION
# -------------------------------------------------

def execute_trade(asset: str, candles: list[Candle]) -> None:
    price = candles[-1].close

    atr_val = atr(candles[-20:])
    if atr_val is None or atr_val <= 0:
        print(asset, "ATR unavailable, skipping")
        return

    stop = price - atr_val * 2
    risk = price - stop

    if risk <= 0:
        print(asset, "invalid risk, skipping")
        return

    size = (ACCOUNT_EQUITY * RISK_PER_TRADE) / risk

    trade = {
        "asset": asset,
        "strategy": "VWAP_REVERSION",
        "entry": price,
        "stop": stop,
        "size": size,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    print("TRADE SIGNAL", trade)

    save_position(asset, trade)

    out = LOG_DIR / f"trade_{asset}_{int(time.time())}.json"
    out.write_text(json.dumps(trade, indent=2))


# -------------------------------------------------
# ENGINE LOOP
# -------------------------------------------------

def run_cycle() -> None:
    print("\n==============================")
    print("CSS AUTONOMOUS ENGINE v40b")
    print(datetime.now(timezone.utc))
    print("==============================\n")

    monitor_positions()

    open_positions = open_position_count()
    print("Open positions:", open_positions)

    if open_positions >= MAX_OPEN_POSITIONS:
        print("Portfolio limit reached")
        return

    markets = discover_markets()
    if not markets:
        print("No markets discovered")
        return

    liquid = rank_liquidity(markets)
    if not liquid:
        print("No liquid markets ranked")
        return

    print("Scoring opportunities...")

    scored: list[dict] = []

    for i, asset in enumerate(liquid, start=1):
        if has_open_position(asset):
            continue

        s = score_asset(asset)
        if s:
            scored.append(s)

        print(f"Scoring progress: {i}/{len(liquid)}")

    scored = sorted(scored, key=lambda x: x["score"], reverse=True)

    slots = MAX_OPEN_POSITIONS - open_positions
    selected = scored[:slots]

    print("Tradable opportunities found:", len(scored))
    print("Slots available:", slots)

    for s in selected:
        execute_trade(s["asset"], s["candles"])


def main() -> None:
    print("\nCSS AUTONOMOUS ENGINE v40b STARTED\n")

    while True:
        run_cycle()
        print("\nSleeping 15 minutes...\n")
        time.sleep(LOOP_INTERVAL)


if __name__ == "__main__":
    main()