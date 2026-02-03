"""
REA Capital Trading Engine
Live Quote Smoke Test (READ-ONLY) — TwelveData fetch_fx_1m path

Branch: live-adapters
Run:
  python test_live_quotes.py

This uses:
  live_data.twelvedata_fx_adapter.fetch_fx_1m(pair, limit)
wrapped by:
  TwelveDataFetchClient
"""

from engine.live.live_quote_router import LiveQuoteRouter
from engine.live.adapters.twelvedata_adapter import TwelveDataAdapter
from engine.live.adapters.twelvedata_fetch_client import TwelveDataFetchClient
from engine.live.mapping.rea_symbol_map import broker_symbol_for_rea


def main():
    rea_instrument = "FX.EURUSD.SPOT"
    mapping = {rea_instrument: broker_symbol_for_rea(rea_instrument)}

    # Real fetch-based client
    client = TwelveDataFetchClient(limit=1)

    adapter = TwelveDataAdapter(client=client)
    router = LiveQuoteRouter(adapter=adapter, mapping=mapping)

    snap = router.get_snapshot(rea_instrument=rea_instrument)

    print("\n==== LIVE QUOTE SNAPSHOT (READ-ONLY / REAL FETCH) ====")
    print(snap)
    print("====================================================\n")


if __name__ == "__main__":
    main()
