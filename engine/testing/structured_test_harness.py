"""
Structured Test Harness – REA Capital Trading Engine (V1 Freeze)
---------------------------------------------------------------

Now:
- Uses TradeTicket (UTRN generated)
- Runs duplicate warning check (non-blocking)
- Auto-logs closed trades into TEST ledger file (separate physical file)

V1 locked controls:
- Max trades/day: 20
- Max concurrent: 50
- Drawdown cap: 30%
- Loss streak: 5 -> cooldown
- Cooldown: 60 minutes
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from engine.reporting.pnl_ledger import append_pnl_event
from trade_ticket import TradeTicket


# -----------------------------
# V1 locked parameters
# -----------------------------
MAX_TRADES_PER_DAY = 20
MAX_CONCURRENT_POSITIONS = 50
DRAWDOWN_CAP = 0.30
LOSS_STREAK_LIMIT = 5
COOLDOWN_MINUTES = 60

# Harness parameters
MINUTE_STEP = 10


def _utc_date_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


@dataclass
class RiskState:
    equity: float
    peak_equity: float
    trades_today: int = 0
    open_positions: int = 0
    loss_streak: int = 0
    cooldown_active: int = 0
    cooldown_until_minute: int = -1

    def drawdown_pct(self) -> float:
        if self.peak_equity <= 0:
            return 0.0
        return max(0.0, (self.peak_equity - self.equity) / self.peak_equity)


def _can_trade(state: RiskState, minute: int) -> Optional[str]:
    if state.cooldown_active and minute < state.cooldown_until_minute:
        return "cooldown_active"
    if state.trades_today >= MAX_TRADES_PER_DAY:
        return "max_trades_reached"
    if state.open_positions >= MAX_CONCURRENT_POSITIONS:
        return "max_concurrent_reached"
    if state.drawdown_pct() >= DRAWDOWN_CAP:
        return "drawdown_cap_reached"
    return None


def _log_closed_trade_from_ticket(
    *,
    ticket: TradeTicket,
    exit_px: float,
    fees: float,
) -> None:
    qty = ticket.qty
    if qty <= 0 and ticket.entry_px > 0:
        qty = ticket.amount / ticket.entry_px

    append_pnl_event(
        mode=ticket.mode,
        symbol=ticket.symbol,
        side=ticket.side,
        qty=qty,
        entry_px=ticket.entry_px,
        exit_px=exit_px,
        fees=fees,
        trade_type=ticket.trade_type,
        execution_date=ticket.execution_date,
        value_date=ticket.value_date,
        currency=ticket.currency,
        amount=ticket.amount,
        fx_rate=ticket.fx_rate,
        exchange_rate_text=ticket.exchange_rate_text,
        tag=ticket.tag or "structured_harness",
        trade_id=ticket.utrn,  # UTRN becomes trade_id in ledger
        ledger_path=ticket.ledger_path(),  # separate TEST/LIVE files
    )


def run_structured_validation() -> None:
    print("=== STRUCTURED LOGIC VALIDATION (V1) ===")

    starting_equity = 100000.00
    state = RiskState(equity=starting_equity, peak_equity=starting_equity)

    trade_returns: List[float] = [0.02, 0.03, -0.02, -0.03, -0.01, -0.02, -0.01]
    notional = 5000.00
    fees = 1.25

    symbol = "EURUSD"
    side = "BUY"
    entry_px = 1.0900

    minute = 0
    trade_index = 0

    while True:
        reason = _can_trade(state, minute)

        if trade_index < len(trade_returns) and reason is None:
            r = trade_returns[trade_index]
            trade_index += 1
            state.trades_today += 1

            # Create ticket (UTRN auto)
            ticket = TradeTicket(
                mode="TEST",
                trade_type="SPOT",
                symbol=symbol,
                side=side,
                currency="USD",
                amount=notional,
                qty=0.0,  # derived
                entry_px=entry_px,
                requested_px=entry_px,
                execution_date=_utc_date_iso(),
                value_date=_utc_date_iso(),
                fx_rate=1.0,
                exchange_rate_text=f"EUR/USD {entry_px:.4f}",
                override_duplicate=False,  # UI button later toggles this
                tag="structured_harness",
                note="V1 validation",
            )

            # Duplicate warning (non-blocking)
            dup = ticket.run_duplicate_check()
            if dup.decision == "WARN":
                print(f"\nWARNING | DUPLICATE_TRADE | {dup.reason}")
                print(f"WARNING | UTRN={ticket.utrn}")

            pnl = notional * r
            state.equity += pnl
            state.peak_equity = max(state.peak_equity, state.equity)

            if pnl < 0:
                state.loss_streak += 1
            elif pnl > 0:
                state.loss_streak = 0

            dd = state.drawdown_pct()

            print(f"\nTRADE #{state.trades_today} | Return {r*100:.2f}% | PnL {pnl:.2f}")
            print(f"UTRN:   {ticket.utrn}")
            print(f"Minute: {minute}")
            print(f"Equity: {state.equity:.2f}")
            print(f"Peak:   {state.peak_equity:.2f}")
            print(f"DD:     {dd*100:.2f}%")
            print(f"Trades: {state.trades_today}/{MAX_TRADES_PER_DAY}")
            print(f"Open:   {state.open_positions}/{MAX_CONCURRENT_POSITIONS}")
            print(f"LStk:   {state.loss_streak}/{LOSS_STREAK_LIMIT}")
            print(f"CD:     {state.cooldown_active} (until minute {state.cooldown_until_minute})")

            # Close the trade and auto-log into TEST ledger (separate file)
            exit_px = entry_px * (1.0 + r)  # BUY model
            ticket.exchange_rate_text = f"EUR/USD {exit_px:.4f}"
            _log_closed_trade_from_ticket(ticket=ticket, exit_px=exit_px, fees=fees)

            if state.loss_streak >= LOSS_STREAK_LIMIT:
                state.cooldown_active = 1
                state.cooldown_until_minute = minute + COOLDOWN_MINUTES
                print(f"\nCOOLDOWN | Loss streak {LOSS_STREAK_LIMIT} reached. Cooling down for {COOLDOWN_MINUTES} minutes.")

            if state.drawdown_pct() >= DRAWDOWN_CAP:
                print("\nHALT | Drawdown cap reached.")
                break

        else:
            if trade_index >= len(trade_returns) and (reason is None):
                break

            if reason is not None:
                dd = state.drawdown_pct()
                print("\n" + "-" * 60)
                print(f"BLOCKED | {reason}")
                print(f"Minute: {minute}")
                print(f"Equity: {state.equity:.2f}")
                print(f"Peak:   {state.peak_equity:.2f}")
                print(f"DD:     {dd*100:.2f}%")
                print(f"Trades: {state.trades_today}/{MAX_TRADES_PER_DAY}")
                print(f"Open:   {state.open_positions}/{MAX_CONCURRENT_POSITIONS}")
                print(f"LStk:   {state.loss_streak}/{LOSS_STREAK_LIMIT}")
                print(f"CD:     {state.cooldown_active} (until minute {state.cooldown_until_minute})")

            if trade_index >= len(trade_returns) and minute >= state.cooldown_until_minute:
                break

        minute += MINUTE_STEP
        if minute > 10000:
            print("\nHALT | Safety stop.")
            break

    print("\n" + "=" * 60)
    print("=== END TEST ===")
    print(f"Final Equity: {state.equity:.2f}")
    print(f"Peak Equity:  {state.peak_equity:.2f}")
    print(f"Final DD:     {state.drawdown_pct()*100:.2f}%")
    print(f"Trades Today: {state.trades_today}")
    print(f"Cooldown Until Minute: {state.cooldown_until_minute}")


if __name__ == "__main__":
    run_structured_validation()
