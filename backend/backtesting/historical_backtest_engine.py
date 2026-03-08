from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class Candle:
    ts: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class BacktestTrade:
    asset: str
    entry_price: float
    exit_price: float
    size: float
    pnl_usd: float
    reason: str


@dataclass
class BacktestResult:
    asset: str
    starting_capital: float
    ending_capital: float
    total_pnl: float
    trades: int
    wins: int
    losses: int
    win_rate: float


class HistoricalBacktestEngine:
    """
    Phase 3 Historical Backtest Engine

    Reads candle data from CSV and runs a simple mean-reversion style
    portfolio simulation using fixed capital slices.
    """

    def __init__(
        self,
        starting_capital: float = 200.0,
        allocation_per_trade: float = 40.0,
        take_profit_pct: float = 0.02,
        stop_loss_pct: float = 0.015,
    ) -> None:
        self.starting_capital = starting_capital
        self.allocation_per_trade = allocation_per_trade
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct

    def load_candles_from_csv(self, csv_path: str | Path) -> List[Candle]:
        path = Path(csv_path)
        candles: List[Candle] = []

        with path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            required = {"ts", "open", "high", "low", "close", "volume"}
            missing = required - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"CSV missing required columns: {sorted(missing)}")

            for row in reader:
                candles.append(
                    Candle(
                        ts=str(row["ts"]),
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=float(row["volume"]),
                    )
                )

        if len(candles) < 5:
            raise ValueError("Need at least 5 candles for backtest.")

        return candles

    def _simple_signal(self, candles: List[Candle], idx: int) -> bool:
        """
        Entry signal:
        Buy when current close is below average of previous 3 closes.
        """
        if idx < 3:
            return False

        avg_prev_3 = (
            candles[idx - 1].close +
            candles[idx - 2].close +
            candles[idx - 3].close
        ) / 3.0

        return candles[idx].close < avg_prev_3 * 0.995

    def run_backtest(self, asset: str, candles: List[Candle]) -> BacktestResult:
        capital = self.starting_capital
        trades: List[BacktestTrade] = []

        in_position = False
        entry_price = 0.0
        size = 0.0

        for idx in range(len(candles)):
            candle = candles[idx]

            if not in_position:
                if capital >= self.allocation_per_trade and self._simple_signal(candles, idx):
                    entry_price = candle.close
                    size = self.allocation_per_trade / entry_price
                    capital -= self.allocation_per_trade
                    in_position = True
                continue

            tp_price = entry_price * (1.0 + self.take_profit_pct)
            sl_price = entry_price * (1.0 - self.stop_loss_pct)

            exit_price: Optional[float] = None
            reason = ""

            if candle.high >= tp_price:
                exit_price = tp_price
                reason = "take_profit"
            elif candle.low <= sl_price:
                exit_price = sl_price
                reason = "stop_loss"
            elif idx == len(candles) - 1:
                exit_price = candle.close
                reason = "final_bar_exit"

            if exit_price is not None:
                gross_value = size * exit_price
                pnl = gross_value - self.allocation_per_trade
                capital += gross_value

                trades.append(
                    BacktestTrade(
                        asset=asset,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        size=size,
                        pnl_usd=round(pnl, 2),
                        reason=reason,
                    )
                )

                in_position = False
                entry_price = 0.0
                size = 0.0

        total_pnl = round(capital - self.starting_capital, 2)
        wins = sum(1 for t in trades if t.pnl_usd > 0)
        losses = sum(1 for t in trades if t.pnl_usd <= 0)
        trades_count = len(trades)
        win_rate = round((wins / trades_count) * 100.0, 2) if trades_count else 0.0

        return BacktestResult(
            asset=asset,
            starting_capital=round(self.starting_capital, 2),
            ending_capital=round(capital, 2),
            total_pnl=total_pnl,
            trades=trades_count,
            wins=wins,
            losses=losses,
            win_rate=win_rate,
        )


def demo() -> None:
    engine = HistoricalBacktestEngine()

    sample_path = Path("data_cache") / "sample_backtest_data.csv"
    if not sample_path.exists():
        print(f"Sample CSV not found at: {sample_path}")
        print("Create the sample CSV first, then rerun this demo.")
        return

    candles = engine.load_candles_from_csv(sample_path)
    result = engine.run_backtest(asset="SAMPLE-USD", candles=candles)

    print("\nCSS Historical Backtest Result\n")
    print(f"Asset:            {result.asset}")
    print(f"Starting Capital: ${result.starting_capital:.2f}")
    print(f"Ending Capital:   ${result.ending_capital:.2f}")
    print(f"Total PnL:        ${result.total_pnl:.2f}")
    print(f"Trades:           {result.trades}")
    print(f"Wins:             {result.wins}")
    print(f"Losses:           {result.losses}")
    print(f"Win Rate:         {result.win_rate:.2f}%")


if __name__ == "__main__":
    demo()