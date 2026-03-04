import subprocess
import sys

BROKER_PACKAGES = {
    "coinbase": "coinbase-advanced-py",
    "alpaca": "alpaca-trade-api",
    "oanda": "oandapyV20",
    "ib": "ib_insync"
}


def ensure_package(pkg):

    try:
        __import__(pkg.split("-")[0])
        print(f"SDK already installed: {pkg}")

    except ImportError:

        print(f"Installing broker SDK: {pkg}")

        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", pkg]
        )

        print(f"{pkg} installation complete.")


def bootstrap_broker(broker_name):

    broker_name = broker_name.lower()

    if broker_name not in BROKER_PACKAGES:
        raise RuntimeError(f"Unsupported broker: {broker_name}")

    pkg = BROKER_PACKAGES[broker_name]

    ensure_package(pkg)

    print(f"Broker ready: {broker_name}")