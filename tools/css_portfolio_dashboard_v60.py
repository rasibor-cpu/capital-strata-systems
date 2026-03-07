import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]

STATE_FILE = PROJECT_ROOT / "backend" / "state" / "spot_position.json"
TRADES_FILE = PROJECT_ROOT / "audit_logs" / "trades.jsonl"

STARTING_CAPITAL = 200.0
REFRESH_SECONDS = 20
CANDLE_GRANULARITY = 900
MAX_PRODUCTS_TO_SCAN = 20
TOP_DISPLAY_COUNT = 5

COINBASE_PRODUCTS_URL = "https://api.exchange.coinbase.com/products"
COINBASE_TICKER_URL = "https://api.exchange.coinbase.com/products/{product_id}/ticker"
COINBASE_CANDLES_URL = (
    "https://api.exchange.coinbase.com/products/{product_id}/candles?granularity={granularity}"
)

_session = requests.Session()
_session.headers.update(
    {
        "Accept": "application/json",
        "User-Agent": "CSS-Dashboard/61",
    }
)

_cached_products: List[str] = []
_cached_products_ts: float = 0.0
PRODUCT_CACHE_SECONDS = 300


def clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def load_position() -> Optional[Dict[str, Any]]:
    if not STATE_FILE.exists():
        return None
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def load_trades() -> List[Dict[str, Any]]:
    trades: List[Dict[str, Any]] = []
    if not TRADES_FILE.exists():
        return trades

    try:
        with open(TRADES_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                    if isinstance(item, dict):
                        trades.append(item)
                except json.JSONDecodeError:
                    continue
    except Exception:
        return []

    return trades


def compute_realized(trades: List[Dict[str, Any]]) -> float:
    pnl = 0.0
    for trade in trades:
        pnl += safe_float(trade.get("realized_pnl", 0.0))
    return pnl


def get_position_asset(position: Optional[Dict[str, Any]]) -> str:
    if not position:
        return "-"
    return str(
        position.get("asset")
        or position.get("symbol")
        or position.get("product_id")
        or position.get("pair")
        or "-"
    )


def get_position_qty(position: Optional[Dict[str, Any]]) -> float:
    if not position:
        return 0.0
    return safe_float(
        position.get("size")
        or position.get("qty")
        or position.get("quantity")
        or position.get("base_size")
        or 0.0
    )


def get_entry_price(position: Optional[Dict[str, Any]]) -> float:
    if not position:
        return 0.0
    return safe_float(
        position.get("entry_price")
        or position.get("entry")
        or position.get("avg_entry_price")
        or position.get("average_entry_price")
        or position.get("avg_price")
        or position.get("price")
        or 0.0
    )


def get_current_price(position: Optional[Dict[str, Any]]) -> float:
    if not position:
        return 0.0
    return safe_float(
        position.get("current_price")
        or position.get("mark_price")
        or position.get("market_price")
        or position.get("last_price")
        or position.get("price")
        or 0.0
    )


def has_open_position(position: Optional[Dict[str, Any]]) -> bool:
    if not position:
        return False

    qty = get_position_qty(position)
    status = str(position.get("status", "")).strip().lower()

    if qty > 0:
        return True

    return status in {"open", "active", "filled", "live"}


def compute_unrealized(position: Optional[Dict[str, Any]]) -> float:
    if not has_open_position(position):
        return 0.0

    entry = get_entry_price(position)
    current = get_current_price(position)
    qty = get_position_qty(position)

    if entry <= 0 or current <= 0 or qty <= 0:
        return 0.0

    return (current - entry) * qty


def compute_market_value(position: Optional[Dict[str, Any]]) -> float:
    if not has_open_position(position):
        return 0.0

    current = get_current_price(position)
    qty = get_position_qty(position)

    if current <= 0 or qty <= 0:
        return 0.0

    return current * qty


def fetch_json(url: str, timeout: int = 5) -> Any:
    try:
        response = _session.get(url, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except Exception:
        return None


def discover_products() -> List[str]:
    global _cached_products_ts, _cached_products

    now = time.time()
    if _cached_products and (now - _cached_products_ts) < PRODUCT_CACHE_SECONDS:
        return _cached_products

    payload = fetch_json(COINBASE_PRODUCTS_URL, timeout=8)
    if not isinstance(payload, list):
        return _cached_products

    products: List[str] = []

    for item in payload:
        if not isinstance(item, dict):
            continue

        product_id = str(item.get("id", "")).strip()
        quote_currency = str(item.get("quote_currency", "")).strip().upper()
        status = str(item.get("status", "")).strip().lower()
        trading_disabled = bool(item.get("trading_disabled", False))
        auction_mode = bool(item.get("auction_mode", False))

        if not product_id.endswith("-USD"):
            continue
        if quote_currency != "USD":
            continue
        if status not in {"online", "active"}:
            continue
        if trading_disabled or auction_mode:
            continue

        base = product_id.split("-")[0]
        if base in {"USDT", "USDC", "DAI", "PYUSD", "EURC"}:
            continue

        products.append(product_id)

    products = sorted(set(products))
    _cached_products = products[:MAX_PRODUCTS_TO_SCAN]
    _cached_products_ts = now
    return _cached_products


def get_price(product_id: str) -> Optional[float]:
    payload = fetch_json(COINBASE_TICKER_URL.format(product_id=product_id), timeout=4)
    if not isinstance(payload, dict):
        return None
    price = safe_float(payload.get("price"), default=0.0)
    return price if price > 0 else None


def get_candles(product_id: str) -> List[List[Any]]:
    payload = fetch_json(
        COINBASE_CANDLES_URL.format(
            product_id=product_id,
            granularity=CANDLE_GRANULARITY,
        ),
        timeout=5,
    )
    if not isinstance(payload, list):
        return []

    valid_rows: List[List[Any]] = []
    for row in payload:
        if isinstance(row, list) and len(row) >= 6:
            valid_rows.append(row)
    return valid_rows


def compute_vwap(candles: List[List[Any]]) -> Optional[float]:
    pv = 0.0
    vol = 0.0

    for candle in candles:
        low = safe_float(candle[1])
        high = safe_float(candle[2])
        close = safe_float(candle[4])
        volume = safe_float(candle[5])

        if volume <= 0:
            continue

        typical_price = (low + high + close) / 3.0
        pv += typical_price * volume
        vol += volume

    if vol <= 0:
        return None

    return pv / vol


def scan_opportunities() -> Tuple[List[Tuple[str, float, float, float]], int]:
    products = discover_products()
    results: List[Tuple[str, float, float, float]] = []

    for product_id in products:
        price = get_price(product_id)
        candles = get_candles(product_id)

        if price is None or not candles:
            continue

        vwap = compute_vwap(candles)
        if vwap is None or vwap <= 0:
            continue

        spread_bps = ((price - vwap) / vwap) * 10000.0
        results.append((product_id, price, vwap, spread_bps))

    results.sort(key=lambda item: abs(item[3]), reverse=True)
    return results, len(products)


def render_dashboard() -> None:
    while True:
        position = load_position()
        trades = load_trades()
        opportunities, scanned_count = scan_opportunities()

        realized = compute_realized(trades)
        unrealized = compute_unrealized(position)
        market_value = compute_market_value(position)

        cash_balance = STARTING_CAPITAL + realized
        total_equity = cash_balance + unrealized

        now_label = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        clear()
        print()
        print("==============================================================")
        print(" CAPITAL STRATA SYSTEMS — MARKET DISCOVERY OPPORTUNITY BOARD ")
        print("==============================================================")
        print(f" Local Time          : {now_label}")
        print(f" Scan Interval       : every {REFRESH_SECONDS} seconds")
        print(f" Candle Granularity  : {CANDLE_GRANULARITY // 60} minutes")
        print(f" Products Scanned    : {scanned_count}")
        print()

        print("---------------------- ACCOUNT SUMMARY -----------------------")
        print(f" Starting Capital    : ${STARTING_CAPITAL:,.2f}")
        print(f" Cash Balance        : ${cash_balance:,.2f}")
        print(f" Realized PnL        : ${realized:,.2f}")
        print(f" Unrealized PnL      : ${unrealized:,.2f}")
        print(f" Total Equity        : ${total_equity:,.2f}")
        print()

        print("---------------------- OPEN POSITION -------------------------")
        if has_open_position(position):
            asset = get_position_asset(position)
            qty = get_position_qty(position)
            entry = get_entry_price(position)
            current = get_current_price(position)

            print(f" Asset               : {asset}")
            print(f" Quantity            : {qty:,.8f}")
            print(f" Entry Price         : ${entry:,.8f}")
            print(f" Current Price       : ${current:,.8f}")
            print(f" Market Value        : ${market_value:,.2f}")
            print(f" Position PnL        : ${unrealized:,.2f}")
        else:
            print(" No open position")
        print()

        print("---------------------- TOP OPPORTUNITIES ---------------------")
        if opportunities:
            for rank, item in enumerate(opportunities[:TOP_DISPLAY_COUNT], start=1):
                asset, price, vwap, spread_bps = item
                signal = "OVERSOLD" if spread_bps < 0 else "OVERBOUGHT"
                print(
                    f" {rank}. {asset:10}  Price ${price:>10,.2f}  "
                    f"VWAP ${vwap:>10,.2f}  Spread {spread_bps:>8.1f} bps  {signal}"
                )
        else:
            print(" No opportunities available")
        print()

        print("---------------------- TRADE LOG -----------------------------")
        print(f" Total Trades        : {len(trades)}")
        print()
        print("==============================================================")

        time.sleep(REFRESH_SECONDS)


if __name__ == "__main__":
    render_dashboard()