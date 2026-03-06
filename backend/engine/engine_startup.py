"""
Capital Strata Systems
Engine Startup Controller

Flow:
1) Arm LIVE trading? (Y/N)
2) Select broker (Coinbase/OANDA/Alpaca)
3) Select mode (DRY_RUN / PAPER / LIVE)
4) Ensure broker SDK installed
5) Initialize executor
6) Launch strategy loop
"""

from __future__ import annotations

import os
import sys


def arm_live_trading() -> bool:

    print("\n====================================")
    print(" CAPITAL STRATA SYSTEMS ENGINE ")
    print("====================================\n")

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


def select_broker() -> str:

    print("\nSelect broker for today:\n")
    print("1 - Coinbase")
    print("2 - OANDA")
    print("3 - Alpaca\n")

    while True:

        choice = input("Broker (1-3): ").strip()

        if choice == "1":
            os.environ["BROKER"] = "coinbase"
            return "coinbase"

        if choice == "2":
            os.environ["BROKER"] = "oanda"
            return "oanda"

        if choice == "3":
            os.environ["BROKER"] = "alpaca"
            return "alpaca"

        print("Invalid choice.")


def select_mode(armed: bool) -> str:

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
            if not armed or os.environ.get("LIVE_TRADING_ARMED") != "YES":
                print("\nLIVE trading was not armed.")
                print("Restart and arm live trading first.")
                sys.exit(1)

            os.environ["TRADE_MODE"] = "LIVE"
            return "LIVE"

        print("Invalid choice.")


def start_engine() -> int:

    armed = arm_live_trading()
    broker = select_broker()
    mode = select_mode(armed)

    # Ensure broker SDK is installed before importing broker executor
    from backend.broker.broker_bootstrap import bootstrap_broker

    bootstrap_broker(broker)

    print("\n----------------------------------")
    print("ENGINE START SUMMARY")
    print("----------------------------------")
    print("Live Armed:", armed)
    print("Broker:", broker)
    print("Mode:", mode)

    print("\nInitializing trading executor...\n")

    if broker == "coinbase":
        from backend.execution.coinbase_executor import CoinbaseExecutor

        _ = CoinbaseExecutor()
        print("Coinbase executor ready.")

        print("\nLaunching strategy loop...\n")
        from backend.engine.strategy_loop import run_loop

        run_loop()
        return 0

    print(f"\nBroker selected '{broker}' but no executor wired yet.")
    print("For now, select Coinbase (1) until other executors are implemented.")
    return 1


if __name__ == "__main__":
    raise SystemExit(start_engine())