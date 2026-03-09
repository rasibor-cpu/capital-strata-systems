from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import List, Dict, Any

from backend.risk.portfolio_risk_governor import PortfolioRiskGovernor
from backend.risk.session_policy_loader import choose_session_policy
from backend.strategies.vwap_mean_reversion import (
    VWAPConfig,
    compute_vwap_from_candles,
    should_buy_mean_reversion,
)

# NEW
from backend.scanner.coinbase_universe import get_top_universe


try:
    from backend.execution.coinbase_executor import CoinbaseExecutor
except Exception:
    CoinbaseExecutor = None


# ---------------- ENV ----------------

def _env(name: str, default: str) -> str:
    v = os.getenv(name)
    return default if v is None else str(v)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return float(raw)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------- AI WATCHLIST ----------------

def build_ai_watchlist() -> List[str]:

    try:

        universe = get_top_universe(200)

        return universe[:5]

    except Exception:

        return ["BTC-USD", "ETH-USD"]


# ---------------- MAIN ----------------

def main():

    scan_interval = int(_env_float("CSS_SCAN_INTERVAL_SECONDS", 45))
    starting_capital = _env_float("CSS_STARTING_CAPITAL_USD", 200)
    trade_size = _env_float("CSS_TRADE_SIZE_USD", 20)

    policy = choose_session_policy(starting_capital)

    governor = PortfolioRiskGovernor(policy)

    executor = None

    if CoinbaseExecutor:
        executor = CoinbaseExecutor(paper_mode=True)

    assets = build_ai_watchlist()

    vwap_cfg = VWAPConfig(
        window=20,
        epsilon_bps=12,
        take_profit_bps=35,
        stop_loss_bps=45,
    )

    print("\n")
    print("===============================================================")
    print("CAPITAL STRATA SYSTEMS LIVE DASHBOARD")
    print("===============================================================")

    print(
        f"Policy: {policy.policy_name} | Capital: ${starting_capital:.2f} | Trade Size: ${trade_size:.2f} | Refresh: {scan_interval}s"
    )

    print("Configured Base Assets:", ", ".join(assets))
    print("Timestamp (UTC):", utc_now())

    print("\n")

    while True:

        try:

            print("LIVE COINBASE EXECUTION WATCHLIST")
            print("---------------------------------------------------------------")

            for asset in assets:

                candles = executor.get_candles(asset, "FIFTEEN_MINUTE")

                if len(candles) < 20:
                    continue

                vwap = compute_vwap_from_candles(candles, 20)

                mid = float(candles[-1]["close"])

                spread = ((mid - vwap) / vwap) * 10000

                signal, reason = should_buy_mean_reversion(
                    mid,
                    vwap,
                    spread,
                    vwap_cfg,
                )

                print(
                    f"{asset:<10} mid {mid:<10.4f} vwap {vwap:<10.4f} spread {spread:>8.2f} signal {signal}"
                )

            print("\nRefreshing in", scan_interval, "seconds... Press Ctrl+C to stop.")
            print("\n")

            time.sleep(scan_interval)

        except KeyboardInterrupt:

            print("\nCSS stopped")

            break

        except Exception as e:

            print("Runner error:", e)

            time.sleep(scan_interval)


if __name__ == "__main__":
    main()