from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

from backend.execution.coinbase_executor import CoinbaseExecutor, OrderIntent
from backend.risk.trading_safety import TradingSafety
from backend.strategy.vwap_mean_reversion import VWAPConfig, compute_vwap_from_candles, should_buy_mean_reversion


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


def _normalize_candles(resp: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Attempt to normalize candles into a list of dicts with:
      high, low, close, volume
    Coinbase SDK/REST shapes vary — we handle common patterns.
    """
    # Common: {"candles":[{...},{...}]}
    if isinstance(resp, dict) and isinstance(resp.get("candles"), list):
        return [c for c in resp["candles"] if isinstance(c, dict)]

    # Sometimes: {"candles":[[ts, low, high, open, close, volume], ...]}
    if isinstance(resp, dict) and isinstance(resp.get("candles"), list):
        out = []
        for row in resp["candles"]:
            if isinstance(row, (list, tuple)) and len(row) >= 6:
                out.append(
                    {
                        "low": row[1],
                        "high": row[2],
                        "open": row[3],
                        "close": row[4],
                        "volume": row[5],
                    }
                )
        return out

    # If response itself is a list
    if isinstance(resp, list):
        return [c for c in resp if isinstance(c, dict)]

    return []


def _extract_best_bid_ask(resp: Dict[str, Any], product_id: str) -> Optional[Dict[str, float]]:
    """
    Normalizes best bid/ask response into floats: {"bid":..., "ask":...}
    Handles common Coinbase response layouts.
    """
    pid = product_id.upper()

    # Some shapes: {"pricebooks":[{"product_id":"BTC-USDC","bids":[{"price":"..."}], "asks":[{"price":"..."}]}]}
    if isinstance(resp, dict) and isinstance(resp.get("pricebooks"), list):
        for pb in resp["pricebooks"]:
            if isinstance(pb, dict) and str(pb.get("product_id", "")).upper() == pid:
                bid = None
                ask = None
                bids = pb.get("bids") or []
                asks = pb.get("asks") or []
                if isinstance(bids, list) and bids and isinstance(bids[0], dict):
                    bid = _safe_float(bids[0].get("price"))
                if isinstance(asks, list) and asks and isinstance(asks[0], dict):
                    ask = _safe_float(asks[0].get("price"))
                if bid and ask:
                    return {"bid": float(bid), "ask": float(ask)}

    # Some shapes: {"best_bid_ask":[{"product_id": "...", "bid": "...", "ask": "..."}]}
    if isinstance(resp, dict) and isinstance(resp.get("best_bid_ask"), list):
        for row in resp["best_bid_ask"]:
            if isinstance(row, dict) and str(row.get("product_id", "")).upper() == pid:
                bid = _safe_float(row.get("bid"))
                ask = _safe_float(row.get("ask"))
                if bid and ask:
                    return {"bid": float(bid), "ask": float(ask)}

    return None


def run_loop() -> None:
    executor = CoinbaseExecutor()
    safety = TradingSafety()

    product_id = _env("PRODUCT_ID", "BTC-USDC").upper()
    quote_size = _env("SMOKE_QUOTE_SIZE", "2")

    # Candle config (keep stable + conservative)
    granularity = _env("CANDLE_GRANULARITY", "FIFTEEN_MINUTE")  # Coinbase supports enumerations; SDK may map
    vwap_window = _as_int(_env("VWAP_WINDOW", "40"), 40)

    cfg = VWAPConfig(
        window=vwap_window,
        entry_bps=_as_float(_env("VWAP_ENTRY_BPS", "35"), 35.0),
        exit_bps=_as_float(_env("VWAP_EXIT_BPS", "10"), 10.0),
        min_spread_bps=_as_float(_env("MAX_SPREAD_BPS", "15"), 15.0),
    )

    print("\nStrategy loop started (VWAP Mean Reversion).")
    print("TRADE_MODE:", _env("TRADE_MODE", "DRY_RUN"))
    print("LIVE_TRADING_ARMED:", _env("LIVE_TRADING_ARMED", "NO"))
    print("PRODUCT_ID:", product_id)
    print("SMOKE_QUOTE_SIZE:", quote_size)
    print("CANDLE_GRANULARITY:", granularity)
    print("VWAP_WINDOW:", cfg.window)
    print("VWAP_ENTRY_BPS:", cfg.entry_bps)
    print("MAX_SPREAD_BPS:", cfg.min_spread_bps)
    print("KILL_SWITCH_FILE:", str(safety.cfg.kill_switch_file))
    print("-------------------------------------------------\n")

    while True:
        try:
            # Kill switch
            if safety.kill_switch_active():
                print("KILL SWITCH ACTIVE — LIVE orders blocked.")
                time.sleep(5)
                continue

            # Get best bid/ask (spread filter)
            # We use the SDK client under executor to call a compatible endpoint.
            # If your SDK has a helper, it will work; otherwise we fall back to REST path via executor._call.
            if hasattr(executor._client, "get_best_bid_ask"):
                bba = executor._client.get_best_bid_ask(product_ids=[product_id])  # type: ignore
                bba_dict = executor._to_plain_dict(bba) if hasattr(executor, "_to_plain_dict") else (bba if isinstance(bba, dict) else {})
            else:
                bba_dict = executor._call("GET", f"/api/v3/brokerage/best_bid_ask?product_ids={product_id}", data=None)  # type: ignore

            bba_norm = _extract_best_bid_ask(bba_dict if isinstance(bba_dict, dict) else {}, product_id)
            if not bba_norm:
                print("NO_BBA — skipping tick")
                time.sleep(10)
                continue

            bid = bba_norm["bid"]
            ask = bba_norm["ask"]
            mid = (bid + ask) / 2.0
            spread_bps = ((ask - bid) / mid) * 10000.0 if mid > 0 else 9999.0

            # Get candles and compute VWAP
            if hasattr(executor._client, "get_candles"):
                resp = executor._client.get_candles(product_id=product_id, granularity=granularity)  # type: ignore
                candles_resp = resp if isinstance(resp, dict) else {}
            else:
                candles_resp = executor._call("GET", f"/api/v3/brokerage/products/{product_id}/candles?granularity={granularity}", data=None)  # type: ignore

            candles = _normalize_candles(candles_resp if isinstance(candles_resp, dict) else {})
            vwap = compute_vwap_from_candles(candles, cfg.window)

            if vwap is None:
                print(f"mid={mid:.2f} spread={spread_bps:.2f}bps VWAP=None (insufficient candles)")
                time.sleep(10)
                continue

            do_buy, reason = should_buy_mean_reversion(mid, vwap, spread_bps, cfg)

            print(
                f"mid={mid:.2f} vwap={vwap:.2f} spread={spread_bps:.2f}bps => {reason}"
            )

            if do_buy:
                allowed, block_reason = safety.can_send_order(quote_size=quote_size)
                if not allowed:
                    safety.record_block(block_reason)
                    print("BLOCKED:", block_reason)
                    time.sleep(5)
                    continue

                intent = OrderIntent(
                    product_id=product_id,
                    side="BUY",
                    order_type="MARKET",
                    quote_size=quote_size,
                )

                result = executor.create_order(intent)
                print("Order Result:", result)

                # Record immediately (crash-safe)
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