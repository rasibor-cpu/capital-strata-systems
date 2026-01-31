"""
batch_close.py — REA Capital Trading Engine
-------------------------------------------
Batch close engine for:
- End-of-Day (EOD)
- Month-end
- Year-end

Responsibilities (read-only):
- Aggregate posting ledger states (opening, DR, CR, closing)
- Compute balance sheet (A=L+E convention by ledger name prefixes)
- Compute ageing schedules (Suspense/Sundry/Unsettled) using ageing.py bucket rules
- Run EOD validations + escalation payload

This module intentionally avoids depending on a specific ageing "engine" symbol name.
It computes ageing from PostingLedger entries using ageing.py primitives.
"""

from datetime import date
from typing import Dict, Any, Tuple, List

from posting_ledger import PostingLedger
from eod_validations import EODValidationEngine

# Import only stable primitives that exist in ageing.py (created earlier)
from ageing import age_days, bucket_for_days, bucket_counts


class BatchCloseEngine:
    """
    Orchestrates batch close operations.
    Read-only aggregation and validations.
    """

    def __init__(self):
        self.posting_ledger = PostingLedger()
        self.validator = EODValidationEngine()

        # Stable interfaces expected by exporters / APIs
        self.ageing = _AgeingAdapter(self.posting_ledger)
        self.auth = _AuthAuditAdapter()
        self.fy = _FinancialYearAdapter()

    # -------------------------
    # Batch entrypoints
    # -------------------------

    def run_eod(self, as_of: date) -> None:
        summary = self._aggregate_ledgers(as_of)
        assets, liabilities, equity = self._compute_balance_sheet(summary)
        ageing_report = self.ageing.run_ageing(as_of)

        # reset breaches for this run
        if hasattr(self.validator, "breaches"):
            self.validator.breaches = []

        self.validator.validate_double_entry(summary)
        self.validator.validate_balance_sheet(assets, liabilities, equity)
        self.validator.validate_ageing(ageing_report)

    def run_month_end(self, year: int, month: int) -> None:
        # compute last day of month safely
        if month == 12:
            as_of = date(year, 12, 31)
        else:
            as_of = date(year, month + 1, 1)
            as_of = as_of.fromordinal(as_of.toordinal() - 1)
        self.run_eod(as_of)

    def run_year_end(self, as_of: date) -> None:
        fy_end = self.fy.financial_year_end(as_of)
        self.run_eod(fy_end)

    # -------------------------
    # Interfaces consumed by ReportExports
    # -------------------------

    def _aggregate_ledgers(self, as_of: date) -> Dict[str, Dict[str, Dict[str, float]]]:
        """
        Returns:
          { ledger_id: { currency: {opening, debits, credits, closing} } }

        Uses PostingLedger entries for the business day only.
        """
        result: Dict[str, Dict[str, Dict[str, float]]] = {}

        entries = getattr(self.posting_ledger, "entries", [])

        for e in entries:
            booking_date = str(getattr(e, "booking_date", ""))[:10]
            if booking_date != as_of.isoformat():
                continue

            ledger = getattr(e, "ledger_id", "UNKNOWN_LEDGER")
            ccy = getattr(e, "currency", "UNKNOWN")

            bucket = result.setdefault(ledger, {}).setdefault(
                ccy,
                {"opening": 0.0, "debits": 0.0, "credits": 0.0, "closing": 0.0},
            )

            amt = float(getattr(e, "notional", 0.0))
            side = str(getattr(e, "side", "")).upper()

            if side == "DR":
                bucket["debits"] += amt
            elif side == "CR":
                bucket["credits"] += amt

            bucket["closing"] = bucket["opening"] + bucket["credits"] - bucket["debits"]

        return result

    def _compute_balance_sheet(
        self, summary: Dict[str, Dict[str, Dict[str, float]]]
    ) -> Tuple[float, float, float]:
        """
        Compute Assets, Liabilities, Equity totals based on ledger naming.

        Naming convention (adjust later as needed):
        - ASSET*
        - LIAB* or LIABILITY*
        - EQUITY*
        """
        assets = liabilities = equity = 0.0

        for ledger, ccy_map in summary.items():
            for _, r in ccy_map.items():
                closing = float(r.get("closing", 0.0))
                name = str(ledger).upper()

                if name.startswith("ASSET"):
                    assets += closing
                elif name.startswith("LIAB") or name.startswith("LIABILITY"):
                    liabilities += closing
                elif name.startswith("EQUITY"):
                    equity += closing

        return assets, liabilities, equity


# -------------------------
# Stable adapters
# -------------------------

class _AgeingAdapter:
    """
    Builds ageing schedules from PostingLedger entries.

    Output format expected by EOD validations:
      {
        "LEDGER|CCY|DOMAIN": {
          "T+1 day": amt,
          "T+3 days": amt,
          ...
        }
      }
    """

    def __init__(self, posting_ledger: PostingLedger):
        self.posting_ledger = posting_ledger

    def run_ageing(self, as_of: date) -> Dict[str, Dict[str, float]]:
        entries = getattr(self.posting_ledger, "entries", [])
        report: Dict[str, Dict[str, float]] = {}

        for e in entries:
            # Use initial entry date T = booking_date (first posted into suspense/sundry/unsettled)
            t_str = str(getattr(e, "booking_date", ""))[:10]
            if not t_str:
                continue

            ledger_id = str(getattr(e, "ledger_id", "UNKNOWN_LEDGER"))
            ccy = str(getattr(e, "currency", "UNKNOWN"))
            domain = str(getattr(e, "domain", "UNKNOWN")).upper()

            # Apply ageing to items considered "unsettled" buckets:
            # - suspense
            # - sundry
            # - any explicitly unsettled transaction types
            tx_type = str(getattr(e, "transaction_type", "")).upper()
            ledger_upper = ledger_id.upper()

            is_suspense = "SUSP" in ledger_upper or "SUSPENSE" in ledger_upper
            is_sundry = "SUND" in ledger_upper or "SUNDRY" in ledger_upper
            is_unsettled = tx_type in ("UNSETTLED", "PENDING", "BREAK")

            if not (is_suspense or is_sundry or is_unsettled):
                continue

            amt = float(getattr(e, "notional", 0.0))
            days = age_days(t_str, as_of=as_of.isoformat())
            bucket = bucket_for_days(days)

            key = f"{ledger_id}|{ccy}|{domain}"
            if key not in report:
                report[key] = bucket_counts()

            report[key][bucket] += abs(amt)

        return report


class _AuthAuditAdapter:
    """
    Keeps exports stable until auth wiring is connected.
    """
    def get_sessions_for_date(self, as_of: date) -> List[Dict[str, Any]]:
        return []


class _FinancialYearAdapter:
    """
    Default calendar year end; organization-specific year end can be wired later.
    """
    def financial_year_end(self, as_of: date) -> date:
        return date(as_of.year, 12, 31)
