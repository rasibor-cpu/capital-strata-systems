from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List

from backend.intelligence.regime_detector import RegimeDetector
from backend.strategies.mean_reversion import signal as mean_reversion_signal
from backend.strategies.trend_following import signal as trend_following_signal
from backend.strategies.breakout import signal as breakout_signal
from backend.risk.atr_risk_engine import ATRRiskEngine
from backend.risk.position_sizing_engine import PositionSizingEngine


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

    def __init__(self, starting_capital: float = 200.0):

        self.starting_capital = starting_capital

        self.detector = RegimeDetector()
        self.atr_engine = ATRRiskEngine()
        self.position_engine = PositionSizingEngine()

        self.reset()

    def reset(self):

        self.capital = self.starting_capital
        self.position = None
        self.trades: List[Trade] = []

    def load_csv(self, path: Path):

        candles = []

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

    def signal(self, candles, i):

        regime = self.detector.detect(candles, i)

        if regime == "RANGE":
            return mean_reversion_signal(candles, i)

        if regime == "TREND":
            return trend_following_signal(candles, i)

        if regime == "VOLATILE":
            return breakout_signal(candles, i)

        return False

    def run(self, asset, candles):

        self.reset()

        for i in range(len(candles)):

            candle = candles[i]

            if self.position is None:

                if self.signal(candles, i):

                    entry = candle.close

                    atr = self.atr_engine.compute_atr(candles, i)

                    if atr is None:
                        continue

                    size = self.position_engine.size_position(
                        self.capital,
                        entry,
                        atr
                    )

                    cost = size * entry

                    if cost > self.capital or size <= 0:
                        continue

                    self.capital -= cost

                    self.position = (entry, size)

                continue

            entry, size = self.position

            atr = self.atr_engine.compute_atr(candles, i)

            if atr is None:
                continue

            tp = self.atr_engine.take_profit(entry, atr)
            sl = self.atr_engine.stop_loss(entry, atr)

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

    def summary(self):

        wins = sum(1 for t in self.trades if t.pnl > 0)
        losses = sum(1 for t in self.trades if t.pnl <= 0)

        win_rate = 0

        if self.trades:
            win_rate = (wins / len(self.trades)) * 100

        return {
            "starting_capital": self.starting_capital,
            "ending_capital": round(self.capital, 2),
            "pnl": round(self.capital - self.starting_capital, 2),
            "trades": len(self.trades),
            "wins": wins,
            "losses": losses,
            "win_rate": round(win_rate, 2),
        }


def main():

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