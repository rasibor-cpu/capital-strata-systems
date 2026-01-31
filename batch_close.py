"""
batch_close.py — REA Capital Trading Engine
-------------------------------------------
Batch Close, Financial Reporting & Ageing Integration

Scope:
- Daily (EOD), Month-end, Year-end batch close
- Ledger state reporting (per ledger, per currency)
- Balance Sheet & P&L
- Login audit
- Suspense / Sundry / Unsettled ageing (T+ buckets)
- Leap-year safe, FY configurable

PROMPT-ONLY. No posting, no execution.
"""

from datetime import date, timedelta
import calendar
from collections import defaultdict
from typing import Dict, Any

# External modules (authoritative)
from ageing import AgeingEngine


# =====================================================
# Financial Year Configuration
# =====================================================
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
        start = self.financial_year_start(d)
        return date(start.year + 1, self.fy_start_month, self.fy_start_day) - timedelta(days=1)


# =====================================================
# Batch Close Engine
# =====================================================
class BatchCloseEngine:
    def __init__(self, posting_ledger, auth_controller, fy_config: FinancialYearConfig):
        self.posting_ledger = posting_ledger
        self.auth = auth_controller
        self.fy = fy_config
        self.ageing = AgeingEngine(posting_ledger)

    # -------------------------------------------------
    # Ledger Aggregation
    # -------------------------------------------------
    def _aggregate_ledgers(self, as_of: date):
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

    # -------------------------------------------------
    # Printing Helpers
    # -------------------------------------------------
    def _print_ledger_states(self, summary):
        print("\n--- LEDGER STATES ---")
        if not summary:
            print("NIL — No ledger activity.")
            return

        for ledger, ccy_map in summary.items():
            for ccy, r in ccy_map.items():
                print(
                    f"{ledger} | {ccy} | "
                    f"OPEN={r['opening']:.2f} "
                    f"DR={r['debits']:.2f} "
                    f"CR={r['credits']:.2f} "
                    f"CLOSE={r['closing']:.2f}"
                )

    def _print_login_audit(self, as_of: date):
        print("\n--- LOGIN AUDIT ---")
        sessions = self.auth.get_sessions_for_date(as_of)

        if not sessions:
            print("NIL — No logins recorded.")
            return

        for s in sessions:
            print(
                f"user={s['user_id']} | "
                f"login={s['login_time']} | "
                f"logout={s.get('logout_time', 'TIMEOUT/ACTIVE')}"
            )

    # -------------------------------------------------
    # Financial Statements
    # -------------------------------------------------
    def _print_balance_sheet(self, summary):
        assets = liabilities = equity = 0.0

        for ledger, ccy_map in summary.items():
            for _, r in ccy_map.items():
                bal = r["closing"]
                if ledger.startswith("ASSET"):
                    assets += bal
                elif ledger.startswith("LIAB"):
                    liabilities += bal
                elif ledger.startswith("EQUITY"):
                    equity += bal

        print("\n--- BALANCE SHEET ---")
        print(f"Assets:      {assets:.2f}")
        print(f"Liabilities: {liabilities:.2f}")
        print(f"Equity:      {equity:.2f}")
        print(f"Check A=L+E: {assets:.2f} vs {(liabilities + equity):.2f}")

    def _print_pnl(self, summary):
        income = expenses = 0.0

        for ledger, ccy_map in summary.items():
            for _, r in ccy_map.items():
                if ledger.startswith("INCOME"):
                    income += r["credits"] - r["debits"]
                elif ledger.startswith("EXPENSE"):
                    expenses += r["debits"] - r["credits"]

        print("\n--- PROFIT & LOSS ---")
        print(f"Income:  {income:.2f}")
        print(f"Expense: {expenses:.2f}")
        print(f"Net P&L: {(income - expenses):.2f}")

    # -------------------------------------------------
    # Ageing Integration (NEW — LOCKED)
    # -------------------------------------------------
    def _print_ageing_reports(self, as_of: date):
        print("\n=== AGEING REPORTS (Suspense / Sundry / Unsettled) ===")

        reports = self.ageing.run_ageing(as_of)

        if not reports:
            print("NIL — No aged items.")
            return

        for key, buckets in reports.items():
            print(f"\n[{key}]")
            for bucket, amount in buckets.items():
                print(f"  {bucket}: {amount:.2f}")

    # -------------------------------------------------
    # Public Batch APIs
    # -------------------------------------------------
    def run_eod(self, as_of: date):
        print(f"\n=== END OF DAY BATCH — {as_of} ===")

        summary = self._aggregate_ledgers(as_of)

        self._print_ledger_states(summary)
        self._print_balance_sheet(summary)
        self._print_pnl(summary)
        self._print_ageing_reports(as_of)
        self._print_login_audit(as_of)

        print("\nEOD batch completed.")

    def run_month_end(self, year: int, month: int):
        last_day = calendar.monthrange(year, month)[1]
        self.run_eod(date(year, month, last_day))

    def run_year_end(self, as_of: date):
        fy_end = self.fy.financial_year_end(as_of)
        self.run_eod(fy_end)
