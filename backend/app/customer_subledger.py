"""
customer_subledger.py — placeholder / minimal scaffold

This module exists to be tracked in git.
It provides a minimal, non-breaking API so other modules can safely import it later.

NOTE:
- Keep this lightweight until subledger rules are finalized.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class SubledgerPostResult:
    ok: bool
    message: str
    reference: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None


def post_customer_subledger(
    payload: Dict[str, Any],
    *,
    reference: Optional[str] = None
) -> Dict[str, Any]:
    """
    Minimal stub that acknowledges receipt of a subledger posting payload.
    Safe default: does NOT mutate ledgers here until subledger engine is finalized.
    """
    res = SubledgerPostResult(
        ok=True,
        message="customer subledger stub acknowledged (no-op)",
        reference=reference,
        payload=payload,
    )
    return {
        "ok": res.ok,
        "message": res.message,
        "reference": res.reference,
        "payload": res.payload,
    }
