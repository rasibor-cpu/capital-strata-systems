"""
backend/app/security/unit_router.py

Maps a user's unit_code (department/function) to a stable set of allowed modules.
This drives "screen/function auto-load" for CLI now and UI later.

Design:
- unit_code is a short stable code (e.g., RISK, OPS, FINCTRL, TRADING_DESK)
- a "module" is a named capability bundle (e.g., "positions.view", "limits.manage")
- deterministic + version-controlled in code
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class UnitBundle:
    unit_code: str
    label: str
    modules: List[str]  # "screens/functions" allowlist


# Canonical bundles (extend carefully; treat names as API)
BUNDLES: Dict[str, UnitBundle] = {
    # Trading desk: view signals, request orders (execution still governed), monitor positions
    "TRADING_DESK": UnitBundle(
        unit_code="TRADING_DESK",
        label="Trading Desk",
        modules=[
            "dashboard.view",
            "signals.view",
            "marketdata.view",
            "positions.view",
            "orders.request",
            "execution.status.view",
            "reports.daily.view",
        ],
    ),
    # Risk: manage limits, approve overrides, view exposures
    "RISK": UnitBundle(
        unit_code="RISK",
        label="Risk Management",
        modules=[
            "dashboard.view",
            "limits.view",
            "limits.manage",
            "exposure.view",
            "override.approve",
            "reports.risk.view",
            "audit.view",
        ],
    ),
    # Ops: session tools, notifications, runbooks
    "OPS": UnitBundle(
        unit_code="OPS",
        label="Operations",
        modules=[
            "dashboard.view",
            "session.view",
            "session.manage",
            "notify.manage",
            "outbox.view",
            "reports.ops.view",
            "audit.view",
        ],
    ),
    # Financial control: ledgers, postings, statements
    "FINCTRL": UnitBundle(
        unit_code="FINCTRL",
        label="Financial Control",
        modules=[
            "dashboard.view",
            "ledger.view",
            "ledger.post",
            "trialbalance.view",
            "statements.view",
            "reports.finance.view",
            "audit.view",
        ],
    ),
    # Compliance: audit + policy reports
    "COMPLIANCE": UnitBundle(
        unit_code="COMPLIANCE",
        label="Compliance",
        modules=[
            "dashboard.view",
            "audit.view",
            "policy.view",
            "reports.compliance.view",
        ],
    ),
}


def resolve_unit_bundle(unit_code: str) -> UnitBundle:
    code = (unit_code or "").strip().upper()
    if not code:
        raise ValueError("unit_code is required")
    if code not in BUNDLES:
        raise ValueError(f"Unknown unit_code: {code}")
    return BUNDLES[code]


def list_unit_codes() -> List[str]:
    return sorted(BUNDLES.keys())
