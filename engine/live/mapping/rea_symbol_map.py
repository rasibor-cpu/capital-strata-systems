"""
REA Capital Trading Engine
Governance-Locked Symbol Mapping (3-Layer Model)

Branch: live-adapters
Invariant (LOCKED):
Strategy Concept → Canonical REA Instrument → Broker Symbol

Rules:
- Mapping changes require manual governance action (code change + commit).
- Startup must hard-fail on missing or ambiguous mappings.
- Human-facing outputs must disclose proxy context where relevant.
- This module is read-only and execution-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


# -----------------------------
# Data Structures
# -----------------------------
@dataclass(frozen=True)
class InstrumentMapping:
    strategy_concept: str       # e.g., "FX_EURUSD_MR"
    rea_instrument: str         # e.g., "FX.EURUSD.SPOT"
    broker_symbol: str          # e.g., "EUR/USD" or "EURUSD"
    proxy_note: Optional[str] = None


@dataclass(frozen=True)
class ResolutionResult:
    strategy_concept: str
    rea_instrument: str
    broker_symbol: str
    proxy_note: Optional[str]


# -----------------------------
# Governance Mapping Registry
# -----------------------------
# IMPORTANT:
# Keep this list small, explicit, and reviewed.
# Add instruments only via governance commit.
MAPPINGS = [
    InstrumentMapping(
        strategy_concept="FX_EURUSD_MR",
        rea_instrument="FX.EURUSD.SPOT",
        broker_symbol="EUR/USD",
    ),
    InstrumentMapping(
        strategy_concept="FX_GBPUSD_MR",
        rea_instrument="FX.GBPUSD.SPOT",
        broker_symbol="GBP/USD",
    ),
]


def _build_indexes() -> Tuple[Dict[str, InstrumentMapping], Dict[str, InstrumentMapping]]:
    by_strategy: Dict[str, InstrumentMapping] = {}
    by_rea: Dict[str, InstrumentMapping] = {}

    for m in MAPPINGS:
        if m.strategy_concept in by_strategy:
            raise RuntimeError(
                f"Ambiguous mapping: duplicate strategy_concept={m.strategy_concept}"
            )
        if m.rea_instrument in by_rea:
            raise RuntimeError(
                f"Ambiguous mapping: duplicate rea_instrument={m.rea_instrument}"
            )
        by_strategy[m.strategy_concept] = m
        by_rea[m.rea_instrument] = m

    return by_strategy, by_rea


# Build at import-time (startup hard-fail if invalid)
_BY_STRATEGY, _BY_REA = _build_indexes()


# -----------------------------
# Public Resolution APIs
# -----------------------------
def resolve_by_strategy(strategy_concept: str) -> ResolutionResult:
    if strategy_concept not in _BY_STRATEGY:
        raise KeyError(f"Missing mapping for strategy_concept={strategy_concept}")
    m = _BY_STRATEGY[strategy_concept]
    return ResolutionResult(
        strategy_concept=m.strategy_concept,
        rea_instrument=m.rea_instrument,
        broker_symbol=m.broker_symbol,
        proxy_note=m.proxy_note,
    )


def resolve_by_rea(rea_instrument: str) -> ResolutionResult:
    if rea_instrument not in _BY_REA:
        raise KeyError(f"Missing mapping for rea_instrument={rea_instrument}")
    m = _BY_REA[rea_instrument]
    return ResolutionResult(
        strategy_concept=m.strategy_concept,
        rea_instrument=m.rea_instrument,
        broker_symbol=m.broker_symbol,
        proxy_note=m.proxy_note,
    )


def broker_symbol_for_rea(rea_instrument: str) -> str:
    """
    Convenience: used by LiveQuoteRouter mapping dict build.
    Hard-fails if missing.
    """
    return resolve_by_rea(rea_instrument).broker_symbol


if __name__ == "__main__":
    raise RuntimeError(
        "rea_symbol_map is a governance module only; it
