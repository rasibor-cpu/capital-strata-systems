"""
batch_close.py — REA Capital Trading Engine
-------------------------------------------
Batch close engine for:
- End-of-Day (EOD)
- Month-end
- Year-end

Responsibilities (read-only):
- Aggregate posting ledger states (opening, DR, CR, closing)
- Compute balance sheet & P&L (based on ledger naming conventions)
- Run ageing analysis (suspense/sundry/unsettled)
- Run EOD validations + escalation payload

NOTE:
- This module intentionally does NOT import trade signal ledger (ledger.py).
  Batch close is built from PostingLedger + controls.
"""

from datetime import date
from typing import Dict, Any, Tuple, List

from posting_ledger import PostingLedger
from ageing import run_ageing  # canonical function-based ageing
from eod_validations import EODValidationEngine


class BatchCloseEngine:
    """
    Orchestrates batch close operations.
    Read-only aggregation and validations.
    """

    def __init__(self):
        # Core ledgers / engines
        self.posting_ledger = PostingLedger()
        self.validator = EODValidationEngine()

        # Stable interface expected by exports/apis
        self.ageing = _AgeingAdapter(self.posting_ledger)

        # Login audit provider (stub-safe): keep interface stable
        self.auth = _AuthAuditAdapter()

        # FY provider (stub-safe): keep interface stable
        self.fy = _FinancialYearAdapter()

    # -------------------------
    # Batch entrypoints
    # -------------------------

    def run_eod(self, as_of: date) -> None:
        """
        Runs EOD aggregation + validations.
        Prints nothing here; printing happens in batch_close runner or exports.
        """
        summary = self._aggregate_ledgers(as_of)
        assets, liabilities, equity = self._compute_balance_sheet(summary)
        ageing_report = self.ageing.run_ageing(as_of)

        # reset breaches for this run (export layer may also reset)
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
            as_of = date(year, month + 1, 1)  # first day next month
            as_of = as_of.fromordinal(as_of.toordinal() - 1)  # back one day
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
          { ledger: { currency: {opening, debits, credits, closing} } }

        IMPORTANT:
        This method is used by report_exports.py and APIs. Keep stable.
        """
        result: Dict[str, Dict[str, Dict[str, float]]] = {}

        # PostingLedger stores entries internally; we read from its snapshot
        entries = getattr(self.posting_ledger, "entries", [])

        # Filter by booking date == as_of
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

            # In posting ledger: DR increases debits, CR increases credits
            if side == "DR":
                bucket["debits"] += amt
            elif side == "CR":
                bucket["credits"] += amt

            # opening balances for demo assumed 0 unless you add balance carryforward later
            bucket["closing"] = bucket["opening"] + bucket["credits"] - bucket["debits"]

        return result

    def _compute_balance_sheet(
        self, summary: Dict[str, Dict[str, Dict[str, float]]]
    ) -> Tuple[float, float, float]:
        """
        Compute Assets, Liabilities, Equity totals based on ledger naming.
        You can align naming conventions later (ASSET*, LIAB*, EQUITY*).
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
    Normalizes ageing interface: run_ageing(as_of) -> dict report
    """
    def __init__(self, posting_ledger: PostingLedger):
        self.posting_ledger = posting_ledger

    def run_ageing(self, as_of: date) -> Dict[str, Dict[str, float]]:
        # run_ageing was authored as a module-level function; it can be extended later
        # In this adapter we simply call it. If you later need ledger injection, we adapt here.
        return run_ageing(as_of)


class _AuthAuditAdapter:
    """
    Keeps exports and batch close stable even before full auth wiring.
    Exports expect get_sessions_for_date(as_of) -> list[dict]
    """
    def get_sessions_for_date(self, as_of: date) -> List[Dict[str, Any]]:
        return []


class _FinancialYearAdapter:
    """
    Keeps interface stable. Your FY config can be wired later.
    """
    def financial_year_end(self, as_of: date) -> date:
        # default calendar year end
        return date(as_of.year, 12, 31)
