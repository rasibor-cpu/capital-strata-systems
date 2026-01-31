"""
batch_close.py — REA Capital Trading Engine
-------------------------------------------
Batch close engine for:
- End-of-Day (EOD)
- Month-end
- Year-end

Responsibilities:
- Aggregate ledger balances
- Produce balance sheet & P&L
- Run ageing analysis
- Run EOD validations
- Provide read-only outputs for exports & APIs
"""

from datetime import date
from typing import Dict, Any, Tuple

# Core components
from posting_ledger import PostingLedger
from ledger import Ledger
from ageing import run_ageing  # canonical ageing function
from eod_validations import EODValidationEngine
from auth_control import AuthControl
from financial_year import FinancialYear


class BatchCloseEngine:
    """
    Orchestrates batch close operations.
    No postings or mutations are allowed here.
    """

    def __init__(self):
        self.ledger = PostingLedger()
        self.validator = EODValidationEngine()
        self.auth = AuthControl()
        self.fy = FinancialYear()

        # expose ageing via a simple adapter to keep interface stable
        self.ageing = _AgeingAdapter()

    # -------------------------
    # Public batch entrypoints
    # -------------------------

    def run_eod(self, as_of: date) -> None:
        """
        Run EOD batch close (read-only aggregation + validations).
        """
        summary = self._aggregate_ledgers(as_of)
        assets, liabilities, equity = self._compute_balance_sheet(summary)

        ageing_report = self.ageing.run_ageing(as_of)

        self.validator.validate_double_entry(summary)
        self.validator.validate_balance_sheet(assets, liabilities, equity)
        self.validator.validate_ageing(ageing_report)

    # -------------------------
    # Internal helpers (read-only)
    # -------------------------

    def _aggregate_ledgers(self, as_of: date) -> Dict[str, Dict[str, Dict[str, float]]]:
        """
        Aggregate all ledgers by currency.
        Returns:
          { ledger_name: { currency: {opening, debits, credits, closing} } }
        """
        result: Dict[str, Dict[str, Dict[str, float]]] = {}

        for entry in self.ledger.get_all_entries(as_of):
            ledger = entry["ledger"]
            ccy = entry["currency"]

            bucket = result.setdefault(ledger, {}).setdefault(
                ccy,
                {"opening": 0.0, "debits": 0.0, "credits": 0.0, "closing": 0.0},
            )

            if entry["type"] == "OPENING":
                bucket["opening"] += entry["amount"]
            elif entry["type"] == "DEBIT":
                bucket["debits"] += entry["amount"]
            elif entry["type"] == "CREDIT":
                bucket["credits"] += entry["amount"]

            bucket["closing"] = bucket["opening"] + bucket["credits"] - bucket["debits"]

        return result

    def _compute_balance_sheet(
        self, summary: Dict[str, Dict[str, Dict[str, float]]]
    ) -> Tuple[float, float, float]:
        """
        Compute Assets, Liabilities, Equity totals.
        """
        assets = liabilities = equity = 0.0

        for ledger, ccy_map in summary.items():
            for _, r in ccy_map.items():
                closing = r.get("closing", 0.0)
                if ledger.startswith("ASSET"):
                    assets += closing
                elif ledger.startswith("LIABILITY"):
                    liabilities += closing
                elif ledger.startswith("EQUITY"):
                    equity += closing

        return assets, liabilities, equity


# -------------------------
# Internal adapter
# -------------------------

class _AgeingAdapter:
    """
    Adapter to normalize ageing interface.
    Keeps BatchCloseEngine stable even if ageing.py evolves.
    """

    def run_ageing(self, as_of: date) -> Dict[str, Dict[str, float]]:
        return run_ageing(as_of)
