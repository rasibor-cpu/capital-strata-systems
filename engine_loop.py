"""
CSS Engine Runner (Compatibility Entrypoint)

This launcher executes the canonical engine located at:

    engine.engine_loop
"""

from engine.engine_loop import EngineLoop
import random
import time


def main() -> int:

    loop = EngineLoop()

    instruments = [
        "EUR_USD",
        "GBP_USD",
        "USD_JPY",
        "AUD_USD",
        "USD_CHF",
    ]

    price = 1.1000

    print("==== CSS ENGINE RUNNER ====")

    for step in range(500):

        instrument = random.choice(instruments)

        # simple price simulation
        price += random.uniform(-0.0005, 0.0005)

        loop.process_bar(
            instrument=instrument,
            price=price,
        )

    print("\n==== ENGINE SUMMARY ====")
    print(loop.summary())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())