from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.backtesting.strategy_optimizer import StrategyOptimizer


DATASET = PROJECT_ROOT / "data_cache" / "BTC_USD_FIFTEEN_MINUTE_7d.csv"


def main() -> None:
    optimizer = StrategyOptimizer()
    results = optimizer.run(DATASET)

    print("\n====== CSS Strategy Optimization Results ======\n")
    print(
        f"{'Rank':<6}"
        f"{'TP %':<10}"
        f"{'STOP %':<10}"
        f"{'PnL($)':<12}"
        f"{'End Cap($)':<14}"
        f"{'Trades':<10}"
        f"{'Win Rate':<10}"
    )

    for idx, r in enumerate(results[:10], start=1):
        print(
            f"{idx:<6}"
            f"{r.tp_pct * 100:<10.2f}"
            f"{r.stop_pct * 100:<10.2f}"
            f"{r.pnl:<12.2f}"
            f"{r.ending_capital:<14.2f}"
            f"{r.trades:<10}"
            f"{r.win_rate:<10.2f}"
        )

    best = results[0]
    print("\nBest Configuration\n")
    print(
        f"TP={best.tp_pct * 100:.2f}% | "
        f"STOP={best.stop_pct * 100:.2f}% | "
        f"PnL=${best.pnl:.2f} | "
        f"Ending Capital=${best.ending_capital:.2f} | "
        f"Win Rate={best.win_rate:.2f}% | "
        f"Trades={best.trades}"
    )


if __name__ == "__main__":
    main()