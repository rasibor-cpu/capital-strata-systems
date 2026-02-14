from __future__ import annotations

from datetime import datetime, timezone


class Simulator:
    def __init__(self, starting_equity: float = 100000.0):
        self.starting_equity = starting_equity
        self.equity = starting_equity

        self.position = None
        self.trades_today = 0
        self.daily_pnl = 0.0
        self.consecutive_losses = 0

        self.cooldown_active = False
        self.cooldown_until = None

        self.equity_peak = starting_equity

    # NOTE: The rest of your Simulator methods should already exist below in your repo.
    # If this file in your repo is longer, DO NOT truncate it.
    # Instead: keep your full existing class + methods, and only add the helpers below.

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def smoke_test() -> None:
    """
    Minimal run harness so `python backend\\app\\simulator.py` produces output.
    This is a Phase-1 sanity test only (no broker, no execution).
    """
    sim = Simulator(starting_equity=100000.0)

    print("SIMULATOR STARTED")
    print("Initial risk_state:", sim.risk_state())

    sim.open_position(side="LONG", entry_price=100.0, size=1.0)
    sim.close_position(pnl=+250.0)
    print("After 1 win:", sim.risk_state())

    for i in range(5):
        sim.open_position(side="LONG", entry_price=100.0, size=1.0)
        sim.close_position(pnl=-100.0)
        print(f"After loss {i+1}:", sim.risk_state())

    sim.cooldown_active = True
    sim.cooldown_until = _utcnow()
    print("Cooldown set:", sim.risk_state())

    print("SIMULATOR SMOKE TEST COMPLETE")


if __name__ == "__main__":
    smoke_test()
