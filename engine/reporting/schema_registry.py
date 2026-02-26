"""
Schema Registry – Reporting Integrity Layer
Capital Strata Systems

Purpose:
- Maintain deterministic schema version mapping
- Support integrity hashing reproducibility
- Fail closed on unknown schemas
"""

from __future__ import annotations


# ============================================================
# Canonical Schema Registry
# ============================================================

SCHEMA_VERSIONS = {
    # Core Financial Reports
    "gl_print": "v1",
    "gl_as_of": "v1",
    "customer_subledger": "v1",
    "treasury_instrument_aggregate": "v1",

    # Supervisory / Control
    "supervisory_control_pack": "v1",

    # Meta
    "list_available_reports": "v1",
}


# ============================================================
# Public API
# ============================================================

def get_schema_version(schema_name: str) -> str:
    """
    Returns schema version for deterministic integrity hashing.
    Fails closed if schema not registered.
    """

    if schema_name not in SCHEMA_VERSIONS:
        raise ValueError(f"Unknown schema: {schema_name}")

    return SCHEMA_VERSIONS[schema_name]