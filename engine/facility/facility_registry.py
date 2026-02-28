"""
Capital Strata Systems
Facility Registry – Phase 22A (Term Loans Baseline)

Purpose:
- Authoritative registry for approved loan facilities
- Stores facility terms + ownership (department/RM) for ageing & regulatory reporting
- Tracks delinquency state (days past due) and classification buckets
- Persistence: JSON store (DB-ready later)

Note:
- Classification is facility metadata (not separate GL accounts).
- Provisioning / write-off postings map to COA accounts already expanded in BANK COA v2.0.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Optional, List


STORE_FILE = Path("state/facilities/facility_registry.json")


# -----------------------------
# Regulatory-ish classification buckets (generic)
# -----------------------------
def classify_by_dpd(days_past_due: int) -> str:
    if days_past_due <= 30:
        return "PERFORMING"
    if days_past_due <= 90:
        return "WATCHLIST"
    if days_past_due <= 180:
        return "SUBSTANDARD"
    if days_past_due <= 365:
        return "DOUBTFUL"
    return "LOSS"


def _today() -> date:
    return datetime.utcnow().date()


def _parse_iso(d: str) -> date:
    return datetime.fromisoformat(str(d)[:10]).date()


def _ensure_store() -> None:
    STORE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not STORE_FILE.exists():
        STORE_FILE.write_text(json.dumps({"facilities": {}}, indent=2), encoding="utf-8")


@dataclass
class TermLoanFacility:
    facility_id: str
    customer_id: str
    department_id: str
    relationship_manager: str

    principal: float
    annual_interest_rate: float  # e.g. 0.24 for 24%
    day_count: str  # ACT/365 baseline
    tenor_months: int
    repayment_frequency: str  # MONTHLY baseline

    start_date: str  # YYYY-MM-DD
    maturity_date: str  # YYYY-MM-DD

    status: str = "ACTIVE"  # ACTIVE | CLOSED | WRITTEN_OFF
    outstanding_principal: float = 0.0

    # Delinquency state
    last_paid_date: Optional[str] = None
    next_due_date: Optional[str] = None
    days_past_due: int = 0
    classification: str = "PERFORMING"

    created_at: str = ""
    updated_at: str = ""


class FacilityRegistry:
    def __init__(self) -> None:
        _ensure_store()
        self._data = json.loads(STORE_FILE.read_text(encoding="utf-8"))

    def _save(self) -> None:
        STORE_FILE.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def list_ids(self) -> List[str]:
        return sorted((self._data.get("facilities") or {}).keys())

    def get(self, facility_id: str) -> Optional[TermLoanFacility]:
        raw = (self._data.get("facilities") or {}).get(facility_id)
        if not raw:
            return None
        return TermLoanFacility(**raw)

    def create_term_loan(
        self,
        *,
        customer_id: str,
        department_id: str,
        relationship_manager: str,
        principal: float,
        annual_interest_rate: float,
        tenor_months: int,
        start_date: str,
        maturity_date: str,
        day_count: str = "ACT/365",
        repayment_frequency: str = "MONTHLY",
    ) -> TermLoanFacility:

        fid = f"FAC-{uuid.uuid4().hex.upper()}"
        now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        fac = TermLoanFacility(
            facility_id=fid,
            customer_id=str(customer_id).strip(),
            department_id=str(department_id).strip().upper(),
            relationship_manager=str(relationship_manager).strip().upper(),
            principal=float(principal),
            annual_interest_rate=float(annual_interest_rate),
            day_count=str(day_count).strip().upper(),
            tenor_months=int(tenor_months),
            repayment_frequency=str(repayment_frequency).strip().upper(),
            start_date=str(start_date),
            maturity_date=str(maturity_date),
            outstanding_principal=float(principal),
            created_at=now,
            updated_at=now,
        )

        self._data["facilities"][fid] = asdict(fac)
        self._save()
        return fac

    def update_delinquency(
        self,
        facility_id: str,
        *,
        as_of_date: Optional[str] = None,
        next_due_date: Optional[str] = None,
        last_paid_date: Optional[str] = None,
    ) -> TermLoanFacility:

        fac = self.get(facility_id)
        if not fac:
            raise KeyError(f"Facility not found: {facility_id}")

        ref_date = _parse_iso(as_of_date) if as_of_date else _today()

        if next_due_date is not None:
            fac.next_due_date = str(next_due_date)
        if last_paid_date is not None:
            fac.last_paid_date = str(last_paid_date)

        # Compute DPD if we have a due date
        dpd = 0
        if fac.next_due_date:
            due = _parse_iso(fac.next_due_date)
            if ref_date > due:
                dpd = (ref_date - due).days

        fac.days_past_due = int(dpd)
        fac.classification = classify_by_dpd(fac.days_past_due)
        fac.updated_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        self._data["facilities"][facility_id] = asdict(fac)
        self._save()
        return fac