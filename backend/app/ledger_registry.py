"""
Ledger Registry – REA Capital Trading Engine
--------------------------------------------

Purpose:
- Provide a stable API surface for ledger/balance lookups used by limits & reporting.
- Fix import contracts expected by other modules (credit_limits.py).

Phase-1 approach:
- Implement get_all_balances() with fail-closed behavior:
    - If no ledger backend is configured/available, return {}.
- Provide optional hooks to integrate with your existing ledger/reporting store later.

This avoids server-start crashes while preserving safety (no fake balances).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Optional
import os


@dataclass(frozen=True)
class BalanceSnapshot:
    """
    A minimal balance snapshot container.

    balances: mapping like {"USD": 1000.0, "NGN": 250000.0}
    meta: optional metadata (timestamp, source, run_id, etc.)
    """
    balances: Dict[str, float]
    meta: Dict[str, Any]


def _safe_float(x: Any) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


def get_all_balances(*, fail_closed: bool = True) -> Dict[str, float]:
    """
    Return a dict of all known balances by currency.

    Phase-1 default:
    - If no backend exists, return {}.
    - Returning {} is fail-closed because callers should BLOCK or downgrade
      when balances are missing (no risk scaling on unknown equity).

    If fail_closed=False, still returns {} (we do NOT invent balances).
    """
    # Optional future env-based wiring (kept non-breaking):
    # Example: REA_LEDGER_BALANCES_JSON='{"USD": 1000, "NGN": 250000}'
    raw = os.getenv("REA_LEDGER_BALANCES_JSON", "").strip()
    if raw:
        # minimal JSON parse without adding hard dependencies
        try:
            import json  # stdlib
            obj = json.loads(raw)
            if isinstance(obj, dict):
                out: Dict[str, float] = {}
                for k, v in obj.items():
                    f = _safe_float(v)
                    if f is not None:
                        out[str(k).strip().upper()] = f
                return out
        except Exception:
            # fail closed => fall through to {}
            pass

    return {}


def get_balance(currency: str, *, fail_closed: bool = True) -> Optional[float]:
    """
    Convenience getter for a single currency.
    Returns None if missing.
    """
    c = (currency or "").strip().upper()
    if not c:
        return None
    return get_all_balances(fail_closed=fail_closed).get(c)
