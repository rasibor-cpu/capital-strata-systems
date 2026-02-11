"""
REA CAPITAL – GUARDED PRACTICE EXECUTION
"""

import os
from dotenv import load_dotenv
from backend.app.brokers.oanda_adapter import OandaAdapter

load_dotenv()


def require(condition: bool, message: str):
    if not condition:
        print(f"ABORT: {message}")
        exit(1)


def main():
    print("\n=================================================")
    print("REA CAPITAL – GUARDED PRACTICE")
    print("=================================================\n")

    env = os.getenv("OANDA_ENV", "").upper()
    base_url = os.getenv("OANDA_BASE_URL")
    headless = os.getenv("HEADLESS_DEV_MODE", "").lower() == "true"

    print(f"OANDA_ENV        : {env}")
    print(f"OANDA_BASE_URL   : {base_url}")
    print(f"HEADLESS_DEV_MODE: {headless}\n")

    require(env == "PRACTICE", "Practice runner requires OANDA_ENV=PRACTICE.")
    require("api-fxpractice.oanda.com" in (base_url or ""),
            "Practice runner requires practice base URL.")
    require(headless, "HEADLESS_DEV_MODE must be true.")

    adapter = OandaAdapter()

    require(adapter.is_configured(), "OANDA not configured correctly.")

    summary = adapter.get_account_summary()
    print(summary)

    print("\nPractice environment ready.\n")


if __name__ == "__main__":
    main()
