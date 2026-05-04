"""
backtest_engine.py
Walk-forward backtesting and parameter optimisation.
Run with:  python backtest_engine.py

Backtests the signal engine on historical OHLCV data,
then uses walk-forward optimisation to find robust parameters.
"""

import logging
from dataclasses import dataclass
from itertools import product
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

import config
from signal_engine import SignalEngine
from indicators import add_all_indicators

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    params:            dict
    total_trades:      int
    win_rate:          float
    total_pnl_pct:     float
    max_drawdown_pct:  float
    sharpe:            float
    profit_factor:     float
    avg_trade_pct:     float
    best_trade_pct:    float
    worst_trade_pct:   float


class BacktestEngine:

    def __init__(self):
        self.signal_engine = SignalEngine()

    # ── Single backtest ──────────────────────────────────────

    def run(
        self,
        df: pd.DataFrame,
        symbol: str,
        asset_class: str,
        timeframe: str,
        params: Optional[dict] = None,
        initial_capital: float = config.STARTING_CAPITAL,
        commission_bps: float = 20,
    ) -> BacktestResult:
        """
        Runs a single backtest on df with given params.
        df: OHLCV DataFrame, DatetimeIndex, oldest → newest
        """
        if params:
            self._apply_params(params)

        capital  = initial_capital
        peak     = initial_capital
        trades   = []
        position = None
        max_dd   = 0.0

        for i in range(60, len(df)):
            window = df.iloc[:i]
            last   = df.iloc[i]

            # Monitor open position
            if position:
                cp = last["close"]
                if (position["side"] == "long"  and cp <= position["sl"]) or \
                   (position["side"] == "short" and cp >= position["sl"]):
                    pnl_pct = self._calc_pnl(position, cp, commission_bps)
                    capital *= (1 + pnl_pct)
                    trades.append({"pnl_pct": pnl_pct, "exit": "SL"})
                    position = None

                elif (position["side"] == "long"  and cp >= position["tp"]) or \
                     (position["side"] == "short" and cp <= position["tp"]):
                    pnl_pct = self._calc_pnl(position, cp, commission_bps)
                    capital *= (1 + pnl_pct)
                    trades.append({"pnl_pct": pnl_pct, "exit": "TP"})
                    position = None

            # Look for new signal
            if position is None:
                signal = self.signal_engine.analyse(window, symbol, asset_class, timeframe)
                if signal:
                    position = {
                        "side":  signal.side,
                        "entry": signal.entry_price,
                        "sl":    signal.stop_loss,
                        "tp":    signal.take_profit,
                    }

            # Track drawdown
            peak = max(peak, capital)
            dd   = (peak - capital) / peak
            max_dd = max(max_dd, dd)

        return self._compute_result(trades, params or {}, max_dd, initial_capital, capital)

    # ── Walk-forward optimisation ────────────────────────────

    def walk_forward(
        self,
        df: pd.DataFrame,
        symbol: str,
        asset_class: str,
        timeframe: str,
        param_grid: dict,
        n_splits: int = 5,
        train_pct: float = 0.70,
    ) -> Tuple[dict, List[BacktestResult]]:
        """
        Walk-forward optimisation.
        param_grid: dict of {param_name: [values_to_try]}
        Returns (best_params, list_of_oos_results)
        """
        split_size = len(df) // n_splits
        all_params  = list(self._grid(param_grid))
        oos_results = []
        best_params = {}

        logger.info(f"Walk-forward: {n_splits} splits, {len(all_params)} param combos")

        for split in range(n_splits - 1):
            train_start = split * split_size
            train_end   = train_start + int(split_size * train_pct * (split + 1))
            test_start  = train_end
            test_end    = test_start + split_size

            train_df = df.iloc[train_start:train_end]
            test_df  = df.iloc[train_start:test_end]  # include train for warmup

            # Find best params on training window
            best_sharpe = -999
            best_p      = all_params[0] if all_params else {}

            for params in all_params:
                r = self.run(train_df, symbol, asset_class, timeframe, params)
                if r.sharpe > best_sharpe:
                    best_sharpe = r.sharpe
                    best_p      = params

            # Evaluate on out-of-sample window
            oos_r = self.run(test_df.iloc[train_end - train_start:],
                             symbol, asset_class, timeframe, best_p)
            oos_results.append(oos_r)
            best_params = best_p

            logger.info(
                f"Split {split+1}/{n_splits-1}: best_params={best_p} "
                f"OOS sharpe={oos_r.sharpe:.2f} winrate={oos_r.win_rate:.1%}"
            )

        return best_params, oos_results

    # ── Helpers ──────────────────────────────────────────────

    def _calc_pnl(self, position: dict, exit_price: float, commission_bps: float) -> float:
        direction = 1 if position["side"] == "long" else -1
        raw_pnl   = direction * (exit_price - position["entry"]) / position["entry"]
        costs     = commission_bps / 10_000
        return raw_pnl - costs

    def _compute_result(self, trades, params, max_dd, initial, final) -> BacktestResult:
        if not trades:
            return BacktestResult(params, 0, 0, 0, max_dd * 100, 0, 0, 0, 0, 0)

        pnls   = [t["pnl_pct"] for t in trades]
        wins   = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        total  = (final - initial) / initial * 100

        sharpe = 0.0
        if len(pnls) > 1 and np.std(pnls) > 0:
            sharpe = (np.mean(pnls) / np.std(pnls)) * np.sqrt(252)

        profit_factor = abs(sum(wins) / sum(losses)) if losses and sum(losses) != 0 else float("inf")

        return BacktestResult(
            params=params,
            total_trades=len(trades),
            win_rate=len(wins) / len(trades),
            total_pnl_pct=round(total, 2),
            max_drawdown_pct=round(max_dd * 100, 2),
            sharpe=round(sharpe, 2),
            profit_factor=round(profit_factor, 2),
            avg_trade_pct=round(np.mean(pnls) * 100, 4),
            best_trade_pct=round(max(pnls) * 100, 4),
            worst_trade_pct=round(min(pnls) * 100, 4),
        )

    def _apply_params(self, params: dict):
        for k, v in params.items():
            if hasattr(config, k):
                setattr(config, k, v)

    @staticmethod
    def _grid(param_grid: dict) -> List[dict]:
        keys   = list(param_grid.keys())
        values = list(param_grid.values())
        return [dict(zip(keys, combo)) for combo in product(*values)]


# ── CLI runner ───────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(levelname)s | %(message)s")

    print("\n  Backtest Engine — Walk-Forward Optimiser")
    print("  ─────────────────────────────────────────")
    print("  This requires historical OHLCV data.")
    print("  Example usage:")
    print()
    print("    from backtest_engine import BacktestEngine")
    print("    import pandas as pd")
    print()
    print("    df = pd.read_csv('BTC_1m.csv', index_col='timestamp', parse_dates=True)")
    print("    bt = BacktestEngine()")
    print()
    print("    # Single backtest")
    print("    result = bt.run(df, 'BTC/USDT', 'crypto', '1m')")
    print("    print(result)")
    print()
    print("    # Walk-forward with param grid")
    print("    best, oos = bt.walk_forward(df, 'BTC/USDT', 'crypto', '1m',")
    print("        param_grid={'EMA_FAST': [5, 8, 13], 'EMA_SLOW': [21, 34]})")
    print()
