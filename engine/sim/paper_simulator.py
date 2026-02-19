"""
Paper Trade Simulator (SAFE)
----------------------------
Deterministic, execution-free simulation engine.

Purpose:
- Simulate position entry/exit
- Apply conservative slippage + fees
- Track PnL, equity, drawdown
- Optionally route CLOSE through PaperBroker (canonical close boundary):
    - PnL ledger append (engine.reporting.pnl_ledger)
    - RiskGovernor.record_trade_outcome() + InstrumentPerformanceLedger

NO broker calls. NO live execution.
Side effects:
- In default mode: memory only
- If use_broker_close=True: writes to configured pnl ledger path via TradeTicket.ledger_path()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import time

from engine.execution.paper_broker import PaperBroker, PaperFillResult


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

    # Optional broker-return metadata
    utrn: Optional[str] = None
    exit_px_effective: Optional[float] = None
    timestamp_utc: Optional[str] = None


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
        self._broker = PaperBroker()

    def _apply_costs(self, price: float, side: str) -> float:
        """
        Adjust price for slippage + fees.
        """
        cost = price * (self.DEFAULT_SLIPPAGE_PCT + self.DEFAULT_FEE_PCT)
        if side == "entry":
            return price + cost
        return price - cost

    def _pnl_math(self, *, direction: str, entry_px: float, exit_px: float, size: float) -> float:
        if direction == "LONG":
            return (exit_px - entry_px) * size
        if direction == "SHORT":
            return (entry_px - exit_px) * size
        raise ValueError("direction must be LONG or SHORT")

    def simulate_trade(
        self,
        *,
        instrument: str,
        direction: str,
        entry_price: float,
        exit_price: float,
        size: float,
        meta: Optional[Dict[str, Any]] = None,
        # Optional canonical close routing
        use_broker_close: bool = False,
        trade_ticket: Optional[Any] = None,
        risk_governor: Optional[Any] = None,
        fees: float = 0.0,
    ) -> SimulatedTrade:
        """
        If use_broker_close=False (default): pure in-memory simulation.

        If use_broker_close=True:
            - requires trade_ticket (TradeTicket) with:
                symbol, side, amount/qty, entry_px, mode, ledger_path()
            - calls PaperBroker.execute_and_close(ticket, fill_price, fees, risk_governor=...)
            - uses broker-returned pnl as authoritative pnl
        """
        now = time.time()
        meta = meta or {}

        # Conservative costs applied to what the strategy "thinks" it traded.
        entry_px_eff = self._apply_costs(entry_price, "entry")
        exit_px_eff = self._apply_costs(exit_price, "exit")

        pnl = self._pnl_math(direction=direction, entry_px=entry_px_eff, exit_px=exit_px_eff, size=size)

        utrn = None
        exit_px_authoritative = exit_px_eff
        ts_utc = datetime.now(timezone.utc).isoformat()

        if use_broker_close:
            if trade_ticket is None:
                raise ValueError("use_broker_close=True requires trade_ticket (TradeTicket)")
            # The broker close is the canonical boundary; it writes PnL ledger and records governor outcome.
            fill: PaperFillResult = self._broker.execute_and_close(
                trade_ticket,
                fill_price=float(exit_price),
                fees=float(fees),
                risk_governor=risk_governor,
            )
            # Use broker PnL as authoritative
            pnl = float(fill.pnl)
            utrn = str(fill.utrn)
            exit_px_authoritative = float(fill.exit_px)
            ts_utc = str(fill.timestamp_utc)

        # Update equity based on authoritative pnl
        self.state.equity += pnl
        self.state.peak_equity = max(self.state.peak_equity, self.state.equity)
        dd = (self.state.peak_equity - self.state.equity) / self.state.peak_equity
        self.state.drawdown_pct = dd

        trade = SimulatedTrade(
            instrument=instrument,
            direction=direction,
            entry_price=entry_px_eff,
            exit_price=exit_px_authoritative,
            size=size,
            pnl=pnl,
            opened_ts=now,
            closed_ts=now,
            meta=meta,
            utrn=utrn,
            exit_px_effective=exit_px_authoritative,
            timestamp_utc=ts_utc,
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
