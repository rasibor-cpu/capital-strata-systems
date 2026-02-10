from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Literal


Side = Literal["LONG", "SHORT"]


@dataclass
class Position:
    side: Side
    entry_price: float
    size: float
    entry_tick_id: int
    stop_distance: float


@dataclass
class SimulationState:
    equity: float
    position: Optional[Position] = None
    last_trade_pnl: float = 0.0


class TradingSimulator:
    """
    Institutional-style simulator with dynamic position sizing.

    Position size = (equity * risk_per_trade_pct) / stop_distance
    """

    def __init__(
        self,
        starting_equity: float = 100000.0,
        risk_per_trade_pct: float = 0.01,   # 1%
        max_position_size: float = 1000.0,
    ):
        self.state = SimulationState(equity=starting_equity)
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_position_size = max_position_size

    # ---------------------------------------------------------
    # Position Sizing Logic
    # ---------------------------------------------------------
    def _calculate_size(self, stop_distance: float) -> float:
        if stop_distance <= 0:
            return 0.0

        capital_at_risk = self.state.equity * self.risk_per_trade_pct
        size = capital_at_risk / stop_distance

        return min(size, self.max_position_size)

    # ---------------------------------------------------------
    # Core Signal Processor
    # ---------------------------------------------------------
    def process_signal(
        self,
        signal: str,
        price: float,
        tick_id: int,
        band_width: float | None,
    ) -> tuple[str, float]:
        """
        Returns (action, pnl)

        band_width used as volatility proxy for stop distance.
        """

        pos = self.state.position

        # ---------------------------------------------------
        # 1. No open position
        # ---------------------------------------------------
        if pos is None:
            if signal in ("LONG", "SHORT") and band_width:
                stop_distance = band_width

                size = self._calculate_size(stop_distance)

                if size <= 0:
                    return "HOLD", 0.0

                self.state.position = Position(
                    side=signal,
                    entry_price=price,
                    size=size,
                    entry_tick_id=tick_id,
                    stop_distance=stop_distance,
                )

                return f"OPEN_{signal}", 0.0

            return "HOLD", 0.0

        # ---------------------------------------------------
        # 2. Position exists — exit on opposite signal
        # ---------------------------------------------------
        pnl = 0.0

        if pos.side == "LONG" and signal == "SHORT":
            pnl = (price - pos.entry_price) * pos.size
        elif pos.side == "SHORT" and signal == "LONG":
            pnl = (pos.entry_price - price) * pos.size
        else:
            return "HOLD", 0.0

        # Close
        self.state.position = None
        self.state.equity += pnl
        self.state.last_trade_pnl = pnl

        return "CLOSE", pnl
