"""
Paper Trade Simulator (SAFE)
----------------------------
Deterministic, execution-free simulation engine.

Purpose:
- Simulate position entry/exit
- Apply conservative slippage + fees
- Track PnL, equity, drawdown
- Emit journal entries (append-only)

NO broker calls. NO live execution. NO side effects outside memory.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
import time


@dataclass
class SimulatedTrade:
    instrument: str
    direction: str                 # "LONG" | "SHORT"
    entry_price: float
    exit_price: float
    size: float                     # units
    pnl: float
    opened_ts: float
    closed_ts: float
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SimulatorState:
    starting_equity: float
    equity: float
    peak_equity: float
    drawdown_pct: float
    trades: List[SimulatedTrade] = field(default_factory=list)


class PaperSimulator:
    """
    Conservative paper trading simulator.
    """

    DEFAULT_SLIPPAGE_PCT = 0.0005     # 5 bps per side
    DEFAULT_FEE_PCT = 0.0002          # 2 bps per side

    def __init__(self, starting_equity: float):
        self.state = SimulatorState(
            starting_equity=starting_equity,
            equity=starting_equity,
            peak_equity=starting_equity,
            drawdown_pct=0.0,
        )

    def _apply_costs(self, price: float, side: str) -> float:
        """
        Adjust price for slippage + fees.
        """
        cost = price * (self.DEFAULT_SLIPPAGE_PCT + self.DEFAULT_FEE_PCT)
        if side == "entry":
            return price + cost
        return price - cost

    def simulate_trade(
        self,
        *,
        instrument: str,
        direction: str,
        entry_price: float,
        exit_price: float,
        size: float,
        meta: Optional[Dict[str, Any]] = None,
    ) -> SimulatedTrade:
        now = time.time()

        # Apply conservative costs
        entry_px = self._apply_costs(entry_price, "entry")
        exit_px = self._apply_costs(exit_price, "exit")

        if direction == "LONG":
            pnl = (exit_px - entry_px) * size
        elif direction == "SHORT":
            pnl = (entry_px - exit_px) * size
        else:
            raise ValueError("direction must be LONG or SHORT")

        # Update equity
        self.state.equity += pnl
        self.state.peak_equity = max(self.state.peak_equity, self.state.equity)
        dd = (self.state.peak_equity - self.state.equity) / self.state.peak_equity
        self.state.drawdown_pct = dd

        trade = SimulatedTrade(
            instrument=instrument,
            direction=direction,
            entry_price=entry_px,
            exit_price=exit_px,
            size=size,
            pnl=pnl,
            opened_ts=now,
            closed_ts=now,
            meta=meta or {},
        )
        self.state.trades.append(trade)
        return trade

    def snapshot(self) -> Dict[str, Any]:
        """
        Lightweight metrics snapshot.
        """
        wins = [t for t in self.state.trades if t.pnl > 0]
        losses = [t for t in self.state.trades if t.pnl <= 0]
        total = len(self.state.trades)

        return {
            "starting_equity": self.state.starting_equity,
            "equity": self.state.equity,
            "peak_equity": self.state.peak_equity,
            "drawdown_pct": round(self.state.drawdown_pct, 4),
            "trades": total,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / total, 4) if total > 0 else 0.0,
        }


# Safety invariant
if __name__ == "__main__":
    raise RuntimeError("paper_simulator.py is a library module only and must not be executed directly.")
