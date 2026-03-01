"""
backend/app/ledger/dormancy_engine.py
Capital Strata Systems (CSS)

Phase 23D.4 — Automatic Dormancy Engine (EOD Callable)

Purpose:
- Automatically flag CUSTOMER accounts as DORMANT
  after inactivity threshold (default: 90 days)

Rules:
- Applies ONLY to category == "CUSTOMER"
- If status already DORMANT → skip (idempotent)
- If no last_customer_activity_date → use created_date
- Writes lifecycle event to account_events.jsonl
- Fail-closed on invalid date formats

Callable from EOD batch.
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any


RUNTIME_REGISTRY_FILE = Path("backend/app/ledger/account_registry.json")
ACCOUNT_EVENTS_FILE = Path("audit_logs/account_events.jsonl")


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def _utc_ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_registry() -> Dict[str, Any]:
    if not RUNTIME_REGISTRY_FILE.exists():
        return {}
    txt = RUNTIME_REGISTRY_FILE.read_text(encoding="utf-8").strip()
    if not txt:
        return {}
    return json.loads(txt)


def _save_registry(reg: Dict[str, Any]) -> None:
    RUNTIME_REGISTRY_FILE.write_text(
        json.dumps(reg, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def _append_event(event: Dict[str, Any]) -> None:
    ACCOUNT_EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    record = dict(event)
    record["event_id"] = f"EVT-{datetime.utcnow().timestamp()}"
    record["ts_utc"] = _utc_ts()

    with ACCOUNT_EVENTS_FILE.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _parse_date_ymd(s: str) -> datetime:
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except Exception:
        raise ValueError(f"Invalid date format (expected YYYY-MM-DD): {s}")


# ------------------------------------------------------------
# Public API
# ------------------------------------------------------------

def run_dormancy_scan(*, threshold_days: int = 90) -> Dict[str, Any]:
    """
    Executes dormancy scan across CUSTOMER accounts.

    Returns:
        {
            "accounts_scanned": int,
            "accounts_dormant_set": int,
            "threshold_days": int
        }
    """

    reg = _load_registry()

    if not isinstance(reg, dict):
        raise ValueError("account_registry.json invalid structure")

    accounts_scanned = 0
    accounts_dormant_set = 0
    today = datetime.utcnow()

    for account_no, meta in reg.items():

        if not isinstance(meta, dict):
            continue

        if str(meta.get("category", "")).upper() != "CUSTOMER":
            continue

        accounts_scanned += 1

        current_status = str(meta.get("status", "ACTIVE")).upper()
        if current_status == "DORMANT":
            continue  # idempotent

        last_activity = meta.get("last_customer_activity_date")
        created_date = meta.get("created_date")

        base_date_str = last_activity or created_date
        if not base_date_str:
            # fail-closed
            raise ValueError(
                f"Customer account {account_no} missing created_date and activity date"
            )

        base_date = _parse_date_ymd(base_date_str)
        inactivity_days = (today - base_date).days

        if inactivity_days >= threshold_days:
            meta["status"] = "DORMANT"
            accounts_dormant_set += 1

            _append_event({
                "event_type": "ACCOUNT_DORMANT_SET",
                "account_no": account_no,
                "prior_status": current_status,
                "new_status": "DORMANT",
                "inactivity_days": inactivity_days,
                "threshold_days": threshold_days,
                "reason": "INACTIVITY_THRESHOLD"
            })

    _save_registry(reg)

    return {
        "accounts_scanned": accounts_scanned,
        "accounts_dormant_set": accounts_dormant_set,
        "threshold_days": threshold_days
    }