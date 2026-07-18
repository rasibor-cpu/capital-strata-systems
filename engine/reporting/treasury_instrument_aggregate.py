"""Treasury instrument aggregate producer (Phase 176 fail-closed stub).

The FinCon report_printer registry references this module. A full treasury book
does not yet exist in CSS, so generation refuses rather than synthesizing
positions. Restores importability of ``engine.reporting.report_printer``.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def generate_treasury_instrument_aggregate(
    *,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    as_of_date: Optional[str] = None,
    sections: Optional[list] = None,
    filters: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> str:
    """Refuse generation — treasury instrument books are not yet implemented."""
    _ = (from_date, to_date, as_of_date, sections, filters, kwargs)
    return (
        "=== TREASURY INSTRUMENT AGGREGATE ===\n"
        "STATUS: DATA_UNAVAILABLE\n"
        "REASON: treasury instrument books are not implemented in CSS.\n"
        "CLASSIFICATION: COMING_SOON / FUTURE_CAPABILITY\n"
        "Do not treat this output as an official treasury statement.\n"
    )


__all__ = ["generate_treasury_instrument_aggregate"]
