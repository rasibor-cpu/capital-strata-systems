"""
Capital Strata Systems
Engine Startup Controller

This module ensures the engine cannot start live trading
without explicit operator confirmation.
"""

import os
import sys


def arm_live_trading():

    print("\n====================================")
    print(" CAPITAL STRATA SYSTEMS ENGINE ")
    print("====================================\n")

    while True:

        response = input("Arm LIVE trading? (Y/N): ").strip().upper()

        if response == "Y":

            os.environ["LIVE_TRADING_ARMED"] = "YES"

            print("\nLIVE trading is ARMED")

            return True

        elif response == "N":

            os.environ["LIVE_TRADING_ARMED"] = "NO"

            print("\nLIVE trading is DISARMED")

            return False

        else:

            print("Please enter Y or N.")


def select_mode():

    print("\nSelect trading mode for today:\n")

    print("1 - DRY RUN (no real trades)")
    print("2 - PAPER TEST (simulated execution)")
    print("3 - LIVE TRADING\n")

    while True:

        mode = input("Enter mode (1-3): ").strip()

        if mode == "1":

            os.environ["TRADE_MODE"] = "DRY_RUN"

            return "DRY_RUN"

        elif mode == "2":

            os.environ["TRADE_MODE"] = "PAPER"

            return "PAPER"

        elif mode == "3":

            if os.environ.get("LIVE_TRADING_ARMED") != "YES":

                print("\nLIVE trading was not armed.")

                print("Restart and arm live trading first.")

                sys.exit()

            os.environ["TRADE_MODE"] = "LIVE"

            return "LIVE"

        else:

            print("Invalid choice.")


def start_engine():

    armed = arm_live_trading()

    mode = select_mode()

    print("\n----------------------------------")
    print("ENGINE START SUMMARY")
    print("----------------------------------")

    print("Live Armed:", armed)
    print("Mode:", mode)

    print("\nInitializing trading executor...\n")

    from backend.execution.coinbase_executor import CoinbaseExecutor

    executor = CoinbaseExecutor()

    print("Coinbase executor ready.")

    return executor


if __name__ == "__main__":

    start_engine()