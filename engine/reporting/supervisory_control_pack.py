"""
engine/reporting/supervisory_control_pack.py

Supervisory Control Pack (SCP) – Multi-Mode
-------------------------------------------
Modes:
    detailed   -> full regulator JSON lines (default)
    summary    -> compressed management totals
    exception  -> only non-NIL / exception content
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from collections import defaultdict
from typing import Dict, Any, List, Optional, Set, Tuple


REPO_ROOT = Path(__file__).resolve().parents[2]

JOURNAL_FILE = REPO_ROOT / "audit_logs" / "journal.jsonl"
OUT_DIR = REPO_ROOT / "audit_logs" / "supervisory_control_pack"

ORG_FILE = REPO_ROOT / "backend" / "app" / "config" / "org_structure.json"
ACCT_FILE = REPO_ROOT / "backend" / "app" / "config" / "account_master.json"
HOLIDAYS_FILE = REPO_ROOT / "backend" / "app" / "config" / "holidays.json"


# ============================================================
# Helpers
# ============================================================

def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(f"Missing required file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_decimal(v: Any) -> Decimal:
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal("0")


def _load_journal_lines() -> List[Dict[str, Any]]:
    if not JOURNAL_FILE.exists():
        return []
    out = []
    with JOURNAL_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s:
                try:
                    out.append(json.loads(s))
                except Exception:
                    continue
    return out


# ============================================================
# Business Day Logic
# ============================================================

def _load_holidays() -> Set[str]:
    if not HOLIDAYS_FILE.exists():
        return set()
    try:
        data = json.loads(HOLIDAYS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return {str(x)[:10] for x in data}
    except Exception:
        pass
    return set()


def _is_working_day(d: date, holidays: Set[str]) -> bool:
    return d.weekday() < 5 and d.isoformat() not in holidays


def previous_working_day(ref: Optional[date] = None) -> date:
    ref = ref or datetime.now(timezone.utc).date()
    holidays = _load_holidays()
    d = ref - timedelta(days=1)
    while not _is_working_day(d, holidays):
        d -= timedelta(days=1)
    return d


# ============================================================
# Core Generators
# ============================================================

def generate_scp_report(
    *,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    as_of_date: Optional[str] = None,
    sections: Optional[List[str]] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> str:

    filters = filters or {}
    mode = filters.get("mode", "detailed").lower()

    report_date = (
        filters.get("date")
        or as_of_date
        or previous_working_day().isoformat()
    )

    org = _load_json(ORG_FILE)
    account_master = _load_json(ACCT_FILE)
    journal = _load_journal_lines()

    journal_for_day = [
        j for j in journal
        if str(j.get("execution_date", ""))[:10] == report_date
    ]

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    lines: List[str] = []

    lines.append(f"SUPERVISORY CONTROL PACK | DATE: {report_date}")
    lines.append(f"MODE: {mode.upper()}")
    lines.append("=" * 92)

    # ============================================================
    # GL Section
    # ============================================================

    movements = defaultdict(lambda: {"dr": Decimal("0"), "cr": Decimal("0"), "count": 0})

    for r in journal_for_day:
        acct = r.get("account_no")
        side = str(r.get("side", "")).upper()
        amt = _parse_decimal(r.get("amount"))

        if acct:
            if side == "DR":
                movements[acct]["dr"] += amt
            elif side == "CR":
                movements[acct]["cr"] += amt
            movements[acct]["count"] += 1

    lines.append("\nGL DAILY MOVEMENT")
    lines.append("-" * 92)

    if not movements and mode == "exception":
        lines.append("NIL")
    else:
        for acct, data in movements.items():
            lines.append(
                f"{acct} | lines={data['count']} | "
                f"DR={data['dr']} | CR={data['cr']}"
            )

    # ============================================================
    # Interbranch
    # ============================================================

    lines.append("\nINTERBRANCH")
    lines.append("-" * 92)

    interbranch_items = []

    for r in journal_for_day:
        maker = r.get("maker_user_id")
        acct = r.get("account_no")

        if not maker or not acct:
            continue

        maker_branch = "UNKNOWN"
        acct_branch = account_master.get(acct, {}).get("domiciled_branch", "UNKNOWN")

        if maker_branch != acct_branch:
            interbranch_items.append(r)

    if not interbranch_items and mode == "exception":
        lines.append("NIL")
    else:
        for r in interbranch_items:
            if mode == "summary":
                lines.append(f"{r.get('account_no')} | {r.get('amount')}")
            else:
                lines.append(json.dumps(r, ensure_ascii=False))

    # ============================================================
    # Supervisor Section
    # ============================================================

    lines.append("\nSUPERVISOR REVIEW")
    lines.append("-" * 92)

    by_maker = defaultdict(list)
    for r in journal_for_day:
        maker = r.get("maker_user_id")
        by_maker[maker].append(r)

    for maker, txns in by_maker.items():

        if mode == "exception" and not txns:
            continue

        lines.append(f"\nMAKER: {maker} | lines={len(txns)}")

        if mode == "summary":
            total = sum(_parse_decimal(t.get("amount")) for t in txns)
            lines.append(f"TOTAL AMOUNT: {total}")
        elif mode == "detailed":
            for t in txns:
                lines.append(json.dumps(t, ensure_ascii=False))

    content = "\n".join(lines)

    out_txt = OUT_DIR / f"SCP_{report_date}_{mode}.txt"
    out_txt.write_text(content, encoding="utf-8")

    return content
