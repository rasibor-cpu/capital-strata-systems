"""
backend/app/security/unit_router.py

Unit routing: unit_code -> UnitBundle (label + allowed modules/screens)

Rules:
- unit_code is required for non-superusers
- Unknown unit_code must fail-closed
- Bundles should be conservative (least privilege) and expanded by governance later
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict


@dataclass(frozen=True)
class UnitBundle:
    unit_code: str
    label: str
    modules: List[str]


# Canonical unit bundles (expand over time)
UNIT_BUNDLES: Dict[str, UnitBundle] = {
    # Core Ops / Admin
    "OPS": UnitBundle("OPS", "Operations", modules=[
        "ops.*",
        "reporting.*",
        "security.*",
        "health.*",
    ]),
    "ADMIN": UnitBundle("ADMIN", "Administration", modules=[
        "ops.*",
        "reporting.*",
        "security.*",
        "health.*",
    ]),

    # Trading desk / execution
    "TRADING": UnitBundle("TRADING", "Trading Desk", modules=[
        "engine.*",
        "execution.*",
        "risk.*",
        "data_live.*",
        "reporting.trades*",
        "reporting.positions*",
        "health.*",
    ]),

    # Risk & controls
    "RISK": UnitBundle("RISK", "Risk Control", modules=[
        "risk.*",
        "engine.*",
        "reporting.*",
        "ops.pre_live_check*",
        "health.*",
    ]),

    # Finance / ledger / reconciliation
    "FIN": UnitBundle("FIN", "Finance & Control", modules=[
        "ledger.*",
        "reporting.financials*",
        "reporting.*",
        "ops.*",
        "health.*",
    ]),
}


def resolve_unit_bundle(unit_code: str) -> UnitBundle:
    if not unit_code:
        raise ValueError("unit_code required")
    uc = unit_code.strip().upper()
    if uc not in UNIT_BUNDLES:
        raise ValueError(f"Unknown unit_code: {uc}")
    return UNIT_BUNDLES[uc]
