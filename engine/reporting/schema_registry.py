"""
engine/reporting/schema_registry.py

Schema Registry – Phase 17+
Capital Strata Systems

Purpose:
- Canonical registry of report schema versions
- Used by integrity hashing + auditor reproducibility
- Fail-closed on unknown schema
"""

from __future__ import annotations

from typing import Dict


# ------------------------------------------------------------
# Schema versions (authoritative)
# ------------------------------------------------------------
# NOTE:
# - Keys must match report_name values used by report_center / report_printer
# - Versions must only change when report structure/output contract changes
# ------------------------------------------------------------

SCHEMA_VERSIONS: Dict[str, str] = {
    # Core reporting
    "trial_balance": "v1",

    # GL (when wired)
    "gl_print": "v1",
    "gl_as_of": "v1",

    # Subledgers / AR
    "customer_subledger": "v1",
    "ar_ageing": "v1",

    # Controls / packs
    "supervisory_control_pack": "v1",
    "supervisor_signoff": "v1",

    # Treasury / PnL
    "treasury_instrument_aggregate": "v1",
    "pnl_report": "v1",

    # EOD snapshots (institutional option C)
    "eod_universe_snapshot": "v1",
}


def get_schema_version(schema_name: str) -> str:
    name = (schema_name or "").strip()
    if not name:
        raise ValueError("Unknown schema: (empty)")

    v = SCHEMA_VERSIONS.get(name)
    if not v:
        raise ValueError(f"Unknown schema: {name}")
    return v


def list_schemas() -> Dict[str, str]:
    return dict(sorted(SCHEMA_VERSIONS.items(), key=lambda kv: kv[0]))