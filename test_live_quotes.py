"""
REA Capital Trading Engine
Live Quote Smoke Test (READ-ONLY) — Real TwelveData Client Attempt

Branch: live-adapters
Purpose:
- Validate mapping → (real) TwelveData client → TwelveDataAdapter → LiveQuoteRouter → QuoteSnapshot
- NO execution, NO orders, NO account calls

Run:
  python test_live_quotes.py

Notes:
- This test attempts to import your real TwelveData client from:
    live_data/twelvedata_fx_adapter.py
- Because names may differ, we try multiple likely entrypoints.
- If we cannot locate a usable client, we fall back to a stub and print guidance.
"""

import os
import time
from typing import Any, Optional, Dict

from engine.live.live_quote_router import LiveQuoteRouter
from engine.live.adapters.twelvedata_adapter import TwelveDataAdapter
from engine.live.mapping.rea_symbol_map import broker_symbol_for_rea


# ---------------------------------------------------------
# STUB (fallback) — always safe
# ---------------------------------------------------------
class TwelveDataClientStub:
    def get_quote(self, symbol: str) -> dict:
        return {
            "bid": None,
            "ask": None,
            "price": 1.2345,
            "timestamp": time.time(),
        }


# ---------------------------------------------------------
# Try to build a REAL client from live_data/twelvedata_fx_adapter.py
# We do NOT assume the exact names inside your file.
# ---------------------------------------------------------
def _try_build_real_twelvedata_client() -> Optional[Any]:
    """
    Returns an object with: get_quote(symbol: str) -> dict
    If not found, returns None.
    """
    try:
        import importlib

        mod = importlib.import_module("live_data.twelvedata_fx_adapter")

        # Common env var names (use whichever you already have)
        api_key = (
            os.getenv("TWELVEDATA_API_KEY")
            or os.getenv("TWELVE_DATA_API_KEY")
            or os.getenv("TWELVEDATA_KEY")
        )

        # 1) If module exposes a ready-made client object
        for attr in ("client", "td_client", "twelvedata_client", "twelve_client"):
            obj = getattr(mod, attr, None)
            if obj is not None and hasattr(obj, "get_quote"):
                return obj

        # 2) If module exposes a class we can instantiate
        for cls_name in (
            "TwelveDataClient",
            "TwelvedataClient",
            "TwelveDataFXAdapter",
            "TwelveDataAdapter",
            "TwelveData",
        ):
            cls = getattr(mod, cls_name, None)
            if cls is not None and callable(cls):
                try:
                    # Try best-effort constructor patterns
                    if api_key is not None:
                        try:
                            return cls(api_key=api_key)
                        except TypeError:
                            try:
                                return cls(key=api_key)
                            except TypeError:
                                try:
                                    return cls(api_key)
                                except TypeError:
                                    pass
                    # No key available or not required
                    return cls()
                except Exception:
                    pass

        # 3) If module exposes a function that fetches quote directly
        for fn_name in ("get_quote", "fetch_quote", "quote", "get_fx_quote"):
            fn = getattr(mod, fn_name, None)
            if fn is not None and callable(fn):

                class FuncClient:
                    def get_quote(self, symbol: str) -> Dict:
                        return fn(symbol)  # type: ignore

                return FuncClient()

        # Nothing found
        _print_module_inventory(mod)
        return None

    except Exception as e:
        print("REAL CLIENT IMPORT FAILED:", repr(e))
        return None


def _print_module_inventory(mod: Any) -> None:
    try:
        names = sorted([n for n in dir(mod) if not n.startswith("_")])
        print("\n--- live_data.twelvedata_fx_adapter inventory (for wiring) ---")
        for n in names:
            print("  ", n)
        print("--- end inventory ---\n")
    except Exception:
        pass


def main():
    # Choose one REA instrument that exists in MAPPINGS
    rea_instrument = "FX.EURUSD.SPOT"

    # Build REA→broker mapping dict for router
    mapping = {rea_instrument: broker_symbol_for_rea(rea_instrument)}

    # Attempt real client
    real_client = _try_build_real_twelvedata_client()

    if real_client is None:
        print("Using STUB TwelveData client (real client not detected).")
        client = TwelveDataClientStub()
    else:
        print("Using REAL TwelveData client from live_data/twelvedata_fx_adapter.py")
        client = real_client

    # Wire adapter
    adapter = TwelveDataAdapter(client=client)

    # Wire router
    router = LiveQuoteRouter(adapter=adapter, mapping=mapping)

    # Pull snapshot
    snap = router.get_snapshot(rea_instrument=rea_instrument)

    print("\n==== LIVE QUOTE SNAPSHOT (READ-ONLY) ====")
    print(snap)
    print("========================================\n")


if __name__ == "__main__":
    main()
