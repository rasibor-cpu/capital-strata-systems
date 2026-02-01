# backend/app/reporting_store.py
"""
Read-only reporting access to journal data.
GAAP-safe: no mutation, aggregation only.
"""

from backend.app.journal import JOURNAL_STORE


def get_all_journal_entries():
    """
    Returns all journal entries in immutable form.
    """
    return list(JOURNAL_STORE)


def get_journal_entries_for_year(year: int):
    """
    Filters journal entries by posting year.
    """
    results = []
    for entry in JOURNAL_STORE:
        posted_at = entry.get("posted_at")
        if not posted_at:
            continue
        if str(year) == posted_at[:4]:
            results.append(entry)
    return results
