from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.execution.coinbase_executor import CoinbaseExecutor, OrderIntent
from backend.adapters.coinbase_adapter import CoinbaseAdapter
from backend.risk.trading_safety import TradingSafety

# NOTE: we keep using your existing VWAP helper (already working in your repo)
from backend.strategy.vwap_mean_reversion import VWAPConfig, compute_vwap_from_candles

STATE_FILE = "backend/state/spot_position.json"
JOURNAL_FILE = "audit_logs/trades.jsonl"


# -----------------------------
# Small helpers
# -----------------------------
def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _env(name: str, default: str) -> str:
    v = os.getenv(name)
    return default if v is None else str(v).strip()


def _as_int(s: str, default: int) -> int:
    try:
        return int(str(s).strip())
    except Exception:
        return default


def _as_float(s: str, default: float) -> float:
    try:
        return float(str(s).strip())
    except Exception:
        return default


def _safe_float(x: Any) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


def _safe_int(x: Any) -> Optional[int]:
    try:
        if isinstance(x, (int, float)):
            return int(x)
        s = str(x).strip()
        if s.isdigit():
            return int(s)
    except Exception:
        pass
    return None


def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def _journal(event: Dict[str, Any]) -> None:
    """
    Append JSONL record. Never crash engine on journaling.
    """
    try:
        _ensure_parent_dir(JOURNAL_FILE)
        rec = dict(event)
        rec.setdefault("ts_utc", _utc_now_iso())
        with open(JOURNAL_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        return


# -----------------------------
# Position state (spot-safe)
# -----------------------------
def load_position() -> Optional[Dict[str, Any]]:
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                if isinstance(d, dict):
                    return d
    except Exception:
        pass
    return None


def save_position(d: Dict[str, Any]) -> None:
    _ensure_parent_dir(STATE_FILE)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


def clear_position() -> None:
    try:
        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)
    except Exception:
        pass


# -----------------------------
# Coinbase response normalization
# -----------------------------
def _normalize_candles(resp: Any) -> List[Dict[str, Any]]:
    """
    Supports shapes:
      - {"candles":[{...}, ...]}
      - {"candles":[[start, low, high, open, close, volume], ...]}
    Output dict keys: start, low, high, open, close, volume
    """
    out: List[Dict[str, Any]] = []
    if isinstance(resp, dict) and isinstance(resp.get("candles"), list):
        rows = resp["candles"]
        if not rows:
            return out

        if isinstance(rows[0], dict):
            for x in rows:
                if not isinstance(x, dict):
                    continue
                out.append(
                    {
                        "start": x.get("start") or x.get("time") or x.get("timestamp"),
                        "low": x.get("low"),
                        "high": x.get("high"),
                        "open": x.get("open"),
                        "close": x.get("close"),
                        "volume": x.get("volume"),
                    }
                )
            return out

        if isinstance(rows[0], (list, tuple)):
            for r in rows:
                if isinstance(r, (list, tuple)) and len(r) >= 6:
                    out.append(
                        {
                            "start": r[0],
                            "low": r[1],
                            "high": r[2],
                            "open": r[3],
                            "close": r[4],
                            "volume": r[5],
                        }
                    )
            return out

    return out


