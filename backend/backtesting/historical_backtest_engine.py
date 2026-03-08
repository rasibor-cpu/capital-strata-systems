from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class Candle:
    ts: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Trade:
    entry: float
    exit: float
    pnl: float


class HistoricalBacktestEngine:
    def __init__(
        self,
        starting_capital: float = 200.0,
        take_profit_pct: float = 0.02,
        stop_loss_pct: float = 0.015,
    ) -> None:
        self.starting_capital = starting_capital
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct
        self.reset()

    def reset(self) -> None:
        self.capital = self.starting_capital
        self.position = None
        self.trades: List[Trade] = []

    def load_csv(self, path: Path) -> List[Candle]:
        candles: List[Candle] = []

        with path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                candles.append(
                    Candle(
                        ts=row["ts"],
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=float(row["volume"]),
                    )
                )

        return candles

    def signal(self, candles: List[Candle], i: int) -> bool:
        if i < 3:
            return False

        avg = (
            candles[i - 1].close +
            candles[i - 2].close +
            candles[i - 3].close
        ) / 3.0

        return candles[i].close < avg * 0.995

    def run(self, asset: str, candles: List[Candle]) -> None:
        self.reset()
        allocation = 40.0

        for i in range(len(candles)):
            candle = candles[i]

            if self.position is None:
                if self.capital >= allocation and self.signal(candles, i):
                    entry = candle.close
                    size = allocation / entry
                    self.capital -= allocation
                    self.position = (entry, size)
                continue

            entry, size = self.position

            tp = entry * (1.0 + self.take_profit_pct)
            sl = entry * (1.0 - self.stop_loss_pct)

            exit_price = None

            if candle.high >= tp:
                exit_price = tp
            elif candle.low <= sl:
                exit_price = sl
            elif i == len(candles) - 1:
                exit_price = candle.close

            if exit_price is not None:
                pnl = (exit_price - entry) * size
                self.capital += size * exit_price
                self.trades.append(
                    Trade(entry=entry, exit=exit_price, pnl=pnl)
                )
                self.position = None

        wins = sum(1 for t in self.trades if t.pnl > 0)
        losses = sum(1 for t in self.trades if t.pnl <= 0)

        print("\nCSS Historical Backtest Result\n")
        print("Asset:", asset)
        print("Starting Capital:", f"${self.starting_capital:.2f}")
        print("Ending Capital:", f"${self.capital:.2f}")
        print("Total PnL:", f"${self.capital - self.starting_capital:.2f}")
        print("Trades:", len(self.trades))
        print("Wins:", wins)
        print("Losses:", losses)

        if self.trades:
            print("Win Rate:", f"{wins / len(self.trades) * 100:.2f}%")
        else:
            print("Win Rate: 0.00%")

    def summary(self) -> dict:
        wins = sum(1 for t in self.trades if t.pnl > 0)
        losses = sum(1 for t in self.trades if t.pnl <= 0)
        win_rate = round((wins / len(self.trades)) * 100.0, 2) if self.trades else 0.0

        return {
            "starting_capital": round(self.starting_capital, 2),
            "ending_capital": round(self.capital, 2),
            "total_pnl": round(self.capital - self.starting_capital, 2),
            "trades": len(self.trades),
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
        }


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage:")
        print("python historical_backtest_engine.py <csv_file>")
        return

    csv_file = Path("data_cache") / sys.argv[1]
    asset = sys.argv[1].split("_")[0]

    engine = HistoricalBacktestEngine()
    candles = engine.load_csv(csv_file)
    engine.run(asset, candles)


if __name__ == "__main__":
    main()