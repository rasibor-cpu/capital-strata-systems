from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ManagedPosition:
    symbol: str
    side: str
    quantity: float
    entry_price: float
    entry_time_utc: str
    stop_loss_price: float
    take_profit_price: float
    max_hold_cycles: int
    opened_cycle_no: int
    original_quantity: float
    remaining_quantity: float
    status: str = "OPEN"
    exit_price: Optional[float] = None
    exit_time_utc: Optional[str] = None
    exit_reason: Optional[str] = None
    realized_pnl_usd: float = 0.0
    hold_cycles: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PositionManager:
    """
    CSS Position Manager

    Responsibilities:
    - prevent duplicate entries per symbol
    - track open positions
    - support stop updates
    - support partial reductions
    - enforce TP / SL / max hold exits
    - maintain normalized closed-trade history
    - produce summary stats for engine reporting

    Current scope:
    - long-only paper trading flow
    - safe for CSS paper execution layer
    """

    def __init__(
        self,
        *,
        take_profit_pct: float = 0.025,
        stop_loss_pct: float = 0.012,
        max_hold_cycles: int = 8,
    ) -> None:
        self.take_profit_pct = float(take_profit_pct)
        self.stop_loss_pct = float(stop_loss_pct)
        self.max_hold_cycles = int(max_hold_cycles)

        self.open_positions: Dict[str, ManagedPosition] = {}
        self.closed_positions: List[ManagedPosition] = []

    # ------------------------------------------------------------------
    # Core state helpers
    # ------------------------------------------------------------------
    def has_position(self, symbol: str) -> bool:
        return str(symbol).upper() in self.open_positions

    def has_open_position(self, symbol: str) -> bool:
        return self.has_position(symbol)

    def open_position_count(self) -> int:
        return len(self.open_positions)

    def closed_position_count(self) -> int:
        return len(self.closed_positions)

    def get_open_positions(self) -> List[Dict[str, Any]]:
        return [p.to_dict() for p in self.open_positions.values()]

    def get_closed_positions(self) -> List[Dict[str, Any]]:
        return [p.to_dict() for p in self.closed_positions]

    # ------------------------------------------------------------------
    # Opening positions
    # ------------------------------------------------------------------
    def open_position(
        self,
        symbol: str,
        entry_price: float,
        size: float,
        take_profit_pct: Optional[float] = None,
        stop_loss_pct: Optional[float] = None,
        cycle_no: int = 0,
        max_hold_cycles: Optional[int] = None,
        entry_time_utc: Optional[str] = None,
    ) -> None:
        symbol = str(symbol).upper()
        entry_price = float(entry_price)
        size = float(size)

        if entry_price <= 0:
            raise ValueError("entry_price must be > 0")

        if size <= 0:
            raise ValueError("size must be > 0")

        if self.has_position(symbol):
            raise ValueError(f"Open position already exists for {symbol}")

        tp_pct = float(take_profit_pct) if take_profit_pct is not None else self.take_profit_pct
        sl_pct = float(stop_loss_pct) if stop_loss_pct is not None else self.stop_loss_pct
        mhc = int(max_hold_cycles) if max_hold_cycles is not None else self.max_hold_cycles

        tp_price = entry_price * (1.0 + tp_pct)
        sl_price = entry_price * (1.0 - sl_pct)

        position = ManagedPosition(
            symbol=symbol,
            side="LONG",
            quantity=size,
            entry_price=entry_price,
            entry_time_utc=entry_time_utc or utc_now_iso(),
            stop_loss_price=sl_price,
            take_profit_price=tp_price,
            max_hold_cycles=mhc,
            opened_cycle_no=int(cycle_no),
            original_quantity=size,
            remaining_quantity=size,
        )

        self.open_positions[symbol] = position

        print(
            f"POSITION OPENED: {symbol} | "
            f"entry={entry_price:.6f} | "
            f"size={size:.8f} | "
            f"tp={tp_price:.6f} | "
            f"sl={sl_price:.6f} | "
            f"max_hold_cycles={mhc}"
        )

    def open_long_position(
        self,
        *,
        symbol: str,
        quantity: float,
        entry_price: float,
        cycle_no: int,
        opened_at_utc: Optional[str] = None,
        take_profit_pct: Optional[float] = None,
        stop_loss_pct: Optional[float] = None,
        max_hold_cycles: Optional[int] = None,
    ) -> Dict[str, Any]:
        self.open_position(
            symbol=symbol,
            entry_price=entry_price,
            size=quantity,
            take_profit_pct=take_profit_pct,
            stop_loss_pct=stop_loss_pct,
            cycle_no=cycle_no,
            max_hold_cycles=max_hold_cycles,
            entry_time_utc=opened_at_utc,
        )
        return self.open_positions[str(symbol).upper()].to_dict()

    # ------------------------------------------------------------------
    # Stop management
    # ------------------------------------------------------------------
    def update_stop(self, symbol: str, new_stop: float) -> None:
        symbol = str(symbol).upper()
        new_stop = float(new_stop)

        if symbol not in self.open_positions:
            return

        pos = self.open_positions[symbol]
        old_stop = float(pos.stop_loss_price)

        if new_stop > old_stop:
            pos.stop_loss_price = new_stop
            print(
                f"STOP UPDATED: {symbol} | "
                f"old_stop={old_stop:.6f} | "
                f"new_stop={new_stop:.6f}"
            )

    # ------------------------------------------------------------------
    # Partial reductions
    # ------------------------------------------------------------------
    def reduce_position(
        self,
        symbol: str,
        exit_price: float,
        size_reduction: float,
        reason: str = "",
    ) -> float:
        symbol = str(symbol).upper()
        exit_price = float(exit_price)
        size_reduction = float(size_reduction)

        if symbol not in self.open_positions:
            return 0.0

        pos = self.open_positions[symbol]
        entry = float(pos.entry_price)
        remaining = float(pos.remaining_quantity)
        reduce_amt = max(0.0, min(size_reduction, remaining))

        if reduce_amt <= 0:
            return 0.0

        pnl = (exit_price - entry) * reduce_amt
        pos.remaining_quantity = remaining - reduce_amt
        pos.realized_pnl_usd = round(float(pos.realized_pnl_usd) + pnl, 8)

        print(
            f"POSITION REDUCED: {symbol} | "
            f"reduced={reduce_amt:.8f} | "
            f"remaining={pos.remaining_quantity:.8f} | "
            f"exit={exit_price:.6f} | "
            f"PNL={pnl:.4f} | "
            f"reason={reason}"
        )

        if pos.remaining_quantity <= 0:
            self._finalize_close(
                symbol=symbol,
                exit_price=exit_price,
                exit_reason=reason or "FULLY_REDUCED",
                exit_time_utc=utc_now_iso(),
            )

        return round(pnl, 8)

    # ------------------------------------------------------------------
    # Full close
    # ------------------------------------------------------------------
    def close_position(self, symbol: str, exit_price: float, reason: str = "") -> float:
        symbol = str(symbol).upper()
        exit_price = float(exit_price)

        if symbol not in self.open_positions:
            return 0.0

        pos = self.open_positions[symbol]
        entry = float(pos.entry_price)
        remaining = float(pos.remaining_quantity)

        pnl = (exit_price - entry) * remaining
        total_pnl = float(pos.realized_pnl_usd) + pnl

        print(
            f"POSITION CLOSED: {symbol} | "
            f"entry={entry:.6f} | "
            f"exit={exit_price:.6f} | "
            f"remaining={remaining:.8f} | "
            f"PNL={pnl:.4f} | "
            f"reason={reason}"
        )

        pos.realized_pnl_usd = round(total_pnl, 8)
        self._finalize_close(
            symbol=symbol,
            exit_price=exit_price,
            exit_reason=reason or "MANUAL_CLOSE",
            exit_time_utc=utc_now_iso(),
        )
        return round(total_pnl, 8)

    def close_position_manually(
        self,
        *,
        symbol: str,
        exit_price: float,
        exit_reason: str = "MANUAL_CLOSE",
        exit_time_utc: Optional[str] = None,
    ) -> Dict[str, Any]:
        symbol = str(symbol).upper()
        exit_price = float(exit_price)

        if symbol not in self.open_positions:
            raise ValueError(f"No open position found for {symbol}")

        pos = self.open_positions[symbol]
        entry = float(pos.entry_price)
        remaining = float(pos.remaining_quantity)
        pnl = (exit_price - entry) * remaining
        pos.realized_pnl_usd = round(float(pos.realized_pnl_usd) + pnl, 8)

        self._finalize_close(
            symbol=symbol,
            exit_price=exit_price,
            exit_reason=exit_reason,
            exit_time_utc=exit_time_utc or utc_now_iso(),
        )
        return self.closed_positions[-1].to_dict()

    # ------------------------------------------------------------------
    # Exit checks
    # ------------------------------------------------------------------
    def check_exit(self, symbol: str, price: float) -> bool:
        symbol = str(symbol).upper()
        price = float(price)

        if symbol not in self.open_positions:
            return False

        pos = self.open_positions[symbol]

        if price >= float(pos.take_profit_price):
            print(f"TAKE PROFIT HIT: {symbol}")
            return True

        if price <= float(pos.stop_loss_price):
            print(f"STOP LOSS HIT: {symbol}")
            return True

        return False

    def update_positions(
        self,
        *,
        latest_prices: Dict[str, float],
        cycle_no: int,
        timestamp_utc: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        timestamp = timestamp_utc or utc_now_iso()
        closed_this_cycle: List[Dict[str, Any]] = []

        symbols = list(self.open_positions.keys())

        for symbol in symbols:
            pos = self.open_positions.get(symbol)
            if pos is None:
                continue

            latest_price = latest_prices.get(symbol)
            if latest_price is None:
                pos.hold_cycles = max(0, int(cycle_no) - int(pos.opened_cycle_no))
                continue

            latest_price = float(latest_price)
            pos.hold_cycles = max(0, int(cycle_no) - int(pos.opened_cycle_no))

            close_reason: Optional[str] = None

            if latest_price >= float(pos.take_profit_price):
                close_reason = "TAKE_PROFIT"
            elif latest_price <= float(pos.stop_loss_price):
                close_reason = "STOP_LOSS"
            elif pos.hold_cycles >= int(pos.max_hold_cycles):
                close_reason = "MAX_HOLD"

            if close_reason is None:
                continue

            remaining = float(pos.remaining_quantity)
            pnl = (latest_price - float(pos.entry_price)) * remaining
            pos.realized_pnl_usd = round(float(pos.realized_pnl_usd) + pnl, 8)

            self._finalize_close(
                symbol=symbol,
                exit_price=latest_price,
                exit_reason=close_reason,
                exit_time_utc=timestamp,
            )
            closed_this_cycle.append(self.closed_positions[-1].to_dict())

        return closed_this_cycle

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------
    def summary(self) -> Dict[str, Any]:
        wins = 0
        losses = 0
        gross_profit = 0.0
        gross_loss = 0.0

        for p in self.closed_positions:
            if p.realized_pnl_usd > 0:
                wins += 1
                gross_profit += float(p.realized_pnl_usd)
            elif p.realized_pnl_usd < 0:
                losses += 1
                gross_loss += abs(float(p.realized_pnl_usd))

        total_closed = len(self.closed_positions)
        win_rate = (wins / total_closed) if total_closed > 0 else 0.0
        realized_pnl = sum(float(p.realized_pnl_usd) for p in self.closed_positions)

        return {
            "open_positions": len(self.open_positions),
            "closed_trades": total_closed,
            "wins": wins,
            "losses": losses,
            "win_rate": round(win_rate, 8),
            "gross_profit_usd": round(gross_profit, 8),
            "gross_loss_usd": round(gross_loss, 8),
            "realized_pnl_usd": round(realized_pnl, 8),
        }

    # ------------------------------------------------------------------
    # Internal close helper
    # ------------------------------------------------------------------
    def _finalize_close(
        self,
        *,
        symbol: str,
        exit_price: float,
        exit_reason: str,
        exit_time_utc: str,
    ) -> None:
        symbol = str(symbol).upper()

        pos = self.open_positions[symbol]
        pos.status = "CLOSED"
        pos.exit_price = float(exit_price)
        pos.exit_reason = str(exit_reason)
        pos.exit_time_utc = exit_time_utc

        self.closed_positions.append(pos)
        del self.open_positions[symbol]