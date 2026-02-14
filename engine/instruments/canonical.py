"""
Canonical Instruments (REA / Capital Strata Systems)
===================================================

This module defines the canonical instrument layer used across the system.

Invariant:
Strategy Concept → Canonical REA Instrument → Broker Symbol

- Canonical instruments are stable IDs the engine reasons about.
- Broker symbols are adapter-specific and may change.
- Any missing/ambiguous mapping must hard-fail at startup.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class CanonicalInstrument:
    """
    Canonical REA Instrument definition.

    Examples:
      - FUT_ES (S&P 500 E-mini futures)
      - FUT_NQ (Nasdaq-100 E-mini futures)
      - FX_EURUSD (spot FX pair concept)
    """
    canonical_id: str          # stable internal ID (e.g., "FUT_ES")
    asset_class: str           # "fx" | "futures" (extend later)
    name: str                  # human-readable
    exchange_hint: str = ""    # optional, informational
    contract_hint: str = ""    # optional, informational


# ----------------------------
# Phase 2A Futures Canonicals
# ----------------------------

CANONICAL_INSTRUMENTS: Dict[str, CanonicalInstrument] = {
    "FUT_ES": CanonicalInstrument(
        canonical_id="FUT_ES",
        asset_class="futures",
        name="E-mini S&P 500 Futures",
        exchange_hint="CME",
        contract_hint="ES (front-month roll policy applies)",
    ),
    "FUT_NQ": CanonicalInstrument(
        canonical_id="FUT_NQ",
        asset_class="futures",
        name="E-mini Nasdaq-100 Futures",
        exchange_hint="CME",
        contract_hint="NQ (front-month roll policy applies)",
    ),
}
