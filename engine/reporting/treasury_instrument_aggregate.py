"""
engine/reporting/treasury_instrument_aggregate.py

Treasury Instrument Aggregate (Auditor-Grade)
---------------------------------------------
Purpose:
- Instrument-level aggregation (DR/CR/NET, counts)
- Supports:
    - mode: detailed | summary | exception
    - date (single working date) OR range (from_date/to_date) OR as_of_date (<= date)
    - branch/team/user breakdown (optional, mode-dependent)
- Role + Department scoped:
    - TREASURY / TREASURY_SUPERVISOR: only instruments allowed for their department
    - AUDIT_CONTROL: read-only, can see all instruments
    - SUPER_USER: can see all instruments
- Data source: audit_logs/journal.jsonl (JSONL)

NOTE:
This report relies on journal entries containing:
    dims.instrument_id
Optionally:
    dims.asset_class, dims.book, dims.branch, dims.team, maker_user_id, checker_user_id
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, date
from decimal import Decimal
from collections import defaultdict
from typing import Dict, Any, List, Optional, Tuple, Set


REPO_ROOT = Path(__file__).resolve().parents[2]

JOURNAL_FILE = REPO_ROOT / "audit_logs" / "journal.jsonl"
ORG_FILE = REPO_ROOT / "backend" / "app" / "config" / "org_structure.json"
INSTR_FILE = REPO_ROOT / "backend" / "app" / "config" / "instrument_master.json"


TREASURY_ROLES = {"TREASURY", "TREASURY_SUPERVISOR", "SUPER_USER", "ADMIN"}
AUDIT_ROLE = "AUDIT_CONTROL"
SUPER_ROLES = {"SUPER_USER", "ADMIN"}


# ============================================================
# Small utilities
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


def _safe_str(v: Any) -> str:
    return "" if v is None else str(v)


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                out.append(json.loads(s))
            except Exception:
                continue
    return out


# ============================================================
# Org resolution (department_code)
# ============================================================

def _iter_teams(org: Dict[str, Any]) -> List[Tuple[str, str, str, str, Dict[str, Any]]]:
    """
    Returns list of (country, division, branch, team, team_obj)
    """
    out = []
    country = _safe_str(org.get("country", ""))
    divisions = org.get("divisions", {}) or {}
    for div_name, div_obj in divisions.items():
        branches = (div_obj or {}).get("branches", {}) or {}
        for branch_name, branch_obj in branches.items():
            teams = (branch_obj or {}).get("teams", {}) or {}
            for team_name, team_obj in teams.items():
                out.append((country, str(div_name), str(branch_name), str(team_name), team_obj or {}))
    return out


def resolve_user_context(org: Dict[str, Any], user_id: str) -> Dict[str, str]:
    """
    Maps user_id to:
      country, division, branch, team, department_code, function_group
    If not found, returns UNKNOWNs.
    """
    for country, division, branch, team, team_obj in _iter_teams(org):
        supervisors = team_obj.get("supervisors") or []
        members = team_obj.get("members") or []
        if user_id in supervisors or user_id in members:
            return {
                "country": country or "UNKNOWN",
                "division": division or "UNKNOWN",
                "branch": branch or "UNKNOWN",
                "team": team or "UNKNOWN",
                "department_code": _safe_str(team_obj.get("department_code") or team),
                "function_group": _safe_str(team_obj.get("function_group") or "UNKNOWN"),
            }
    return {
        "country": "UNKNOWN",
        "division": "UNKNOWN",
        "branch": "UNKNOWN",
        "team": "UNKNOWN",
        "department_code": "UNKNOWN",
        "function_group": "UNKNOWN",
    }


# ============================================================
# Instrument entitlement
# ============================================================

def _allowed_instruments_for_department(instr_master: Dict[str, Any], department_code: str) -> Set[str]:
    allowed = set()
    for instr_id, meta in (instr_master or {}).items():
        deps = (meta or {}).get("allowed_departments") or []
        if department_code in deps:
            allowed.add(instr_id)
    return allowed


# ============================================================
# Date filtering
# ============================================================

def _date_of_entry(r: Dict[str, Any]) -> Optional[str]:
    d = _safe_str(r.get("execution_date", ""))[:10]
    if len(d) == 10 and d[4] == "-" and d[7] == "-":
        return d
    return None


def _in_scope(
    d: str,
    *,
    report_date: Optional[str],
    from_date: Optional[str],
    to_date: Optional[str],
    as_of_date: Optional[str],
) -> bool:
    # precedence:
    # 1) report_date exact
    # 2) from/to range inclusive
    # 3) as_of_date (<=)
    if report_date:
        return d == report_date
    if from_date and to_date:
        return from_date <= d <= to_date
    if as_of_date:
        return d <= as_of_date
    return False


# ============================================================
# Aggregation
# ============================================================

def build_instrument_aggregate(
    rows: List[Dict[str, Any]],
    *,
    mode: str,
) -> Dict[str, Any]:
    """
    Produces:
      per_instrument totals
      optional breakdowns (branch/team/user)
    """
    mode = (mode or "detailed").lower()

    per_instr = defaultdict(lambda: {
        "count": 0,
        "dr": Decimal("0"),
        "cr": Decimal("0"),
        "net": Decimal("0"),
        "by_branch": defaultdict(lambda: {"count": 0, "dr": Decimal("0"), "cr": Decimal("0"), "net": Decimal("0")}),
        "by_team": defaultdict(lambda: {"count": 0, "dr": Decimal("0"), "cr": Decimal("0"), "net": Decimal("0")}),
        "by_user": defaultdict(lambda: {"count": 0, "dr": Decimal("0"), "cr": Decimal("0"), "net": Decimal("0")}),
    })

    for r in rows:
        dims = r.get("dims") or {}
        if not isinstance(dims, dict):
            dims = {}

        instr_id = _safe_str(dims.get("instrument_id")).strip()
        if not instr_id:
            # no instrument dimension -> cannot be counted
            continue

        side = _safe_str(r.get("side")).upper()
        amt = _parse_decimal(r.get("amount"))
        maker = _safe_str(r.get("maker_user_id")).strip() or "UNKNOWN"
        branch = _safe_str(dims.get("branch")).strip() or "UNKNOWN"
        team = _safe_str(dims.get("team")).strip() or "UNKNOWN"

        bucket = per_instr[instr_id]
        bucket["count"] += 1

        if side == "DR":
            bucket["dr"] += amt
            bucket["net"] += amt
        elif side == "CR":
            bucket["cr"] += amt
            bucket["net"] -= amt
        else:
            # unknown side counts but doesn't move money
            pass

        # breakdowns: always maintained, but only printed depending on mode
        b = bucket["by_branch"][branch]
        t = bucket["by_team"][team]
        u = bucket["by_user"][maker]

        b["count"] += 1
        t["count"] += 1
        u["count"] += 1

        if side == "DR":
            b["dr"] += amt; b["net"] += amt
            t["dr"] += amt; t["net"] += amt
            u["dr"] += amt; u["net"] += amt
        elif side == "CR":
            b["cr"] += amt; b["net"] -= amt
            t["cr"] += amt; t["net"] -= amt
            u["cr"] += amt; u["net"] -= amt

    # Convert Decimals to strings for safe printing later
    def _dec(v: Decimal) -> str:
        return str(v)

    out = {}
    for instr_id, bucket in per_instr.items():
        out[instr_id] = {
            "count": bucket["count"],
            "dr": _dec(bucket["dr"]),
            "cr": _dec(bucket["cr"]),
            "net": _dec(bucket["net"]),
            "by_branch": {
                k: {"count": v["count"], "dr": _dec(v["dr"]), "cr": _dec(v["cr"]), "net": _dec(v["net"])}
                for k, v in bucket["by_branch"].items()
            },
            "by_team": {
                k: {"count": v["count"], "dr": _dec(v["dr"]), "cr": _dec(v["cr"]), "net": _dec(v["net"])}
                for k, v in bucket["by_team"].items()
            },
            "by_user": {
                k: {"count": v["count"], "dr": _dec(v["dr"]), "cr": _dec(v["cr"]), "net": _dec(v["net"])}
                for k, v in bucket["by_user"].items()
            },
        }

    return out


# ============================================================
# Public report handler (Report Registry compatible)
# ============================================================

def generate_treasury_instrument_aggregate(**kwargs) -> str:
    """
    Registry handler signature:
      from_date, to_date, as_of_date, sections, filters
    """
    filters: Dict[str, Any] = kwargs.get("filters") or {}
    role = _safe_str(filters.get("role") or "").strip().upper()  # optional; registry passes role separately too
    user_id = _safe_str(filters.get("user_id") or "").strip() or "UNKNOWN"

    mode = _safe_str(filters.get("mode") or "detailed").strip().lower()
    report_date = _safe_str(filters.get("date") or kwargs.get("as_of_date") or "").strip() or None

    from_date = _safe_str(kwargs.get("from_date") or "").strip() or None
    to_date = _safe_str(kwargs.get("to_date") or "").strip() or None
    as_of_date = _safe_str(kwargs.get("as_of_date") or "").strip() or None

    # Role enforcement (report_printer will also gate, but we harden here)
    if not role:
        # if role wasn't passed in filters, allow report_printer to gate; still proceed safely
        role = "UNKNOWN"

    if role != AUDIT_ROLE and role not in TREASURY_ROLES:
        raise PermissionError("Instrument aggregates are restricted (Treasury/Audit/Super roles only).")

    org = _load_json(ORG_FILE)
    instr_master = _load_json(INSTR_FILE, default={})

    user_ctx = resolve_user_context(org, user_id)
    dept = user_ctx.get("department_code", "UNKNOWN")

    # Entitlement set
    if role == AUDIT_ROLE or role in SUPER_ROLES:
        allowed_instr = set(instr_master.keys())
    else:
        allowed_instr = _allowed_instruments_for_department(instr_master, dept)

    rows = _read_jsonl(JOURNAL_FILE)

    scoped: List[Dict[str, Any]] = []
    for r in rows:
        d = _date_of_entry(r)
        if not d:
            continue
        if not _in_scope(d, report_date=report_date, from_date=from_date, to_date=to_date, as_of_date=as_of_date):
            continue

        dims = r.get("dims") or {}
        if not isinstance(dims, dict):
            dims = {}
        instr_id = _safe_str(dims.get("instrument_id")).strip()
        if not instr_id:
            continue

        if instr_id not in allowed_instr:
            continue

        scoped.append(r)

    agg = build_instrument_aggregate(scoped, mode=mode)

    # Formatting
    lines: List[str] = []
    lines.append("TREASURY INSTRUMENT AGGREGATE")
    lines.append("=" * 92)
    lines.append(f"MODE       : {mode.upper()}")
    lines.append(f"ROLE       : {role}")
    lines.append(f"USER_ID    : {user_id}")
    lines.append(f"DEPARTMENT : {dept}")
    if report_date:
        lines.append(f"DATE       : {report_date}")
    elif from_date and to_date:
        lines.append(f"RANGE      : {from_date} .. {to_date}")
    elif as_of_date:
        lines.append(f"AS-OF      : {as_of_date}")
    else:
        lines.append("SCOPE      : (none specified)")

    lines.append("-" * 92)

    if not agg:
        # exception mode should be NIL-friendly
        lines.append("NIL: No instrument-tagged transactions found in scope.")
        return "\n".join(lines)

    # Sort by instrument_id
    for instr_id in sorted(agg.keys()):
        a = agg[instr_id]
        lines.append(f"\nINSTRUMENT: {instr_id}")
        lines.append(f"  lines : {a['count']}")
        lines.append(f"  DR    : {a['dr']}")
        lines.append(f"  CR    : {a['cr']}")
        lines.append(f"  NET   : {a['net']}   (DR - CR)")
        # all-of-the-above requirement: include branch breakdown in summary and detailed, but suppress in exception if NIL-like
        if mode in {"summary", "detailed"}:
            lines.append("  BY BRANCH:")
            byb = a.get("by_branch") or {}
            if not byb:
                lines.append("    (none)")
            else:
                for b in sorted(byb.keys()):
                    v = byb[b]
                    lines.append(f"    {b}: lines={v['count']} DR={v['dr']} CR={v['cr']} NET={v['net']}")
        if mode == "detailed":
            lines.append("  BY TEAM:")
            byt = a.get("by_team") or {}
            if not byt:
                lines.append("    (none)")
            else:
                for t in sorted(byt.keys()):
                    v = byt[t]
                    lines.append(f"    {t}: lines={v['count']} DR={v['dr']} CR={v['cr']} NET={v['net']}")
            lines.append("  BY USER:")
            byu = a.get("by_user") or {}
            if not byu:
                lines.append("    (none)")
            else:
                for u in sorted(byu.keys()):
                    v = byu[u]
                    lines.append(f"    {u}: lines={v['count']} DR={v['dr']} CR={v['cr']} NET={v['net']}")

        if mode == "exception":
            # in exception mode, print only if there was activity (already true) but keep it minimal
            pass

    return "\n".join(lines)