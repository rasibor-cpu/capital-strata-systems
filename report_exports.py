"""
report_exports.py — REA Capital Trading Engine
----------------------------------------------
Wave 2: Regulatory / Management Report Exports

Exports (read-only):
- Daily EOD pack (ledger states, balance sheet, P&L, ageing, validations, login audit)
- Monthly pack (month-end EOD equivalent)
- Year-end pack (FY-configured year-end EOD equivalent)

Outputs:
- CSV files in ./out/reports/<period>/
- Prints NIL CSVs (headers only) if no transactions

Standard library only.
"""

import csv
import os
from dataclasses import asdict
from datetime import date
from typing import Dict, Any, List, Optional


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _write_csv(path: str, headers: List[str], rows: List[Dict[str, Any]]) -> None:
    _ensure_dir(os.path.dirname(path))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        if rows:
            for r in rows:
                w.writerow({k: r.get(k) for k in headers})


class ReportExports:
    """
    This export layer is intentionally thin:
    - It consumes precomputed outputs from BatchCloseEngine / EODValidationEngine
    - It does NOT recompute business logic
    """

    def __init__(self, batch_close_engine):
        self.batch = batch_close_engine

    # -------------------------
    # Helpers to flatten outputs
    # -------------------------

    @staticmethod
    def _flatten_ledger_summary(summary: Dict[str, Dict[str, Dict[str, float]]]) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for ledger, ccy_map in summary.items():
            for ccy, r in ccy_map.items():
                rows.append({
                    "ledger": ledger,
                    "currency": ccy,
                    "opening": r.get("opening", 0.0),
                    "debits": r.get("debits", 0.0),
                    "credits": r.get("credits", 0.0),
                    "closing": r.get("closing", 0.0),
                })
        return rows

    @staticmethod
    def _flatten_ageing(ageing_report: Dict[str, Dict[str, float]]) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for key, buckets in ageing_report.items():
            # key format used in batch_close integration: "LEDGER|CCY|DOMAIN"
            parts = key.split("|")
            ledger = parts[0] if len(parts) > 0 else key
            currency = parts[1] if len(parts) > 1 else ""
            domain = parts[2] if len(parts) > 2 else ""
            for bucket, amt in buckets.items():
                rows.append({
                    "ledger": ledger,
                    "currency": currency,
                    "domain": domain,
                    "bucket": bucket,
                    "amount": amt,
                })
        return rows

    @staticmethod
    def _flatten_breaches(breaches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for b in breaches:
            rows.append({
                "breach_type": b.get("breach_type"),
                "severity": b.get("severity"),
                "details": str(b.get("details")),
            })
        return rows

    # -------------------------
    # Core export API
    # -------------------------

    def export_eod_pack(self, as_of: date, out_root: str = "out/reports/daily") -> str:
        """
        Writes a full EOD pack to:
          out/reports/daily/YYYY-MM-DD/
        Returns the folder path.
        """
        folder = os.path.join(out_root, as_of.isoformat())
        _ensure_dir(folder)

        # We rely on the batch engine's internal methods for consistent output.
        summary = self.batch._aggregate_ledgers(as_of)  # noqa: SLF001 (controlled)
        assets, liabilities, equity = self.batch._compute_balance_sheet(summary)  # noqa: SLF001
        ageing_report = self.batch.ageing.run_ageing(as_of)
        sessions = self.batch.auth.get_sessions_for_date(as_of)

        # Re-run validations in a controlled way (read-only)
        validator = self.batch.validator
        validator.breaches = []  # reset for export snapshot
        validator.validate_double_entry(summary)
        validator.validate_balance_sheet(assets, liabilities, equity)
        validator.validate_ageing(ageing_report)

        # 1) Ledger states
        ledger_rows = self._flatten_ledger_summary(summary)
        _write_csv(
            os.path.join(folder, "ledger_states.csv"),
            headers=["ledger", "currency", "opening", "debits", "credits", "closing"],
            rows=ledger_rows,
        )

        # 2) Balance sheet
        bs_rows = [{
            "assets": assets,
            "liabilities": liabilities,
            "equity": equity,
            "check_assets_equals_liab_plus_eq": (assets == (liabilities + equity)),
        }]
        _write_csv(
            os.path.join(folder, "balance_sheet.csv"),
            headers=["assets", "liabilities", "equity", "check_assets_equals_liab_plus_eq"],
            rows=bs_rows,
        )

        # 3) P&L (printed by batch; for export we compute the same way)
        # Keep it conservative: income = sum(INCOME credits-debits), expenses = sum(EXPENSE debits-credits)
        income = expenses = 0.0
        for ledger, ccy_map in summary.items():
            for _, r in ccy_map.items():
                if str(ledger).startswith("INCOME"):
                    income += float(r.get("credits", 0.0)) - float(r.get("debits", 0.0))
                elif str(ledger).startswith("EXPENSE"):
                    expenses += float(r.get("debits", 0.0)) - float(r.get("credits", 0.0))

        pnl_rows = [{
            "income": income,
            "expenses": expenses,
            "net": (income - expenses),
        }]
        _write_csv(
            os.path.join(folder, "pnl.csv"),
            headers=["income", "expenses", "net"],
            rows=pnl_rows,
        )

        # 4) Ageing schedule
        ageing_rows = self._flatten_ageing(ageing_report)
        _write_csv(
            os.path.join(folder, "ageing.csv"),
            headers=["ledger", "currency", "domain", "bucket", "amount"],
            rows=ageing_rows,
        )

        # 5) Validations / breaches
        breach_rows = self._flatten_breaches(validator.breaches)
        _write_csv(
            os.path.join(folder, "validations.csv"),
            headers=["breach_type", "severity", "details"],
            rows=breach_rows,
        )

        # 6) Login audit
        login_rows: List[Dict[str, Any]] = []
        for s in sessions or []:
            login_rows.append({
                "user_id": s.get("user_id"),
                "login_time": s.get("login_time"),
                "logout_time": s.get("logout_time", "TIMEOUT/ACTIVE"),
            })
        _write_csv(
            os.path.join(folder, "logins.csv"),
            headers=["user_id", "login_time", "logout_time"],
            rows=login_rows,
        )

        return folder

    def export_month_end_pack(self, year: int, month: int, out_root: str = "out/reports/monthly") -> str:
        last_day = date(year, month, 1).replace(day=28)
        # compute month end safely
        while True:
            try:
                last_day = last_day.replace(day=last_day.day + 1)
            except ValueError:
                break
        # last_day is now invalid day+1; back off one day
        month_end = last_day

        folder = os.path.join(out_root, f"{year:04d}-{month:02d}")
        _ensure_dir(folder)
        # reuse daily exporter logic into a month folder
        daily_folder = self.export_eod_pack(month_end, out_root=folder)
        return daily_folder

    def export_year_end_pack(self, as_of: date, out_root: str = "out/reports/yearly") -> str:
        fy_end = self.batch.fy.financial_year_end(as_of)
        folder = os.path.join(out_root, f"FY_END_{fy_end.isoformat()}")
        _ensure_dir(folder)
        daily_folder = self.export_eod_pack(fy_end, out_root=folder)
        return daily_folder
