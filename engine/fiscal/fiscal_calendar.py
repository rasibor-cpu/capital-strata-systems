"""
Fiscal Calendar (Financial Year Governance)
Capital Strata Systems – Phase 18A

Purpose:
- Define and persist financial year boundaries
- Allow SUPER_USER/ADMIN to set FY start date (month/day)
- Compute FY period for any date
- Support auto-rollover after YEAR_END close

Storage (Phase 1):
- audit_logs/fiscal/financial_year.json
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
FISCAL_DIR = REPO_ROOT / "audit_logs" / "fiscal"
FISCAL_DIR.mkdir(parents=True, exist_ok=True)

CFG_FILE = FISCAL_DIR / "financial_year.json"

ALLOWED_ROLES = {"ADMIN", "SUPER_USER"}


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


def _load() -> Dict[str, Any]:
    if not CFG_FILE.exists():
        # Default: calendar year
        return {
            "schema": "CSS_FISCAL_YEAR_CFG_V1",
            "schema_version": "v1.0",
            "fy_start_month": 1,
            "fy_start_day": 1,
            "active_fy_start_year": _utc_today().year,
            "last_updated_utc": _now_iso(),
            "updated_by_role": "SYSTEM_DEFAULT",
            "notes": "Defaulted to calendar year (Jan 1).",
        }
    return json.loads(CFG_FILE.read_text(encoding="utf-8"))


def _save(payload: Dict[str, Any]) -> None:
    CFG_FILE.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _validate_month_day(month: int, day: int) -> None:
    if month < 1 or month > 12:
        raise ValueError("fy_start_month must be 1..12")
    if day < 1 or day > 31:
        raise ValueError("fy_start_day must be 1..31")
    # Validate by constructing a date in a safe leap year
    date(2024, month, day)


@dataclass(frozen=True)
class FiscalYearWindow:
    fy_label: str              # e.g. "FY2026"
    start_date: date
    end_date: date             # inclusive


class FiscalCalendar:
    @staticmethod
    def get_config() -> Dict[str, Any]:
        return _load()

    @staticmethod
    def set_fy_start(month: int, day: int, role: str, notes: str = "") -> Dict[str, Any]:
        role = role.strip().upper()
        if role not in ALLOWED_ROLES:
            raise PermissionError(f"Insufficient authority. Requires one of: {sorted(ALLOWED_ROLES)}")

        _validate_month_day(month, day)

        cfg = _load()
        cfg["fy_start_month"] = int(month)
        cfg["fy_start_day"] = int(day)

        # Reset active FY based on today's date
        today = _utc_today()
        fy = FiscalCalendar.fiscal_year_for_date(today)
        cfg["active_fy_start_year"] = fy.start_date.year

        cfg["last_updated_utc"] = _now_iso()
        cfg["updated_by_role"] = role
        cfg["notes"] = notes

        _save(cfg)
        return cfg

    @staticmethod
    def fiscal_year_for_date(d: date) -> FiscalYearWindow:
        cfg = _load()
        sm = int(cfg["fy_start_month"])
        sd = int(cfg["fy_start_day"])

        # Candidate FY start for the same calendar year
        start_this_year = date(d.year, sm, sd)

        if d >= start_this_year:
            start = start_this_year
        else:
            start = date(d.year - 1, sm, sd)

        next_start = date(start.year + 1, sm, sd)
        end = next_start - timedelta(days=1)

        label = f"FY{start.year}"
        return FiscalYearWindow(fy_label=label, start_date=start, end_date=end)

    @staticmethod
    def get_active_fy() -> FiscalYearWindow:
        cfg = _load()
        sm = int(cfg["fy_start_month"])
        sd = int(cfg["fy_start_day"])
        start_year = int(cfg["active_fy_start_year"])

        start = date(start_year, sm, sd)
        next_start = date(start_year + 1, sm, sd)
        end = next_start - timedelta(days=1)
        label = f"FY{start_year}"
        return FiscalYearWindow(fy_label=label, start_date=start, end_date=end)

    @staticmethod
    def rollover_to_next_fy(role: str, notes: str = "") -> Dict[str, Any]:
        """
        Called after YEAR_END close (idempotent safe behavior).
        Moves active_fy_start_year forward by 1.
        """
        role = role.strip().upper()
        if role not in ALLOWED_ROLES:
            raise PermissionError(f"Insufficient authority. Requires one of: {sorted(ALLOWED_ROLES)}")

        cfg = _load()
        cfg["active_fy_start_year"] = int(cfg.get("active_fy_start_year", _utc_today().year)) + 1
        cfg["last_updated_utc"] = _now_iso()
        cfg["updated_by_role"] = role
        cfg["notes"] = notes or "Auto-rollover after YEAR_END close."

        _save(cfg)
        return cfg
