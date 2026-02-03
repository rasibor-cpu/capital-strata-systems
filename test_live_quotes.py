"""
REA Capital Trading Engine
Live Quote Smoke Test (READ-ONLY)

Branch: live-adapters
Purpose:
- Validate mapping → adapter → router wiring
- No execution, no orders, no accounts

Run:
  python test_live_quotes.py
"""

from engine.live.live_quote_router import LiveQuoteRouter
from engine.live.adapters.twelvedata_adapter import TwelveDataAdapter
from engine.live.mapping.rea_symbol_map import broker_symbol_for_rea


# ---------------------------------------------------------
# Minimal TwelveData client stub:
# Replace this with your real TwelveData client object.
# It MUST implement: get_quote(symbol: str) -> dict
# ---------------------------------------------------------
class TwelveDataClientStub:
    def get_quote(self, symbol: str) -> dict:
        # Example shape: you should replace with real API output
        return {
            "bid": None,
            "ask": None,
            "price": 1.2345,
            "timestamp": None,
        }


def main():
    # Choose one REA instrument that exists in MAPPINGS
    rea_instrument = "FX.EURUSD.SPOT"

    # Build REA→broker mapping dict for router
    mapping = {rea_instrument: broker_symbol_for_rea(rea_instrument)}

    # Wire adapter
    client = TwelveDataClientStub()
    adapter = TwelveDataAdapter(client=client)

    # Wire router
    router = LiveQuoteRouter(adapter=adapter, mapping=mapping)

    # Pull snapshot
    snap = router.get_snapshot(rea_instrument=rea_instrument)

    print("==== LIVE QUOTE SNAPSHOT (READ-ONLY) ====")
    print(snap)


if __name__ == "__main__":
    main()

