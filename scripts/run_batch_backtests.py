from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.backtesting.historical_backtest_engine import HistoricalBacktestEngine


DATA_CACHE = PROJECT_ROOT / "data_cache"


def run_one(csv_path: Path) -> dict:
    asset = csv_path.name.split("_")[0]

    engine = HistoricalBacktestEngine()
    candles = engine.load_csv(csv_path)
    engine.run(asset, candles)

    wins = sum(1 for t in engine.trades if t.pnl > 0)
    losses = sum(1 for t in engine.trades if t.pnl <= 0)
    win_rate = round((wins / len(engine.trades)) * 100.0, 2) if engine.trades else 0.0
    total_pnl = round(engine.capital - engine.starting_capital, 2)

    return {
        "asset": asset,
        "file": csv_path.name,
        "ending_capital": round(engine.capital, 2),
        "total_pnl": total_pnl,
        "trades": len(engine.trades),
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
    }


def main() -> None:
    if not DATA_CACHE.exists():
        print(f"data_cache folder not found: {DATA_CACHE}")
        return

    csv_files = sorted(DATA_CACHE.glob("*_FIFTEEN_MINUTE_*d.csv"))

    if not csv_files:
        print("No matching CSV files found in data_cache.")
        print("Expected names like BTC_USD_FIFTEEN_MINUTE_7d.csv")
        return

    print("\n====== CSS Batch Backtest Runner ======\n")
    print(f"Found {len(csv_files)} dataset(s).\n")

    results = []

    for csv_file in csv_files:
        print(f"Running backtest for: {csv_file.name}")
        result = run_one(csv_file)
        results.append(result)
        print("-" * 60)

    results.sort(key=lambda x: (x["total_pnl"], x["win_rate"]), reverse=True)

    print("\n====== CSS Batch Backtest Ranking ======\n")
    print(
        f"{'Rank':<6}"
        f"{'Asset':<10}"
        f"{'PnL($)':<12}"
        f"{'End Cap($)':<14}"
        f"{'Trades':<10}"
        f"{'Wins':<8}"
        f"{'Losses':<10}"
        f"{'Win Rate':<10}"
    )

    for idx, r in enumerate(results, start=1):
        print(
            f"{idx:<6}"
            f"{r['asset']:<10}"
            f"{r['total_pnl']:<12.2f}"
            f"{r['ending_capital']:<14.2f}"
            f"{r['trades']:<10}"
            f"{r['wins']:<8}"
            f"{r['losses']:<10}"
            f"{r['win_rate']:<10.2f}"
        )

    print("\nTop performer:")
    best = results[0]
    print(
        f"{best['asset']} | PnL=${best['total_pnl']:.2f} | "
        f"Ending Capital=${best['ending_capital']:.2f} | "
        f"Win Rate={best['win_rate']:.2f}%"
    )


if __name__ == "__main__":
    main()