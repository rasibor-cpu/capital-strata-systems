from __future__ import annotations

import os
import sys
import subprocess

from backend.risk.trading_safety import TradingSafety


def _banner() -> None:
    print("\n==============================")
    print(" CAPITAL STRATA SYSTEMS ENGINE ")
    print("==============================\n")


def arm_live_trading() -> bool:
    while True:
        response = input("Arm LIVE trading? (Y/N): ").strip().upper()
        if response == "Y":
            os.environ["LIVE_TRADING_ARMED"] = "YES"
            print("\nLIVE trading is ARMED")
            return True
        if response == "N":
            os.environ["LIVE_TRADING_ARMED"] = "NO"
            print("\nLIVE trading is DISARMED")
            return False
        print("Please enter Y or N.")


def select_mode() -> str:
    print("\nSelect trading mode for today:\n")
    print("1 - DRY RUN (no real trades)")
    print("2 - PAPER TEST (simulated execution)")
    print("3 - LIVE TRADING\n")

    while True:
        mode = input("Enter mode (1-3): ").strip()
        if mode == "1":
            os.environ["TRADE_MODE"] = "DRY_RUN"
            return "DRY_RUN"
        if mode == "2":
            os.environ["TRADE_MODE"] = "PAPER"
            return "PAPER"
        if mode == "3":
            if os.environ.get("LIVE_TRADING_ARMED") != "YES":
                print("\nLIVE trading was not armed. Restart and arm LIVE trading first.")
                sys.exit(1)
            os.environ["TRADE_MODE"] = "LIVE"
            return "LIVE"
        print("Invalid choice.")


def start_engine() -> int:
    _banner()

    armed = arm_live_trading()
    mode = select_mode()

    # Initialize safety (reads env we just set)
    safety = TradingSafety()

    print("\n----------------------------------")
    print("ENGINE START SUMMARY")
    print("----------------------------------")
    print("Live Armed:", armed)
    print("Mode:", mode)
    print("Kill Switch File:", str(safety.cfg.kill_switch_file))
    print("Kill Switch Active:", safety.kill_switch_active())
    print("MAX_LIVE_QUOTE:", safety.cfg.max_live_quote)
    print("MAX_ORDERS_PER_SESSION:", safety.cfg.max_orders_per_session)
    print("ORDER_COOLDOWN_SECONDS:", safety.cfg.order_cooldown_seconds)

    if mode == "LIVE" and safety.kill_switch_active():
        print("\nKILL SWITCH ACTIVE — LIVE trading blocked.")
        print("Remove tools\\KILL_SWITCH.flag to proceed.")
        return 1

    print("\nInitializing trading executor...\n")
    from backend.execution.coinbase_executor import CoinbaseExecutor

    _ = CoinbaseExecutor()
    print("Coinbase executor ready.\n")

    # Launch the strategy loop as a module so imports work and env is inherited
    print("Launching strategy loop...\n")
    cmd = [sys.executable, "-m", "backend.engine.strategy_loop"]
    return subprocess.call(cmd, env=os.environ.copy())


if __name__ == "__main__":
    raise SystemExit(start_engine())