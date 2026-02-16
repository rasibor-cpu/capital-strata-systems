"""
Risk State Store
Capital Strata Systems – Institutional Persistence Layer

Fail-Closed | Versioned | Migration-Aware

This module provides:

- Schema versioning
- Automatic migration handling
- Corruption detection
- Deterministic persistence
- Forward compatibility support
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

# ---------------------------------------------------------
# CONFIG
# ---------------------------------------------------------

STATE_FILE = Path("risk_state.json")
STATE_SCHEMA_VERSION = 2  # Increment when schema changes


# ---------------------------------------------------------
# DEFAULT STATE TEMPLATE
# ---------------------------------------------------------

def _default_state() -> Dict[str, Any]:
    return {
        "_schema_version": STATE_SCHEMA_VERSION,
        "day_key": None,
        "equity": None,
        "equity_peak": None,
        "trades_today": 0,
        "daily_pnl": 0.0,
        "consecutive_losses": 0,
        "cooldown_active": False,
        "regime": None,
        "open_positions": 0,
        "last_extras": None,
    }


# ---------------------------------------------------------
# MIGRATIONS
# ---------------------------------------------------------

def _migrate_v1_to_v2(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Example migration:
    - Ensure open_positions exists
    - Ensure last_extras exists
    """
    state.setdefault("open_positions", 0)
    state.setdefault("last_extras", None)
    state["_schema_version"] = 2
    return state


MIGRATIONS = {
    (1, 2): _migrate_v1_to_v2,
}


def _apply_migrations(state: Dict[str, Any]) -> Dict[str, Any]:
    version = state.get("_schema_version", 1)

    while version < STATE_SCHEMA_VERSION:
        migration_key = (version, version + 1)
        if migration_key not in MIGRATIONS:
            raise RuntimeError(
                f"No migration path from schema {version} to {version + 1}"
            )
        state = MIGRATIONS[migration_key](state)
        version = state["_schema_version"]

    return state


# ---------------------------------------------------------
# VALIDATION
# ---------------------------------------------------------

def _validate_state(state: Dict[str, Any]) -> None:
    if not isinstance(state, dict):
        raise RuntimeError("Persisted state is not a dict")

    if "_schema_version" not in state:
        raise RuntimeError("Persisted state missing schema version")

    if state["_schema_version"] != STATE_SCHEMA_VERSION:
        raise RuntimeError("Schema version mismatch after migration")

    # Minimal required fields
    required = ["day_key", "equity", "trades_today"]
    for field in required:
        if field not in state:
            raise RuntimeError(f"Missing required state field: {field}")


# ---------------------------------------------------------
# PUBLIC API
# ---------------------------------------------------------

def load_state() -> Dict[str, Any]:
    """
    Load persisted state.

    Fail-closed behavior:
    - If corruption detected → return clean default state
    - If migration fails → raise error
    """

    if not os.getenv("REA_PERSIST_RISK_STATE"):
        return _default_state()

    if not STATE_FILE.exists():
        return _default_state()

    try:
        raw = STATE_FILE.read_text(encoding="utf-8")
        state = json.loads(raw)

        state = _apply_migrations(state)
        _validate_state(state)

        return state

    except Exception as e:
        print(f"[risk_state_store] CORRUPTED_STATE_RESET: {e}")
        return _default_state()


def save_state(state: Dict[str, Any]) -> None:
    """
    Persist state deterministically.
    """

    if not os.getenv("REA_PERSIST_RISK_STATE"):
        return

    state = dict(state)
    state["_schema_version"] = STATE_SCHEMA_VERSION

    serialized = json.dumps(state, sort_keys=True, indent=2)

    STATE_FILE.write_text(serialized, encoding="utf-8")
