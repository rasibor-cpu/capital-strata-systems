"""
Customer Subledger – REA Capital Trading Engine
-----------------------------------------------

Purpose:
- Provide customer/account lookup APIs expected by credit_limits.py and other modules.
- Maintain fail-closed behavior: if no data is available, return empty structures
  so upstream risk/credit gates can BLOCK safely.

Phase-1:
- get_customer_accounts(): returns dict keyed by customer/account id.
- Optional env-based JSON injection for quick dev tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Optional
import os


@dataclass(frozen=True)
class CustomerAccount:
    account_id: str
    customer_name: str
    meta: Dict[str, Any]


def _safe_str(x: Any) -> str:
    try:
        return str(x)
    except Exception:
        return ""


def get_customer_accounts(*, fail_closed: bool = True) -> Dict[str, Dict[str, Any]]:
    """
    Return customer accounts mapping.

    Output example:
    {
      "ACC001": {"customer_name": "Robert", "status": "ACTIVE"},
      "ACC002": {"customer_name": "Test", "status": "ACTIVE"}
    }

    Phase-1 default:
    - Return {} when not configured.
    - Never fabricate accounts.

    Optional env override:
    - REA_CUSTOMER_ACCOUNTS_JSON='{"ACC001":{"customer_name":"Robert","status":"ACTIVE"}}'
    """
    raw = os.getenv("REA_CUSTOMER_ACCOUNTS_JSON", "").strip()
    if raw:
        try:
            import json  # stdlib
            obj = json.loads(raw)
            if isinstance(obj, dict):
                out: Dict[str, Dict[str, Any]] = {}
                for k, v in obj.items():
                    if not isinstance(v, dict):
                        continue
                    out[_safe_str(k).strip()] = dict(v)
                return out
        except Exception:
            # fail-closed => ignore and fall through
            pass

    return {}


def get_customer_account(account_id: str, *, fail_closed: bool = True) -> Optional[Dict[str, Any]]:
    """
    Convenience getter for a single account.
    """
    aid = (account_id or "").strip()
    if not aid:
        return None
    return get_customer_accounts(fail_closed=fail_closed).get(aid)
