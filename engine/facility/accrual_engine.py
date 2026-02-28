"""
accrual_engine.py
Capital Strata Systems (CSS)

Phase 22C — Daily Accrual Engine (Institutional Grade)

Purpose:
- Calculate daily accrued interest for ACTIVE facilities
- Enforce idempotency (no duplicate accrual per facility per day)
- Post accruals through atomic journal writer
- Be callable by:
    1) EOD batch runner
    2) System startup safety check
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime
from pathlib import Path
import json
import uuid

# --- CONFIG PATHS ---

FACILITY_MASTER_FILE = Path("data/facility_master.json")
ACCRUAL_REGISTRY_FILE = Path("audit/accrual_registry.json")


# --- HELPER FUNCTIONS ---


def _load_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, "r") as f:
        return json.load(f)


def _save_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=4)


def _generate_txn_id() -> str:
    return f"ACCR-{uuid.uuid4().hex[:12].upper()}"


def _round_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# --- CORE ENGINE ---


def run_daily_accrual(posting_date: date | None = None):
    """
    Executes daily interest accrual for all ACTIVE facilities.

    Idempotent:
        Will not post twice for same facility on same date.
    """

    if posting_date is None:
        posting_date = date.today()

    facilities = _load_json(FACILITY_MASTER_FILE, [])
    accrual_registry = _load_json(ACCRUAL_REGISTRY_FILE, {})

    total_accrued = Decimal("0.00")
    postings_executed = 0

    for facility in facilities:

        if facility.get("status") != "ACTIVE":
            continue

        facility_id = facility["facility_id"]
        principal = Decimal(str(facility["outstanding_principal"]))
        annual_rate = Decimal(str(facility["interest_rate"]))

        # --- Idempotency Check ---
        facility_registry = accrual_registry.get(facility_id, [])

        if str(posting_date) in facility_registry:
            continue

        # --- Daily Interest Calculation ---
        daily_rate = annual_rate / Decimal("100") / Decimal("365")
        daily_interest = _round_money(principal * daily_rate)

        if daily_interest == Decimal("0.00"):
            continue

        # --- Create Journal Payload ---
        txn_id = _generate_txn_id()

        journal_payload = {
            "transaction_id": txn_id,
            "transaction_date": str(posting_date),
            "value_date": str(posting_date),
            "description": f"Daily Interest Accrual - Facility {facility_id}",
            "currency": facility.get("currency", "USD"),
            "entries": [
                {
                    "account_id": "INTEREST_EXPENSE",
                    "debit": str(daily_interest),
                    "credit": "0.00",
                },
                {
                    "account_id": "ACCRUED_INTEREST_PAYABLE",
                    "debit": "0.00",
                    "credit": str(daily_interest),
                },
            ],
        }

        # --- Atomic Journal Hook ---
        from engine.ledger.atomic_journal_writer import post_journal

        post_journal(journal_payload)

        # --- Update Registry ---
        facility_registry.append(str(posting_date))
        accrual_registry[facility_id] = facility_registry

        total_accrued += daily_interest
        postings_executed += 1

    _save_json(ACCRUAL_REGISTRY_FILE, accrual_registry)

    return {
        "posting_date": str(posting_date),
        "facilities_processed": len(facilities),
        "accruals_posted": postings_executed,
        "total_interest_accrued": str(_round_money(total_accrued)),
    }


# --- STARTUP SAFETY CHECK ---


def startup_accrual_check():
    """
    Ensures accrual for today has been run.
    Safe to call on system startup.
    """

    today = date.today()
    result = run_daily_accrual(today)
    return result