from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.execution.coinbase_executor import CoinbaseExecutor, OrderIntent
from backend.risk.trading_safety import TradingSafety
from backend.strategy.vwap_mean_reversion import (
    VWAPConfig,
    compute_vwap_from_candles,
    should_buy_mean_reversion,
)


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


def _normalize_candles(resp: Any) -> List[Dict[str, Any]]:
    """
    Normalize Coinbase candles response into list[dict] with:
      { start, low, high, open, close, volume }

    We accept either dict rows or list rows. If timestamps are present we keep them.
    """
    out: List[Dict[str, Any]] = []

    if isinstance(resp, dict) and isinstance(resp.get("candles"), list):
        c = resp["candles"]
        if not c:
            return []

        # dict rows
        if isinstance(c[0], dict):
            for x in c:
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

        # list/tuple rows
        if isinstance(c[0], (list, tuple)):
            for row in c:
                if not isinstance(row, (list, tuple)):
                    continue

                # We don't assume exact ordering beyond having OHLCV somewhere;
                # but many Coinbase variants look like:
                # [start, low, high, open, close, volume]
                if len(row) >= 6:
                    out.append(
                        {
                            "start": row[0],
                            "low": row[1],
                            "high": row[2],
                            "open": row[3],
                            "close": row[4],
                            "volume": row[5],
                        }
                    )
            return out

    return out


def _latest_candle_info(candles: List[Dict[str, Any]]) -> Tuple[Optional[float], Optional[str]]:
    if not candles:
        return None, None

    # assume last item is most recent; if not, still good enough for diagnostics
    last = candles[-1]
    close = _safe_float(last.get("close"))
    start = last.get("start")

    ts = None
    if start is not None:
        try:
            # if epoch seconds
            if isinstance(start, (int, float)) or (isinstance(start, str) and start.isdigit()):
                ts = datetime.fromtimestamp(int(start), tz=timezone.utc).isoformat(timespec="seconds")
            else:
                ts = str(start)
        except Exception:
            ts = str(start)

    return close, ts


def run_loop() -> None:
    executor = CoinbaseExecutor()
    safety = TradingSafety()

    product_id = _env("PRODUCT_ID", "BTC-USDC").upper()
    quote_size = _env("SMOKE_QUOTE_SIZE", "2")

    granularity = _env("CANDLE_GRANULARITY", "FIFTEEN_MINUTE")
    vwap_window = _as_int(_env("VWAP_WINDOW", "40"), 40)

    cfg = VWAPConfig(
        window=vwap_window,
        entry_bps=_as_float(_env("VWAP_ENTRY_BPS", "8"), 8.0),
        exit_bps=_as_float(_env("VWAP_EXIT_BPS", "6"), 6.0),
        min_spread_bps=_as_float(_env("MAX_SPREAD_BPS", "25"), 25.0),
    )

    # simple single-position guard (paper-friendly)
    position_open = False
    entry_price = None
    take_profit = None
    stop_loss = None

    tp_bps = _as_float(_env("TP_BPS", "40"), 40.0)   # 0.40%
    sl_bps = _as_float(_env("SL_BPS", "20"), 20.0)   # 0.20%

    print("\nStrategy loop started (VWAP Mean Reversion).")
    print("UTC_NOW:", datetime.now(timezone.utc).isoformat(timespec="seconds"))
    print("TRADE_MODE:", _env("TRADE_MODE", "DRY_RUN"))
    print("LIVE_TRADING_ARMED:", _env("LIVE_TRADING_ARMED", "NO"))
    print("PRODUCT_ID:", product_id)
    print("SMOKE_QUOTE_SIZE:", quote_size)
    print("CANDLE_GRANULARITY:", granularity)
    print("VWAP_WINDOW:", cfg.window)
    print("VWAP_ENTRY_BPS:", cfg.entry_bps)
    print("VWAP_EXIT_BPS:", cfg.exit_bps)
    print("MAX_SPREAD_BPS:", cfg.min_spread_bps)
    print("TP_BPS:", tp_bps, "SL_BPS:", sl_bps)
    print("KILL_SWITCH_FILE:", str(safety.cfg.kill_switch_file))
    print("-------------------------------------------------\n")

    while True:
        try:
            if safety.kill_switch_active():
                print("KILL SWITCH ACTIVE — orders blocked.")
                time.sleep(5)
                continue

            bba = executor.get_best_bid_ask(product_id=product_id, limit=1)
            if not bba:
                print("NO_BBA — skipping tick")
                time.sleep(10)
                continue

            bid = bba["bid"]
            ask = bba["ask"]
            mid = (bid + ask) / 2.0
            spread_bps = ((ask - bid) / mid) * 10000.0 if mid > 0 else 9999.0

            # --- manage open position (paper)
            if position_open and entry_price and take_profit and stop_loss:
                if mid >= take_profit:
                    print(f">>> TAKE PROFIT hit at {mid:.2f} (entry={entry_price:.2f})")
                    executor.create_order(
                        OrderIntent(product_id=product_id, side="SELL", order_type="MARKET", base_size="0.00003")
                    )
                    position_open = False
                    entry_price = take_profit = stop_loss = None
                    time.sleep(2)
                    continue

                if mid <= stop_loss:
                    print(f">>> STOP LOSS hit at {mid:.2f} (entry={entry_price:.2f})")
                    executor.create_order(
                        OrderIntent(product_id=product_id, side="SELL", order_type="MARKET", base_size="0.00003")
                    )
                    position_open = False
                    entry_price = take_profit = stop_loss = None
                    time.sleep(2)
                    continue

            # --- candles + vwap
            candles_resp = executor.get_candles(product_id=product_id, granularity=granularity)
            candles = _normalize_candles(candles_resp)

            last_close, last_ts = _latest_candle_info(candles)
            vwap = compute_vwap_from_candles(candles, cfg.window)

            if vwap is None:
                print(f"mid={mid:.2f} spread={spread_bps:.2f}bps VWAP=None last_close={last_close} last_ts={last_ts}")
                time.sleep(10)
                continue

            dev_bps = ((mid - vwap) / vwap) * 10000.0 if vwap > 0 else 0.0

            do_buy, reason = should_buy_mean_reversion(mid, vwap, spread_bps, cfg)

            print(
                f"mid={mid:.2f} vwap={vwap:.2f} dev={dev_bps:.2f}bps "
                f"spread={spread_bps:.2f}bps last_close={last_close} last_ts={last_ts} => {reason}"
            )

            if do_buy and not position_open:
                allowed, block_reason = safety.can_send_order(quote_size=quote_size)
                if not allowed:
                    safety.record_block(block_reason)
                    print("BLOCKED:", block_reason)
                    time.sleep(5)
                    continue

                result = executor.create_order(
                    OrderIntent(product_id=product_id, side="BUY", order_type="MARKET", quote_size=quote_size)
                )
                print("Order Result:", result)

                entry_price = mid
                take_profit = mid * (1 + tp_bps / 10000.0)
                stop_loss = mid * (1 - sl_bps / 10000.0)
                position_open = True

                print(f">>> POSITION OPENED entry={entry_price:.2f} TP={take_profit:.2f} SL={stop_loss:.2f}")

                if isinstance(result, dict) and not result.get("dry_run", True):
                    safety.record_order_sent()

        except Exception as e:
            print("ENGINE EXCEPTION:", str(e))

        time.sleep(10)


def main() -> int:
    run_loop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())