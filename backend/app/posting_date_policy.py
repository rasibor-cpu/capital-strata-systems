"""
backend/app/posting_date_policy.py

Posting Date & Value Date Governance (CSS)
------------------------------------------

Purpose
- Enforce posting-date integrity: valid transaction_date + controlled value_date behavior.
- Block invalid/future dates (unless explicitly allowed).
- Back-valued value_date (< transaction_date) requires an override by sufficient authority.
- Override attempts and outcomes are logged immutably (append-only JSONL) for audit.
- Designed to be called from posting_approval / posting runtime flows.

Key design choices
- Fail-closed on unknown authority bands.
- Always log override decisions (including forced rejections due to insufficient authority).
- Persistence-agnostic: file-backed JSONL log that can later be swapped for DB.

File created/updated by governance-first workflow in Phase 16.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import json
import uuid


# -----------------------------
# Utilities
# -----------------------------

def utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def ensure_date(value: Any, field_name: str) -> date:
    """
    Accepts:
      - datetime.date
      - datetime.datetime
      - ISO string 'YYYY-MM-DD'
    Returns: date
    """
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return datetime.strptime(value.strip(), "%Y-%m-%d").date()
        except ValueError as e:
            raise ValueError(f"{field_name} must be YYYY-MM-DD (got '{value}')") from e
    raise TypeError(f"{field_name} must be date/datetime/ISO string (got {type(value).__name__})")


def jsonl_append(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


# -----------------------------
# Authority Model (lightweight)
# -----------------------------

# Increasing authority from left to right.
AUTH_BANDS = ["AUTO", "L1", "L2", "ADMIN", "SUPER"]


def band_index(band: str) -> int:
    if band not in AUTH_BANDS:
        # Fail-closed: unknown treated as lowest
        return 0
    return AUTH_BANDS.index(band)


# -----------------------------
# Data Structures
# -----------------------------

@dataclass(frozen=True)
class DateOverrideRequest:
    request_id: str
    created_utc: str
    requester_user_id: str
    transaction_date: str
    value_date: str
    reason: str
    context: Dict[str, Any]


@dataclass(frozen=True)
class DateOverrideDecision:
    decision_utc: str
    approver_user_id: str
    approver_band: str
    outcome: str  # "APPROVED" | "REJECTED"
    decision_reason: str


@dataclass(frozen=True)
class DateOverrideLogEntry:
    event_type: str  # "POSTING_DATE_OVERRIDE"
    request: Dict[str, Any]
    decision: Dict[str, Any]


# -----------------------------
# Policy + Engine
# -----------------------------

class PostingDatePolicy:
    """
    Small explicit policy container.
    Policy changes should be governance-controlled.
    """

    def __init__(
        self,
        allow_future_transaction_dates: bool = False,
        enforce_financial_year_bounds: bool = False,
        min_override_band_for_back_valuation: str = "L1",
        override_log_path: str = "audit/override_logs/posting_date_overrides.jsonl",
    ):
        self.allow_future_transaction_dates = bool(allow_future_transaction_dates)
        self.enforce_financial_year_bounds = bool(enforce_financial_year_bounds)
        self.min_override_band_for_back_valuation = min_override_band_for_back_valuation
        self.override_log_path = Path(override_log_path)


class PostingDateGovernor:
    """
    Enforces posting date + value date rules and logs overrides.
    """

    def __init__(
        self,
        policy: Optional[PostingDatePolicy] = None,
        financial_year_start: Optional[Any] = None,
        financial_year_end: Optional[Any] = None,
    ):
        self.policy = policy or PostingDatePolicy()
        self.financial_year_start: Optional[date] = ensure_date(financial_year_start, "financial_year_start") if financial_year_start else None
        self.financial_year_end: Optional[date] = ensure_date(financial_year_end, "financial_year_end") if financial_year_end else None

    # ---- Financial year bounds ----

    def set_financial_year(self, start: Any, end: Any) -> None:
        s = ensure_date(start, "financial_year_start")
        e = ensure_date(end, "financial_year_end")
        if e < s:
            raise ValueError("financial_year_end cannot be earlier than financial_year_start")
        self.financial_year_start = s
        self.financial_year_end = e

    def validate_transaction_date(self, txn_date: Any) -> date:
        d = ensure_date(txn_date, "transaction_date")

        if not self.policy.allow_future_transaction_dates and d > date.today():
            raise ValueError(f"transaction_date cannot be in the future ({d.isoformat()})")

        if self.policy.enforce_financial_year_bounds and self.financial_year_start and self.financial_year_end:
            if d < self.financial_year_start or d > self.financial_year_end:
                raise ValueError(
                    f"transaction_date {d.isoformat()} outside configured financial year "
                    f"({self.financial_year_start.isoformat()} to {self.financial_year_end.isoformat()})"
                )

        return d

    def requires_back_valuation_override(self, txn_date: Any, value_date: Any) -> bool:
        t = self.validate_transaction_date(txn_date)
        v = ensure_date(value_date, "value_date")
        return v < t

    def validate_value_date_no_override(self, txn_date: Any, value_date: Any) -> Tuple[date, date]:
        t = self.validate_transaction_date(txn_date)
        v = ensure_date(value_date, "value_date")
        if v < t:
            raise ValueError(
                f"value_date {v.isoformat()} cannot be earlier than transaction_date {t.isoformat()} without override"
            )
        return t, v

    # ---- Override workflow ----

    def create_back_valuation_override_request(
        self,
        requester_user_id: str,
        txn_date: Any,
        value_date: Any,
        reason: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> DateOverrideRequest:
        if not requester_user_id:
            raise ValueError("requester_user_id is required")

        t = self.validate_transaction_date(txn_date)
        v = ensure_date(value_date, "value_date")

        if v >= t:
            raise ValueError("Override request not required: value_date is not earlier than transaction_date")

        return DateOverrideRequest(
            request_id=str(uuid.uuid4()),
            created_utc=utc_now_iso(),
            requester_user_id=requester_user_id,
            transaction_date=t.isoformat(),
            value_date=v.isoformat(),
            reason=(reason or "").strip(),
            context=context or {},
        )

    def decide_override(
        self,
        req: DateOverrideRequest,
        approver_user_id: str,
        approver_band: str,
        outcome: str,
        decision_reason: str,
    ) -> DateOverrideDecision:
        if not approver_user_id:
            raise ValueError("approver_user_id is required")

        outcome_u = (outcome or "").strip().upper()
        if outcome_u not in ("APPROVED", "REJECTED"):
            raise ValueError("outcome must be APPROVED or REJECTED")

        min_band = self.policy.min_override_band_for_back_valuation
        if band_index(approver_band) < band_index(min_band):
            # Force reject, but still log the attempt.
            outcome_u = "REJECTED"
            decision_reason = (
                (decision_reason or "").strip()
                + f" | REJECTED: insufficient authority (required {min_band}, got {approver_band})"
            ).strip()

        decision = DateOverrideDecision(
            decision_utc=utc_now_iso(),
            approver_user_id=approver_user_id,
            approver_band=approver_band,
            outcome=outcome_u,
            decision_reason=(decision_reason or "").strip(),
        )

        entry = DateOverrideLogEntry(
            event_type="POSTING_DATE_OVERRIDE",
            request=asdict(req),
            decision=asdict(decision),
        )
        jsonl_append(self.policy.override_log_path, asdict(entry))
        return decision

    def apply_override_if_approved(
        self,
        txn_date: Any,
        value_date: Any,
        decision: Optional[DateOverrideDecision],
    ) -> Tuple[date, date]:
        t = self.validate_transaction_date(txn_date)
        v = ensure_date(value_date, "value_date")

        if v >= t:
            return t, v

        if not decision:
            raise ValueError("Back-valued value_date requires an approved override decision")

        if decision.outcome != "APPROVED":
            raise ValueError("Override decision is not APPROVED; cannot apply back-valuation")

        return t, v