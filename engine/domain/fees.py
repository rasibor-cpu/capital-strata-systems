from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class FeeSchedule:
    """
    Authorized fee and tax configuration.
    Versioned and time-effective for audit traceability.
    """

    # Identity
    fee_schedule_id: str
    version: str

    # Effectivity
    effective_from: datetime
    effective_to: Optional[datetime] = None

    # Rates (percentage-based)
    commission_rate_pct: float = 0.0  # e.g. 0.10 = 0.10%
    tax_rate_pct: float = 0.0          # e.g. VAT / transaction tax

    # Scope (optional narrowing)
    scope_company_id: Optional[str] = None
    scope_branch_id: Optional[str] = None
    scope_department_id: Optional[str] = None

    # Governance
    approved_by_user_id: Optional[str] = None
    approved_at: Optional[datetime] = None
    notes: Optional[str] = None