"""
Capital Strata Systems
Engine Startup Controller

This module ensures the engine cannot start live trading
without explicit operator confirmation, then selects broker,
ensures broker SDK is installed, and launches strategy loop.
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


def start_engine():

    armed = arm_live_trading()
    broker = select_broker()
    mode = select_mode(armed)

    # Ensure broker SDK is installed before importing executor
    from backend.broker.broker_bootstrap import bootstrap_broker

    bootstrap_broker(broker)

    print("\n----------------------------------")
    print("ENGINE START SUMMARY")
    print("----------------------------------")
    print("Live Armed:", armed)
    print("Broker:", broker)
    print("Mode:", mode)

    print("\nInitializing trading executor...\n")

    # For now: Coinbase executor is our active implementation.
    # Later: broker factory will route to the selected broker.
    if broker == "coinbase":
        from backend.execution.coinbase_executor import CoinbaseExecutor

        executor = CoinbaseExecutor()
        print("Coinbase executor ready.")
        return executor

    print(f"\nBroker selected '{broker}' but no executor wired yet.")
    print("For now, select Coinbase (1) until other executors are implemented.")
    sys.exit(1)


if __name__ == "__main__":

    start_engine()