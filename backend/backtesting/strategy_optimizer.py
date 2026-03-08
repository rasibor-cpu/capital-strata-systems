from __future__ import annotations

import itertools
from dataclasses import dataclass
from pathlib import Path
from typing import List

from backend.backtesting.historical_backtest_engine import HistoricalBacktestEngine


@dataclass
class OptimizationResult:
    tp_pct: float
    stop_pct: float
    pnl: float
    win_rate: float
    trades: int
    ending_capital: float


class StrategyOptimizer:
    def __init__(self) -> None:
        self.tp_grid = [0.01, 0.015, 0.02, 0.025, 0.03]
        self.stop_grid = [0.01, 0.015, 0.02, 0.025, 0.03]

    def generate_param_sets(self):
        return list(itertools.product(self.tp_grid, self.stop_grid))

    def run(self, dataset: str | Path) -> List[OptimizationResult]:
        dataset_path = Path(dataset)
        if not dataset_path.exists():
            raise FileNotFoundError(f"Dataset not found: {dataset_path}")

        results: List[OptimizationResult] = []
        param_sets = self.generate_param_sets()

        print(f"\nRunning optimizer on dataset: {dataset_path}")
        print(f"Total configurations: {len(param_sets)}\n")

        for tp_pct, stop_pct in param_sets:
            engine = HistoricalBacktestEngine(starting_capital=200.0)

            candles = engine.load_csv(dataset_path)
            asset = dataset_path.name.split("_")[0]

            starting_capital = engine.starting_capital
            engine.run(asset, candles)

            wins = sum(1 for t in engine.trades if t.pnl > 0)
            win_rate = round((wins / len(engine.trades)) * 100.0, 2) if engine.trades else 0.0
            total_pnl = round(engine.capital - starting_capital, 2)

            results.append(
                OptimizationResult(
                    tp_pct=tp_pct,
                    stop_pct=stop_pct,
                    pnl=total_pnl,
                    win_rate=win_rate,
                    trades=len(engine.trades),
                    ending_capital=round(engine.capital, 2),
                )
            )

        results.sort(
            key=lambda r: (r.pnl, r.win_rate, -r.stop_pct),
            reverse=True,
        )
        return results