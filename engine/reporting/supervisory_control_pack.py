"""
engine/reporting/supervisory_control_pack.py

Supervisory Control Pack (SCP) – Bank-Grade Daily Controls
----------------------------------------------------------
Generates:
1) Supervisor Daily Review Report (by supervisor -> subordinates -> txns)
2) GL Daily Movement Report (active accounts + NIL accounts)
3) Interbranch Movement Report (maker_branch != account domiciled branch)

Inputs:
- audit_logs/journal.jsonl  (flat journal lines)
- backend/app/config/org_structure.json
- backend/app/config/account_master.json
- backend/app/config/holidays.json (optional)

Outputs:
- audit_logs/supervisory_control_pack/SCP_<date>.json
- audit_logs/supervisory_control_pack/SCP_<date>_PRINT.txt

Return:
- Printable text content (for Report Center / API)
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


# -------------------------
# Helpers
# -------------------------

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
    out: List[Dict[str, Any]] = []
    with JOURNAL_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                out.append(json.loads(s))
            except Exception:
                continue
    return out


# -------------------------
# Business Calendar
# -------------------------

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
    if d.weekday() >= 5:
        return False
    if d.isoformat() in holidays:
        return False
    return True


def previous_working_day(ref: Optional[date] = None) -> date:
    ref = ref or datetime.utcnow().date()
    holidays = _load_holidays()
    d = ref - timedelta(days=1)
    while not _is_working_day(d, holidays):
        d -= timedelta(days=1)
    return d


# -------------------------
# Org Resolution
# -------------------------

def build_user_index(org: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """
    user_id -> {team, branch, division, country, role}
    role ∈ {"SUPERVISOR","MEMBER"}
    """
    country = str(org.get("country", "")).strip() or "UNKNOWN_COUNTRY"
    out: Dict[str, Dict[str, str]] = {}

    divisions = org.get("divisions", {}) or {}
    for div_name, div_obj in divisions.items():
        branches = (div_obj or {}).get("branches", {}) or {}
        for branch_name, branch_obj in branches.items():
            teams = (branch_obj or {}).get("teams", {}) or {}
            for team_name, team_obj in teams.items():
                supervisors = team_obj.get("supervisors", []) or []
                members = team_obj.get("members", []) or []

                for u in supervisors:
                    uid = str(u).strip()
                    if uid:
                        out[uid] = {
                            "team": team_name,
                            "branch": branch_name,
                            "division": div_name,
                            "country": country,
                            "role": "SUPERVISOR",
                        }

                for u in members:
                    uid = str(u).strip()
                    if uid and uid not in out:
                        out[uid] = {
                            "team": team_name,
                            "branch": branch_name,
                            "division": div_name,
                            "country": country,
                            "role": "MEMBER",
                        }

    return out


def supervisor_members(org: Dict[str, Any], supervisor_id: str) -> List[str]:
    """
    Returns members of any team where supervisor_id is listed as supervisor.
    Branch-tied by construction (teams live under branches).
    """
    supervisor_id = (supervisor_id or "").strip()
    if not supervisor_id:
        return []

    members: List[str] = []
    divisions = org.get("divisions", {}) or {}
    for _, div_obj in divisions.items():
        branches = (div_obj or {}).get("branches", {}) or {}
        for _, branch_obj in branches.items():
            teams = (branch_obj or {}).get("teams", {}) or {}
            for _, team_obj in teams.items():
                supervisors = [str(x).strip() for x in (team_obj.get("supervisors", []) or [])]
                if supervisor_id in supervisors:
                    members.extend([str(x).strip() for x in (team_obj.get("members", []) or [])])

    seen = set()
    out: List[str] = []
    for m in members:
        if m and m not in seen:
            seen.add(m)
            out.append(m)
    return out


# -------------------------
# Report Builders
# -------------------------

def _filter_journal_by_date(journal: List[Dict[str, Any]], d: str) -> List[Dict[str, Any]]:
    return [r for r in journal if str(r.get("execution_date", ""))[:10] == d]


def build_supervisor_daily_review(
    *,
    journal_for_day: List[Dict[str, Any]],
    org: Dict[str, Any],
    user_index: Dict[str, Dict[str, str]],
    report_date: str,
    supervisor_id: Optional[str] = None,
) -> Tuple[Dict[str, Any], List[str]]:
    supervisors = [u for u, meta in user_index.items() if meta.get("role") == "SUPERVISOR"]
    if supervisor_id:
        supervisor_id = supervisor_id.strip()
        supervisors = [s for s in supervisors if s == supervisor_id]

    by_maker = defaultdict(list)
    for r in journal_for_day:
        maker = str(r.get("maker_user_id", "")).strip() or "UNKNOWN_MAKER"
        by_maker[maker].append(r)

    pack: Dict[str, Any] = {
        "generated_on_utc": datetime.now(timezone.utc).isoformat(),
        "date": report_date,
        "report": "SUPERVISOR_DAILY_REVIEW",
        "supervisors": {},
    }

    lines: List[str] = []

    for s in supervisors:
        subs = supervisor_members(org, s)
        s_meta = user_index.get(s, {})

        block = {
            "meta": s_meta,
            "subordinates": {},
            "total_lines": 0,
        }

        lines.append("\f")
        lines.append(f"SUPERVISOR DAILY REVIEW | DATE: {report_date}")
        lines.append(f"SUPERVISOR: {s}")
        lines.append(
            f"BRANCH: {s_meta.get('branch')} | TEAM: {s_meta.get('team')} | "
            f"DIV: {s_meta.get('division')} | COUNTRY: {s_meta.get('country')}"
        )
        lines.append("=" * 92)
        lines.append("SIGN-OFF: ____________________________    DATE: ________________")
        lines.append("")

        for sub in subs:
            txns = by_maker.get(sub, [])
            sub_meta = user_index.get(sub, {})

            block["subordinates"][sub] = {
                "meta": sub_meta,
                "count": len(txns),
                "entries": txns,
            }
            block["total_lines"] += len(txns)

            lines.append("\f")
            lines.append(f"SUBORDINATE: {sub}")
            lines.append(
                f"BRANCH: {sub_meta.get('branch')} | TEAM: {sub_meta.get('team')} | "
                f"DIV: {sub_meta.get('division')} | COUNTRY: {sub_meta.get('country')}"
            )
            lines.append("-" * 92)

            if not txns:
                lines.append("NIL: No transactions for this subordinate on this date.")
            else:
                for r in txns:
                    # one JSON line per transaction for audit traceability
                    lines.append(json.dumps(r, ensure_ascii=False))

            lines.append("-" * 92)
            lines.append(f"SUBORDINATE TOTAL LINES: {len(txns)}")

        pack["supervisors"][s] = block

    if supervisor_id and supervisor_id not in pack["supervisors"]:
        # Supervisor not found in org map (or no longer in role)
        lines.append("\f")
        lines.append(f"SUPERVISOR DAILY REVIEW | DATE: {report_date}")
        lines.append(f"SUPERVISOR: {supervisor_id}")
        lines.append("NIL: supervisor not found in org_structure.json (or not in SUPERVISOR role).")
        pack["supervisors"][supervisor_id] = {"meta": {}, "subordinates": {}, "total_lines": 0}

    return pack, lines


def build_gl_daily_movement(
    *,
    journal_for_day: List[Dict[str, Any]],
    account_master: Dict[str, Any],
    report_date: str,
) -> Tuple[Dict[str, Any], List[str]]:
    universe = sorted([str(k) for k in (account_master or {}).keys()])
    active: Set[str] = set()
    movements = defaultdict(lambda: {"dr": Decimal("0"), "cr": Decimal("0"), "count": 0})

    for r in journal_for_day:
        acct = str(r.get("account_no", "")).strip()
        if not acct:
            continue

        active.add(acct)
        side = str(r.get("side", "")).upper()
        amt = _parse_decimal(r.get("amount", "0"))

        if side == "DR":
            movements[acct]["dr"] += amt
        elif side == "CR":
            movements[acct]["cr"] += amt
        movements[acct]["count"] += 1

    nil = [a for a in universe if a not in active]

    pack = {
        "generated_on_utc": datetime.now(timezone.utc).isoformat(),
        "date": report_date,
        "report": "GL_DAILY_MOVEMENT",
        "active_accounts": [],
        "nil_accounts": nil,
    }

    lines: List[str] = []
    lines.append(f"GL DAILY MOVEMENT REPORT | DATE: {report_date}")
    lines.append("=" * 92)
    lines.append("ACTIVE ACCOUNTS")
    lines.append("-" * 92)

    for acct in sorted(active):
        meta = account_master.get(acct, {}) if isinstance(account_master, dict) else {}
        name = meta.get("name", "")
        dr = movements[acct]["dr"]
        cr = movements[acct]["cr"]
        cnt = movements[acct]["count"]

        pack["active_accounts"].append({
            "account_no": acct,
            "name": name,
            "count": cnt,
            "total_dr": str(dr),
            "total_cr": str(cr),
        })

        lines.append(f"{acct} {name} | lines={cnt} | DR={dr} | CR={cr}")

    lines.append("")
    lines.append("-" * 92)
    lines.append("NIL ACCOUNTS (NO MOVEMENT)")
    lines.append("-" * 92)
    for acct in nil:
        meta = account_master.get(acct, {}) if isinstance(account_master, dict) else {}
        name = meta.get("name", "")
        lines.append(f"{acct} {name}")

    return pack, lines


def build_interbranch_report(
    *,
    journal_for_day: List[Dict[str, Any]],
    user_index: Dict[str, Dict[str, str]],
    account_master: Dict[str, Any],
    report_date: str,
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Interbranch = maker branch != account domiciled branch
    (Your hierarchy is respected: user->team->branch->division->country)
    """
    items: List[Dict[str, Any]] = []

    for r in journal_for_day:
        maker = str(r.get("maker_user_id", "")).strip()
        acct = str(r.get("account_no", "")).strip()
        if not maker or not acct:
            continue

        maker_branch = (user_index.get(maker, {}) or {}).get("branch", "UNKNOWN_BRANCH")
        domiciled_branch = (account_master.get(acct, {}) or {}).get("domiciled_branch", "UNKNOWN_BRANCH")

        if maker_branch != domiciled_branch:
            item = dict(r)
            item["_maker_branch"] = maker_branch
            item["_domiciled_branch"] = domiciled_branch
            items.append(item)

    pack = {
        "generated_on_utc": datetime.now(timezone.utc).isoformat(),
        "date": report_date,
        "report": "INTERBRANCH_MOVEMENTS",
        "items": items,
    }

    lines: List[str] = []
    lines.append(f"INTERBRANCH MOVEMENT REPORT | DATE: {report_date}")
    lines.append("=" * 92)

    if not items:
        lines.append("NIL: No interbranch items detected for this date.")
        return pack, lines

    grouped = defaultdict(list)
    for it in items:
        k = f"{it.get('_maker_branch')} -> {it.get('_domiciled_branch')}"
        grouped[k].append(it)

    for k in sorted(grouped.keys()):
        lines.append("")
        lines.append("-" * 92)
        lines.append(f"ROUTE: {k}")
        lines.append("-" * 92)
        for it in grouped[k]:
            lines.append(json.dumps(it, ensure_ascii=False))

    return pack, lines


