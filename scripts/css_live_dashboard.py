from __future__ import annotations

import sys
from pathlib import Path

# --- FIX IMPORT PATH ---
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

import os
import time
from datetime import datetime, timezone
from typing import List

from backend.risk.portfolio_risk_governor import PortfolioRiskGovernor
from backend.risk.session_policy_loader import choose_session_policy
from backend.strategies.vwap_mean_reversion import (
    VWAPConfig,
    compute_vwap_from_candles,
    should_buy_mean_reversion,
)

# NEW: universe scanner
try:
    from backend.scanner.coinbase_universe import get_top_universe
except Exception:
    get_top_universe = None

# Coinbase executor
try:
    from backend.execution.coinbase_executor import CoinbaseExecutor
except Exception:
    CoinbaseExecutor = None


# ---------------- ENV HELPERS ----------------

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


# ---------------- UNIVERSE ----------------

def build_asset_universe() -> List[str]:

    # Use scanner if available
    if get_top_universe:

        try:
            universe = get_top_universe(200)

            if len(universe) > 0:
                return universe

        except Exception:
            pass

    # fallback
    return ["BTC-USD", "ETH-USD"]


# ---------------- DASHBOARD ----------------

def print_header(policy_name, capital, trade_size, scan_interval, assets):

    print()
    print("==============================================================")
    print("        CAPITAL STRATA SYSTEMS LIVE DASHBOARD")
    print("==============================================================")
    print(
        f"Policy: {policy_name} | Capital: ${capital:.2f} | Trade Size: ${trade_size:.2f} | Refresh: {scan_interval}s"
    )

    print("Configured Base Assets:", ", ".join(assets[:5]), "...")
    print("Timestamp (UTC):", utc_now())
    print()


# ---------------- MAIN ----------------

def main():

    scan_interval = int(_env_float("CSS_SCAN_INTERVAL_SECONDS", 45))
    starting_capital = _env_float("CSS_STARTING_CAPITAL_USD", 200)
    trade_size = _env_float("CSS_TRADE_SIZE_USD", 20)

    # Risk policy
    policy = choose_session_policy(starting_capital)
    governor = PortfolioRiskGovernor(policy)

    # Coinbase adapter
    executor = None

    if CoinbaseExecutor:
        executor = CoinbaseExecutor(paper_mode=True)

    # Build asset universe
    assets = build_asset_universe()

    # Strategy config
    vwap_cfg = VWAPConfig(
        window=20,
        epsilon_bps=12,
        take_profit_bps=35,
        stop_loss_bps=45,
    )

    print_header(policy.policy_name, starting_capital, trade_size, scan_interval, assets)

    while True:

        try:

            print("LIVE COINBASE EXECUTION WATCHLIST")
            print("--------------------------------------------------------------")

            # Only display first 5 assets to keep dashboard readable
            watchlist = assets[:5]

            for asset in watchlist:

                if executor is None:
                    print(asset, "Executor unavailable")
                    continue

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
                    f"{asset:<10} mid {mid:<12.4f} vwap {vwap:<12.4f} spread {spread:>8.2f}  signal {signal}"
                )

            print()
            print("Refreshing in", scan_interval, "seconds... Press Ctrl+C to stop.")
            print()

            time.sleep(scan_interval)

        except KeyboardInterrupt:

            print("\nCSS stopped")
            break

        except Exception as e:

            print("Runner error:", e)
            time.sleep(scan_interval)


if __name__ == "__main__":
    main()