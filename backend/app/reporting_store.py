# backend/app/reporting_store.py
"""
GAAP-safe read-only reporting access.

Authoritative source:
- Immutable journal lives in ledger_registry (server process / module state).
- reporting_store exposes stable accessors for reporting engines
  (trial balance, financial statements, exposure, etc.)

NO MUTATION in this module.
"""

from typing import List, Dict, Any


def _get_journal_source() -> List[Dict[str, Any]]:
    """
    Returns the authoritative journal entries list.
    """
    # Ledger registry is the single source of truth for journal entries.
    from backend.app.ledger_registry import get_full_journal  # type: ignore
    return get_full_journal()


def get_all_journal_entries() -> List[Dict[str, Any]]:
    """
    Returns all journal entries (immutable view).
    """
    return list(_get_journal_source())


def get_journal_entries_for_year(year: int) -> List[Dict[str, Any]]:
    """
    Filters journal entries by posting year.
    """
    y = str(year)
    out: List[Dict[str, Any]] = []
    for e in _get_journal_source():
        posted_at = str(e.get("posted_at", ""))
        if posted_at.startswith(y):
            out.append(e)
    return out