# -------------------------
# Public entrypoint for Report Printer
# -------------------------

def generate_scp_report(
    *,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    as_of_date: Optional[str] = None,
    sections: Optional[List[str]] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Report Printer contract: returns printable text content.
    Also writes json + PRINT.txt outputs to audit_logs/supervisory_control_pack.

    Date selection priority:
      1) filters["date"]
      2) as_of_date
      3) previous_working_day(utc_today)
    """
    filters = filters or {}
    sections = sections or []

    org = _load_json(ORG_FILE)
    account_master = _load_json(ACCT_FILE)

    supervisor_id = filters.get("supervisor_id")
    if supervisor_id is not None:
        supervisor_id = str(supervisor_id).strip() or None

    report_date = str(filters.get("date") or "").strip()
    if not report_date:
        report_date = str(as_of_date or "").strip()
    if not report_date:
        report_date = previous_working_day().isoformat()

    journal = _load_journal_lines()
    journal_for_day = _filter_journal_by_date(journal, report_date)

    user_index = build_user_index(org)

    s_pack, s_lines = build_supervisor_daily_review(
        journal_for_day=journal_for_day,
        org=org,
        user_index=user_index,
        report_date=report_date,
        supervisor_id=supervisor_id,
    )
    g_pack, g_lines = build_gl_daily_movement(
        journal_for_day=journal_for_day,
        account_master=account_master,
        report_date=report_date,
    )
    i_pack, i_lines = build_interbranch_report(
        journal_for_day=journal_for_day,
        user_index=user_index,
        account_master=account_master,
        report_date=report_date,
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_json = OUT_DIR / f"SCP_{report_date}.json"
    out_txt = OUT_DIR / f"SCP_{report_date}_PRINT.txt"

    combined = {
        "generated_on_utc": datetime.now(timezone.utc).isoformat(),
        "date": report_date,
        "supervisor_daily_review": s_pack,
        "gl_daily_movement": g_pack,
        "interbranch": i_pack,
    }

    out_json.write_text(json.dumps(combined, indent=2, ensure_ascii=False), encoding="utf-8")

    # Build printable content
    lines: List[str] = []
    lines.append(f"SUPERVISORY CONTROL PACK (SCP) | DATE: {report_date}")
    lines.append("=" * 92)
    lines.append(f"Journal source: {JOURNAL_FILE}")
    lines.append(f"Org source    : {ORG_FILE}")
    lines.append(f"Acct source   : {ACCT_FILE}")
    if supervisor_id:
        lines.append(f"Supervisor filter: {supervisor_id}")
    lines.append("")

    lines.append("\f")
    lines.extend(g_lines)

    lines.append("\f")
    lines.extend(i_lines)

    lines.append("\f")
    lines.extend(s_lines)

    out_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return "\n".join(lines)