"""
batch_close.py — REA Capital Trading Engine
-------------------------------------------
Bank-grade Batch Close & Financial Reporting Engine

Scope:
- Daily (EOD) batch close
- Monthly close
- Year-end close (organization-defined FY)
- Ledger state reporting (per ledger, per currency)
- Balance Sheet & P&L preparation
- Login / session audit reporting
- NIL reporting when no activity
- Leap-year safe date handling

This module is PROMPT-ONLY (no posting, no execution).
"""

from datetime import datetime, date, timedelta
import calendar
from collections import defaultdict
from typing import Dict, List, Any

# -----------------------------
# Helper: Financial Year Logic
# -----------------------------
class FinancialYearConfig:
    def __init__(self, fy_start_month: int = 1, fy_start_day: int = 1):
        self.fy_start_month = fy_start_month
        self.fy_start_day = fy_start_day

    def financial_year_start(self, d: date) -> date:
        fy_start = date(d.year, self.fy_start_month, self.fy_start_day)
        if d < fy_start:
            fy_start = date(d.year - 1, self.fy_start_month, self.fy_start_day)
        return fy_start

    def financial_year_end(self, d: date) -> date:
        fy_start = self.financial_year_start(d)
        next_fy_start = date(fy_start.year + 1, self.fy_start_month, self.fy_start_day)
        return next_fy_start - timedelta(days=1)


# -----------------------------
# Batch Close Engine
# -----------------------------
class BatchCloseEngine:
    def __init__(
        self,
        posting_ledger,
        auth_controller,
        fy_config: FinancialYearConfig,
    ):
        self.posting_ledger = posting_ledger
        self.auth = auth_controller
        self.fy = fy_config

    # -------------------------
    # Core Aggregation
    # -------------------------
    def _aggregate_ledgers(self, as_of: date) -> Dict[str, Dict[str, Any]]:
        """
        Returns:
        {
          ledger_name: {
            currency: {
              opening,
              debits,
              credits,
              closing
            }
          }
        }
        """
        summary = defaultdict(lambda: defaultdict(lambda: {
            "opening": 0.0,
            "debits": 0.0,
            "credits": 0.0,
            "closing": 0.0
        }))

        entries = self.posting_ledger.get_entries_for_date(as_of)

        for e in entries:
            ledger = e["ledger"]
            ccy = e["currency"]
            amt = e["amount"]

            if e["type"] == "DR":
                summary[ledger][ccy]["debits"] += amt
            else:
                summary[ledger][ccy]["credits"] += amt

        for ledger, ccy_map in summary.items():
            for ccy, row in ccy_map.items():
                opening = self.posting_ledger.get_opening_balance(
                    ledger=ledger,
                    currency=ccy,
                    as_of=as_of
                )
                row["opening"] = opening
                row["closing"] = opening + row["credits"] - row["debits"]

        return summary

    # -------------------------
    # Reporting Primitives
    # -------------------------
    def _print_ledger_report(self, ledger_summary: Dict[str, Dict[str, Any]]):
        if not ledger_summary:
            print("NIL — No ledger activity for this business day.")
            return

        for ledger, ccy_map in ledger_summary.items():
            for ccy, r in ccy_map.items():
                print(
                    f"{ledger} | {ccy} | "
                    f"OPEN={r['opening']:.2f} "
                    f"DR={r['debits']:.2f} "
                    f"CR={r['credits']:.2f} "
                    f"CLOSE={r['closing']:.2f}"
                )

    def _print_login_audit(self, as_of: date):
        sessions = self.auth.get_sessions_for_date(as_of)
        print("\n=== LOGIN AUDIT REPORT ===")

        if not sessions:
            print("NIL — No user logins for this business day.")
            return

        for s in sessions:
            print(
                f"user={s['user_id']} | "
                f"login={s['login_time']} | "
                f"logout={s.get('logout_time', 'TIMEOUT/ACTIVE')}"
            )

    # -------------------------
    # Financial Statements
    # -------------------------
    def _prepare_balance_sheet(self, ledger_summary):
        assets = liabilities = equity = 0.0

        for ledger, ccy_map in ledger_summary.items():
            for _, r in ccy_map.items():
                bal = r["closing"]
                if ledger.startswith("ASSET"):
                    assets += bal
                elif ledger.startswith("LIAB"):
                    liabilities += bal
                elif ledger.startswith("EQUITY"):
                    equity += bal

        print("\n=== BALANCE SHEET ===")
        print(f"Assets: {assets:.2f}")
        print(f"Liabilities: {liabilities:.2f}")
        print(f"Equity: {equity:.2f}")
        print(f"Check (A = L + E): {assets:.2f} vs {(liabilities + equity):.2f}")

    def _prepare_pnl(self, ledger_summary):
        income = expenses = 0.0

        for ledger, ccy_map in ledger_summary.items():
            for _, r in ccy_map.items():
                if ledger.startswith("INCOME"):
                    income += r["credits"] - r["debits"]
                elif ledger.startswith("EXPENSE"):
                    expenses += r["debits"] - r["credits"]

        print("\n=== PROFIT & LOSS ===")
        print(f"Income: {income:.2f}")
        print(f"Expenses: {expenses:.2f}")
        print(f"Net P&L: {(income - expenses):.2f}")

    # -------------------------
    # Public Batch APIs
    # -------------------------
    def run_eod(self, as_of: date):
        print(f"\n=== END-OF-DAY BATCH — {as_of} ===")
        ledger_summary = self._aggregate_ledgers(as_of)

        print("\n--- LEDGER STATES ---")
        self._print_ledger_report(ledger_summary)

        self._prepare_balance_sheet(ledger_summary)
        self._prepare_pnl(ledger_summary)
        self._print_login_audit(as_of)

        print("\nEOD batch complete.")

    def run_month_end(self, year: int, month: int):
        last_day = calendar.monthrange(year, month)[1]
        self.run_eod(date(year, month, last_day))

    def run_year_end(self, as_of: date):
        fy_end = self.fy.financial_year_end(as_of)
        self.run_eod(fy_end)
