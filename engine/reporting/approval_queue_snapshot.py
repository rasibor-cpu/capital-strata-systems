"""
engine/reporting/approval_queue_snapshot.py

Approval Queue Control Ledger (Auditor-Grade)
----------------------------------------------
Purpose:
• Lists ALL unapproved / unclosed tickets
• Age analysis
• Branch / Team / Maker grouping
• Control totals
• Designed for next-day governance follow-up

Fail-closed:
If approval queue file missing → returns structured NIL report
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
from typing import Dict, Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUEUE_FILE = REPO_ROOT / "backend" / "app" / "postings" / "approval_queue.json"
ORG_FILE = REPO_ROOT / "backend" / "app" / "config" / "org_structure.json"


# --------------------------------------------------
# Utilities
# --------------------------------------------------

def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else []
    return json.loads(path.read_text(encoding="utf-8"))


def _today_utc():
    return datetime.now(timezone.utc).date()


def _age_bucket(days: int) -> str:
    if days <= 1:
        return "0-1 DAYS"
    if days <= 3:
        return "2-3 DAYS"
    if days <= 7:
        return "4-7 DAYS"
    return "7+ DAYS"


def _resolve_org(user_id: str):
    org = _load_json(ORG_FILE, default={})
    divisions = org.get("divisions", {}) or {}

    for div_name, div in divisions.items():
        branches = (div or {}).get("branches", {}) or {}
        for branch_name, branch in branches.items():
            teams = (branch or {}).get("teams", {}) or {}
            for team_name, team in teams.items():
                if user_id in (team.get("members") or []) \
                   or user_id in (team.get("supervisors") or []):
                    return branch_name, team_name, div_name

    return "UNKNOWN", "UNKNOWN", "UNKNOWN"


# --------------------------------------------------
# Main Report
# --------------------------------------------------

def approval_queue_control_ledger(**kwargs) -> str:
    today = _today_utc()
    queue = _load_json(QUEUE_FILE, default=[])

    if not queue:
        return (
            "APPROVAL QUEUE CONTROL LEDGER\n"
            "=============================================\n"
            "NIL: No items currently pending.\n"
        )

    grouped = defaultdict(list)
    totals_by_bucket = defaultdict(int)
    amount_by_bucket = defaultdict(float)

    total_count = 0
    total_amount = 0.0

    for item in queue:

        status = str(item.get("status", "")).upper()
        if status not in {"PENDING", "RETURNED"}:
            continue

        maker = item.get("maker_user_id", "UNKNOWN")
        ticket_id = item.get("ticket_id", "UNKNOWN")
        amount = float(item.get("amount", 0.0))
        created_iso = item.get("created_at")

        try:
            created_dt = datetime.fromisoformat(created_iso).date()
        except Exception:
            created_dt = today

        age_days = (today - created_dt).days
        bucket = _age_bucket(age_days)

        branch, team, division = _resolve_org(maker)

        grouped[(branch, team, maker)].append({
            "ticket_id": ticket_id,
            "amount": amount,
            "age_days": age_days,
            "bucket": bucket,
        })

        totals_by_bucket[bucket] += 1
        amount_by_bucket[bucket] += amount

        total_count += 1
        total_amount += amount

    # --------------------------------------------------
    # Render
    # --------------------------------------------------

    lines = []
    lines.append("APPROVAL QUEUE CONTROL LEDGER")
    lines.append("=" * 60)
    lines.append(f"DATE : {today}")
    lines.append("")

    for (branch, team, maker), items in grouped.items():

        lines.append("-" * 60)
        lines.append(f"BRANCH : {branch}")
        lines.append(f"TEAM   : {team}")
        lines.append(f"MAKER  : {maker}")
        lines.append("-" * 60)

        for x in items:
            lines.append(
                f"{x['ticket_id']} | "
                f"AMT: {x['amount']:,.2f} | "
                f"AGE: {x['age_days']}d | "
                f"{x['bucket']}"
            )

        lines.append("")

    lines.append("=" * 60)
    lines.append("AGEING SUMMARY")
    lines.append("-" * 60)

    for bucket in sorted(totals_by_bucket.keys()):
        lines.append(
            f"{bucket:<10} "
            f"COUNT: {totals_by_bucket[bucket]:<5} "
            f"AMOUNT: {amount_by_bucket[bucket]:,.2f}"
        )

    lines.append("-" * 60)
    lines.append(f"TOTAL COUNT  : {total_count}")
    lines.append(f"TOTAL AMOUNT : {total_amount:,.2f}")
    lines.append("=" * 60)

    return "\n".join(lines)