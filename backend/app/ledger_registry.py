"""
Ledger Registry – Capital Strata Systems (CSS)
---------------------------------------------

Purpose:
- Provide a stable API surface for ledger/balance lookups used by limits & reporting.
- Preserve import contracts expected by other modules (e.g., credit_limits.py).
- Wire to the institutional ledger module (LedgerStore + LedgerEngine) with a single
  system-wide instance to guarantee real-time consolidated balances.

Fail-closed behavior (default):
- If balances cannot be resolved safely, return {} (callers must BLOCK/downgrade).

Notes on "currency balances":
- Your institutional ledger store tracks balances per ACCOUNT (account_id -> Decimal).
- Some legacy callers expect balances by currency (e.g., {"USD": 1000.0}).
- We support that via:
    (A) Explicit env override: REA_LEDGER_BALANCES_JSON='{"USD": 1000, "NGN": 250000}'
    (B) Heuristic currency inference from account_id (e.g., "EQUITY:USD", "CASH_USD")
    (C) Optional explicit mapping: REA_LEDGER_ACCOUNT_CCY_MAP_JSON='{"EQUITY:MAIN":"USD"}'

You also get new helpers:
- get_all_account_balances(): Dict[str, float]
- get_ledger_store(), get_ledger_engine() accessors
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple
import os
import json

# IMPORTANT:
# This file lives inside the "app" package, so we use RELATIVE imports.
# This removes PYTHONPATH/root ambiguity and prevents "No module named app.*" errors.
from .ledger.ledger_store import LedgerStore
from .ledger.ledger_engine import LedgerEngine


# ==========================================================
# DATA CONTAINERS
# ==========================================================

@dataclass(frozen=True)
class BalanceSnapshot:
    """
    Minimal balance snapshot container.

    balances: mapping like {"USD": 1000.0, "NGN": 250000.0}
    meta: optional metadata (timestamp, source, run_id, etc.)
    """
    balances: Dict[str, float]
    meta: Dict[str, Any]


# ==========================================================
# SINGLETONS (SYSTEM-WIDE)
# ==========================================================

# IMPORTANT: These must be singletons to prevent ledger fragmentation.
# Do NOT instantiate LedgerStore/LedgerEngine elsewhere.
_LEDGER_STORE: Optional[LedgerStore] = None
_LEDGER_ENGINE: Optional[LedgerEngine] = None


def get_ledger_store() -> LedgerStore:
    global _LEDGER_STORE
    if _LEDGER_STORE is None:
        _LEDGER_STORE = LedgerStore()
    return _LEDGER_STORE


def get_ledger_engine() -> LedgerEngine:
    global _LEDGER_ENGINE
    if _LEDGER_ENGINE is None:
        _LEDGER_ENGINE = LedgerEngine(get_ledger_store())
    return _LEDGER_ENGINE


# ==========================================================
# HELPERS
# ==========================================================

def _safe_float(x: Any) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


def _load_json_env(var_name: str) -> Optional[Any]:
    raw = os.getenv(var_name, "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def _infer_currency_from_account_id(account_id: str) -> Optional[str]:
    """
    Heuristic inference:
    - "EQUITY:USD" -> USD
    - "CASH_USD" -> USD
    - "GL-USD-1000" -> USD (limited)
    """
    s = (account_id or "").strip()
    if not s:
        return None

    for delim in (":", "_", "-", "/"):
        parts = [p for p in s.split(delim) if p]
        if parts:
            tail = parts[-1].upper().strip()
            if len(tail) == 3 and tail.isalpha():
                return tail

    return None


def _account_currency_mapping() -> Dict[str, str]:
    """
    Optional explicit mapping:
    REA_LEDGER_ACCOUNT_CCY_MAP_JSON='{"EQUITY:MAIN":"USD","CUST:123":"NGN"}'
    """
    obj = _load_json_env("REA_LEDGER_ACCOUNT_CCY_MAP_JSON")
    if isinstance(obj, dict):
        out: Dict[str, str] = {}
        for k, v in obj.items():
            kk = str(k).strip()
            vv = str(v).strip().upper()
            if kk and vv:
                out[kk] = vv
        return out
    return {}


def _aggregate_currency_balances_from_accounts(
    account_balances: Dict[str, float],
) -> Tuple[Dict[str, float], Dict[str, Any]]:
    """
    Convert account balances -> currency balances using mapping/inference.

    Returns:
      (currency_balances, meta)
    """
    ccy_map = _account_currency_mapping()
    currency_balances: Dict[str, float] = {}
    unresolved: int = 0

    for acct, bal in account_balances.items():
        ccy = ccy_map.get(acct) or _infer_currency_from_account_id(acct)
        if not ccy:
            unresolved += 1
            continue
        currency_balances[ccy] = currency_balances.get(ccy, 0.0) + float(bal)

    meta = {
        "source": "ledger_engine_account_aggregation",
        "unresolved_accounts": unresolved,
        "mapped_accounts": len(account_balances) - unresolved,
        "total_accounts": len(account_balances),
    }
    return currency_balances, meta


# ==========================================================
# PUBLIC API (BACKWARD COMPATIBLE)
# ==========================================================

def get_all_balances(*, fail_closed: bool = True) -> Dict[str, float]:
    """
    Backward compatible API: returns balances by currency.

    Priority order:
    1) Explicit override env: REA_LEDGER_BALANCES_JSON (legacy, safe, simple)
    2) Aggregate from institutional ledger accounts (mapping/inference)
    3) Fail-closed => {}
    """
    # (1) Legacy explicit override
    obj = _load_json_env("REA_LEDGER_BALANCES_JSON")
    if isinstance(obj, dict):
        out: Dict[str, float] = {}
        for k, v in obj.items():
            f = _safe_float(v)
            if f is not None:
                out[str(k).strip().upper()] = f
        return out

    # (2) Institutional ledger aggregation (account -> currency)
    try:
        engine = get_ledger_engine()
        acct_decimals = engine.get_all_balances()  # account_id -> Decimal

        acct_balances: Dict[str, float] = {}
        for acct, dec in acct_decimals.items():
            acct_balances[acct] = float(dec)

        currency_balances, _meta = _aggregate_currency_balances_from_accounts(acct_balances)

        if not currency_balances and fail_closed:
            return {}

        return currency_balances

    except Exception:
        return {} if fail_closed else {}


def get_balance(currency: str, *, fail_closed: bool = True) -> Optional[float]:
    """
    Convenience getter for a single currency.
    Returns None if missing.
    """
    c = (currency or "").strip().upper()
    if not c:
        return None
    return get_all_balances(fail_closed=fail_closed).get(c)


# ==========================================================
# NEW (INSTITUTIONAL) API SURFACES
# ==========================================================

def get_all_account_balances(*, fail_closed: bool = True) -> Dict[str, float]:
    """
    Returns account-level balances (account_id -> float).
    This is the institutional-native surface.
    """
    try:
        acct_decimals = get_ledger_engine().get_all_balances()
        return {acct: float(dec) for acct, dec in acct_decimals.items()}
    except Exception:
        return {} if fail_closed else {}