"""
Unified Market Scanner
Capital Strata Systems – Phase 18 (Futures Enabled)

Adds:
- Futures instruments
- Maintains crypto + FX scanning
- Non-breaking, additive only
"""

from typing import List, Dict

# =========================
# STATIC FUTURES UNIVERSE
# =========================

FUTURES_SYMBOLS = [
    "ES",  # S&P 500
    "NQ",  # Nasdaq
    "CL",  # Crude Oil
    "GC",  # Gold
    "ZN",  # 10Y Treasury
]


class UnifiedMarketScanner:

    def __init__(self):
        pass

    # =========================
    # MAIN SCAN
    # =========================

    def scan(self) -> List[Dict]:

        results: List[Dict] = []

        # =========================
        # CRYPTO (UNCHANGED)
        # =========================
        crypto_symbols = [
            "BTC-USD",
            "ETH-USD",
            "SOL-USD",
            "XRP-USD",
            "ADA-USD",
            "DOGE-USD",
            "AVAX-USD",
            "LINK-USD",
            "LTC-USD",
            "BCH-USD",
        ]

        for sym in crypto_symbols:
            results.append({
                "symbol": sym,
                "asset_class": "CRYPTO",
            })

        # =========================
        # FX (UNCHANGED)
        # =========================
        fx_symbols = [
            "EUR_USD",
            "GBP_USD",
            "USD_JPY",
            "AUD_USD",
            "USD_CAD",
        ]

        for sym in fx_symbols:
            results.append({
                "symbol": sym,
                "asset_class": "FX",
            })

        # =========================
        # 🔥 FUTURES (NEW)
        # =========================
        for sym in FUTURES_SYMBOLS:
            results.append({
                "symbol": sym,
                "asset_class": "FUTURES",
            })

        return results