def _sort_candles_by_start(candles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    usable = [c for c in candles if _safe_int(c.get("start")) is not None]
    usable.sort(key=lambda x: int(_safe_int(x.get("start")) or 0))
    return usable


def _latest_close_and_ts(candles_sorted: List[Dict[str, Any]]) -> Tuple[Optional[float], Optional[str]]:
    if not candles_sorted:
        return None, None
    last = candles_sorted[-1]
    close = _safe_float(last.get("close"))
    start_i = _safe_int(last.get("start"))
    ts = None
    if start_i is not None:
        ts = datetime.fromtimestamp(start_i, tz=timezone.utc).isoformat(timespec="seconds")
    return close, ts


# -----------------------------
# Volatility estimate (bps)
# -----------------------------
def _vol_bps_from_candles(candles_sorted: List[Dict[str, Any]], window: int) -> Optional[float]:
    """
    Simple, robust volatility proxy:
      median absolute close-to-close return (bps) over last N closes.
    """
    closes: List[float] = []
    for c in candles_sorted[-(window + 2) :]:
        v = _safe_float(c.get("close"))
        if v is not None and v > 0:
            closes.append(v)
    if len(closes) < 6:
        return None

    rets_bps: List[float] = []
    for i in range(1, len(closes)):
        prev = closes[i - 1]
        cur = closes[i]
        if prev <= 0:
            continue
        rets_bps.append(abs((cur - prev) / prev) * 10000.0)

    if not rets_bps:
        return None

    rets_bps.sort()
    mid = len(rets_bps) // 2
    med = rets_bps[mid] if len(rets_bps) % 2 == 1 else (rets_bps[mid - 1] + rets_bps[mid]) / 2.0
    return float(med)


# -----------------------------
# Balances
# -----------------------------
def _extract_balance(accounts_resp: Any, currency: str) -> float:
    """
    accounts_resp (from CoinbaseAdapter.get_accounts):
      {"accounts":[{"currency":"USDC","available_balance":{"value":"141.0","currency":"USDC"}}, ...]}
    """
    try:
        if not isinstance(accounts_resp, dict):
            return 0.0
        rows = accounts_resp.get("accounts", [])
        if not isinstance(rows, list):
            return 0.0

        for x in rows:
            if not isinstance(x, dict):
                continue
            if str(x.get("currency", "")).upper() != currency.upper():
                continue
            ab = x.get("available_balance", {})
            if isinstance(ab, dict):
                v = ab.get("value")
                f = _safe_float(v)
                return float(f or 0.0)
    except Exception:
        return 0.0
    return 0.0


# -----------------------------
# Time window helpers for candles
# -----------------------------
def _granularity_minutes(name: str) -> int:
    """
    Matches your existing env values (FIFTEEN_MINUTE etc).
    """
    n = str(name).upper().strip()
    if n == "ONE_MINUTE":
        return 1
    if n == "FIVE_MINUTE":
        return 5
    if n == "FIFTEEN_MINUTE":
        return 15
    if n == "THIRTY_MINUTE":
        return 30
    if n == "ONE_HOUR":
        return 60
    if n == "TWO_HOUR":
        return 120
    if n == "SIX_HOUR":
        return 360
    if n == "ONE_DAY":
        return 1440
    # default to 15m
    return 15


def _iso_from_epoch(epoch_s: int) -> str:
    return datetime.fromtimestamp(epoch_s, tz=timezone.utc).isoformat(timespec="seconds")


# -----------------------------
# Main loop
# -----------------------------
def run_loop() -> None:
    executor = CoinbaseExecutor()   # orders + market data
    acct = CoinbaseAdapter()        # balances
    safety = TradingSafety()

    product_id = _env("PRODUCT_ID", "BTC-USDC").upper()
    granularity = _env("CANDLE_GRANULARITY", "FIFTEEN_MINUTE")

    # VWAP config
    vwap_window = _as_int(_env("VWAP_WINDOW", "40"), 40)
    static_entry_bps = _as_float(_env("VWAP_ENTRY_BPS", "25"), 25.0)
    exit_bps = _as_float(_env("VWAP_EXIT_BPS", "4"), 4.0)
    max_spread_bps = _as_float(_env("MAX_SPREAD_BPS", "25"), 25.0)

    cfg = VWAPConfig(window=vwap_window, entry_bps=static_entry_bps, exit_bps=exit_bps, min_spread_bps=max_spread_bps)

    # Allocation controls (spot-safe)
    target_btc_pct = _as_float(_env("TARGET_BTC_PCT", "0.30"), 0.30)
    alloc_buffer = _as_float(_env("ALLOC_BUFFER_PCT", "0.03"), 0.03)

    # Order sizing
    buy_quote_usd = _as_float(_env("BUY_QUOTE_SIZE_USD", "2"), 2.0)
    min_usdc_reserve = _as_float(_env("MIN_USDC_RESERVE", "10"), 10.0)
    min_btc_sell = _as_float(_env("MIN_BTC_SELL", "0.00002"), 0.00002)

    # TP/SL (bps)
    tp_bps = _as_float(_env("TP_BPS", "40"), 40.0)
    sl_bps = _as_float(_env("SL_BPS", "20"), 20.0)

    # Volatility-adaptive entry threshold
    # adaptive_entry = clamp( VOL_K * vol_bps, MIN_ENTRY_BPS, MAX_ENTRY_BPS )
    vol_k = _as_float(_env("VOL_K", "1.8"), 1.8)
    min_entry_bps = _as_float(_env("MIN_ENTRY_BPS", "8"), 8.0)
    max_entry_bps_adapt = _as_float(_env("MAX_ENTRY_BPS", "80"), 80.0)
    vol_window = _as_int(_env("VOL_WINDOW", "30"), 30)

    print("\nStrategy loop started (VWAP Rotation | Target Allocation | Spot Safe | TP/SL | Vol-Adaptive Entry).")
    print("UTC_NOW:", _utc_now_iso())
    print("TRADE_MODE:", _env("TRADE_MODE", "DRY_RUN"))
    print("LIVE_TRADING_ARMED:", _env("LIVE_TRADING_ARMED", "NO"))
    print("PRODUCT_ID:", product_id)
    print("CANDLE_GRANULARITY:", granularity)
    print("VWAP_WINDOW:", vwap_window)
    print("STATIC_ENTRY_BPS:", static_entry_bps)
    print("EXIT_BPS:", exit_bps)
    print("MAX_SPREAD_BPS:", max_spread_bps)
    print("TP_BPS:", tp_bps, "SL_BPS:", sl_bps)
    print("TARGET_BTC_PCT:", target_btc_pct, "ALLOC_BUFFER_PCT:", alloc_buffer)
    print("BUY_QUOTE_SIZE_USD:", buy_quote_usd, "MIN_USDC_RESERVE:", min_usdc_reserve, "MIN_BTC_SELL:", min_btc_sell)
    print("VOL_K:", vol_k, "VOL_WINDOW:", vol_window, "MIN_ENTRY_BPS:", min_entry_bps, "MAX_ENTRY_BPS:", max_entry_bps_adapt)
    print("KILL_SWITCH_FILE:", str(safety.cfg.kill_switch_file))
    print("JOURNAL_FILE:", JOURNAL_FILE)
    print("STATE_FILE:", STATE_FILE)
    print("-------------------------------------------------\n")

    # Candle range for broker API (start/end required)
    gmin = _granularity_minutes(granularity)
    lookback_candles = max(vwap_window + 60, 150)  # enough history for VWAP + vol + safety
    lookback_seconds = lookback_candles * gmin * 60

    while True:
        try:
            if safety.kill_switch_active():
                print("KILL SWITCH ACTIVE — orders blocked.")
                _journal({"event": "KILL_SWITCH_ACTIVE"})
                time.sleep(5)
                continue

            bba = executor.get_best_bid_ask(product_id=product_id, limit=1)
            if not bba:
                print("NO_BBA — skipping tick")
                _journal({"event": "NO_BBA"})
                time.sleep(10)
                continue

            bid = bba["bid"]
            ask = bba["ask"]
            mid = (bid + ask) / 2.0
            spread_bps = ((ask - bid) / mid) * 10000.0 if mid > 0 else 9999.0

            if spread_bps > max_spread_bps:
                msg = f"SPREAD_TOO_WIDE mid={mid:.2f} spread={spread_bps:.2f}bps > {max_spread_bps:.2f}bps"
                print(msg)
                _journal({"event": "SPREAD_BLOCK", "mid": mid, "spread_bps": spread_bps, "max_spread_bps": max_spread_bps})
                time.sleep(10)
                continue

            end_epoch = int(time.time())
            start_epoch = end_epoch - lookback_seconds
            start_iso = _iso_from_epoch(start_epoch)
            end_iso = _iso_from_epoch(end_epoch)

            candles_resp = executor.get_candles(product_id=product_id, granularity=granularity, start=start_iso, end=end_iso)
            candles = _sort_candles_by_start(_normalize_candles(candles_resp))
            last_close, last_ts = _latest_close_and_ts(candles)

            vwap = compute_vwap_from_candles(candles, vwap_window)
            if vwap is None or vwap <= 0:
                print(f"VWAP_NONE mid={mid:.2f} last_close={last_close} last_ts={last_ts}")
                _journal({"event": "VWAP_NONE", "mid": mid, "last_close": last_close, "last_ts": last_ts})
                time.sleep(10)
                continue

            dev_bps = ((mid - vwap) / vwap) * 10000.0

            # Vol-adaptive entry threshold
            vol_bps = _vol_bps_from_candles(candles, vol_window)
            adaptive_entry = None
            if vol_bps is not None:
                adaptive_entry = max(min_entry_bps, min(max_entry_bps_adapt, vol_k * vol_bps))
            entry_bps_used = max(static_entry_bps, adaptive_entry) if adaptive_entry is not None else static_entry_bps

            # Balances
            accounts = acct.get_accounts(limit=250)
            usdc = _extract_balance(accounts, "USDC")
            btc = _extract_balance(accounts, "BTC")
            btc_value = btc * mid
            total = usdc + btc_value
            btc_pct = (btc_value / total) if total > 0 else 0.0

            # Position management (TP/SL has priority)
            pos = load_position()
            if pos and isinstance(pos, dict):
                entry_price = _safe_float(pos.get("entry_price"))
                btc_size = _safe_float(pos.get("btc_size"))

                if entry_price and btc_size and entry_price > 0:
                    pnl_bps = ((mid - entry_price) / entry_price) * 10000.0

                    # TP
                    if pnl_bps >= tp_bps:
                        print(f"TP_HIT pnl={pnl_bps:.2f}bps entry={entry_price:.2f} mid={mid:.2f} size={btc_size:.8f}")
                        _journal({"event": "TP_HIT", "pnl_bps": pnl_bps, "entry": entry_price, "mid": mid, "btc_size": btc_size})

                        result = executor.create_order(
                            OrderIntent(product_id=product_id, side="SELL", order_type="MARKET", base_size=str(btc_size))
                        )
                        _journal({"event": "ORDER_SELL_TP", "result": result})

                        clear_position()
                        time.sleep(10)
                        continue

                    # SL
                    if pnl_bps <= -sl_bps:
                        print(f"SL_HIT pnl={pnl_bps:.2f}bps entry={entry_price:.2f} mid={mid:.2f} size={btc_size:.8f}")
                        _journal({"event": "SL_HIT", "pnl_bps": pnl_bps, "entry": entry_price, "mid": mid, "btc_size": btc_size})

                        result = executor.create_order(
                            OrderIntent(product_id=product_id, side="SELL", order_type="MARKET", base_size=str(btc_size))
                        )
                        _journal({"event": "ORDER_SELL_SL", "result": result})

                        clear_position()
                        time.sleep(10)
                        continue

                    # VWAP exit (mean reversion)
                    if dev_bps >= -exit_bps:
                        print(f"VWAP_EXIT dev={dev_bps:.2f}bps >= -{exit_bps:.2f}bps entry={entry_price:.2f} mid={mid:.2f}")
                        _journal({"event": "VWAP_EXIT", "dev_bps": dev_bps, "exit_bps": exit_bps, "entry": entry_price, "mid": mid})

                        result = executor.create_order(
                            OrderIntent(product_id=product_id, side="SELL", order_type="MARKET", base_size=str(btc_size))
                        )
                        _journal({"event": "ORDER_SELL_VWAP_EXIT", "result": result})

                        clear_position()
                        time.sleep(10)
                        continue

            # Allocation signal
            under_target = btc_pct < (target_btc_pct - alloc_buffer)
            over_target = btc_pct > (target_btc_pct + alloc_buffer)

            cheap = dev_bps <= (-entry_bps_used)
            rich = dev_bps >= (+entry_bps_used)

            action = "HOLD"
            reason = f"btc%={btc_pct:.2%} dev={dev_bps:.2f} entry_used={entry_bps_used:.2f} spread={spread_bps:.2f}"

            if under_target and cheap:
                action = "BUY"
                reason = f"UNDER_TARGET & CHEAP | {reason}"
            elif over_target and rich:
                action = "SELL"
                reason = f"OVER_TARGET & RICH | {reason}"

            print(
                f"mid={mid:.2f} vwap={vwap:.2f} dev={dev_bps:.2f}bps spread={spread_bps:.2f}bps "
                f"last_close={last_close} last_ts={last_ts} | vol={None if vol_bps is None else round(vol_bps,2)}bps "
                f"entry_used={entry_bps_used:.2f}bps | USDC={usdc:.2f} BTC={btc:.8f} BTC%={btc_pct:.2%} => {action}"
            )

            _journal(
                {
                    "event": "TICK",
                    "product": product_id,
                    "mid": mid,
                    "vwap": vwap,
                    "dev_bps": dev_bps,
                    "spread_bps": spread_bps,
                    "vol_bps": vol_bps,
                    "entry_bps_used": entry_bps_used,
                    "last_close": last_close,
                    "last_ts": last_ts,
                    "usdc": usdc,
                    "btc": btc,
                    "btc_pct": btc_pct,
                    "action": action,
                    "reason": reason,
                }
            )

            # Execute BUY
            if action == "BUY":
                if usdc <= (min_usdc_reserve + buy_quote_usd):
                    msg = f"BLOCKED_USDC_LOW usdc={usdc:.2f} reserve={min_usdc_reserve:.2f} buy={buy_quote_usd:.2f}"
                    print(msg)
                    _journal({"event": "BLOCKED_USDC_LOW", "usdc": usdc, "reserve": min_usdc_reserve, "buy_quote": buy_quote_usd})
                    time.sleep(10)
                    continue

                allowed, block_reason = safety.can_send_order(quote_size=str(buy_quote_usd))
                if not allowed:
                    safety.record_block(block_reason)
                    print("BLOCKED:", block_reason)
                    _journal({"event": "SAFETY_BLOCK_BUY", "reason": block_reason})
                    time.sleep(10)
                    continue

                result = executor.create_order(
                    OrderIntent(product_id=product_id, side="BUY", order_type="MARKET", quote_size=str(buy_quote_usd))
                )
                _journal({"event": "ORDER_BUY", "quote_usd": buy_quote_usd, "result": result})

                # Spot-safe position block: approximate BTC size from mid (works for paper; live fills can differ slightly)
                approx_btc = (buy_quote_usd / mid) if mid > 0 else 0.0
                save_position({"entry_price": mid, "btc_size": approx_btc, "entry_ts_utc": _utc_now_iso(), "product": product_id})
                _journal({"event": "POSITION_OPENED", "entry": mid, "btc_size": approx_btc, "product": product_id})

                time.sleep(10)
                continue

            # Execute SELL (allocation rebalance only; TP/SL handled above)
            if action == "SELL":
                if btc < min_btc_sell:
                    msg = f"BLOCKED_BTC_DUST btc={btc:.8f} min={min_btc_sell:.8f}"
                    print(msg)
                    _journal({"event": "BLOCKED_BTC_DUST", "btc": btc, "min_btc_sell": min_btc_sell})
                    time.sleep(10)
                    continue

                # Sell a controlled fraction to drift toward target (cap 25% of BTC)
                desired_btc_value = target_btc_pct * total
                excess_value = max(0.0, btc_value - desired_btc_value)
                sell_value = min(excess_value, btc_value * 0.25)
                sell_btc = (sell_value / mid) if mid > 0 else 0.0
                sell_btc = max(min_btc_sell, sell_btc)

                allowed, block_reason = safety.can_send_order(quote_size="0")
                if not allowed:
                    safety.record_block(block_reason)
                    print("BLOCKED:", block_reason)
                    _journal({"event": "SAFETY_BLOCK_SELL", "reason": block_reason})
                    time.sleep(10)
                    continue

                result = executor.create_order(
                    OrderIntent(product_id=product_id, side="SELL", order_type="MARKET", base_size=str(sell_btc))
                )
                _journal({"event": "ORDER_SELL_ALLOC", "base_size": sell_btc, "result": result})

                time.sleep(10)
                continue

        except Exception as e:
            print("ENGINE EXCEPTION:", str(e))
            _journal({"event": "ENGINE_EXCEPTION", "error": str(e)})

        time.sleep(10)


def main() -> int:
    run_loop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())