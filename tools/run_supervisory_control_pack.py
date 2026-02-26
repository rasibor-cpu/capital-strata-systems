from __future__ import annotations

import sys
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
from decimal import Decimal
from typing import Dict, Any, List, Set, Tuple

# -----------------------------
# BOOTSTRAP: ensure repo root in sys.path
# -----------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.business_calendar import previous_working_day  # noqa: E402


JOURNAL_FILE = REPO_ROOT / "audit_logs" / "journal.jsonl"

ORG_FILE = REPO_ROOT / "backend" / "app" / "config" / "org_structure.json"
ACCT_FILE = REPO_ROOT / "backend" / "app" / "config" / "account_master.json"

OUT_DIR = REPO_ROOT / "audit_logs" / "supervisory_control_pack"


def _load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Missing required config file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_journal() -> List[Dict[str, Any]]:
    if not JOURNAL_FILE.exists():
        print("Journal file not found:", JOURNAL_FILE)
        sys.exit(1)

    rows: List[Dict[str, Any]] = []
    with JOURNAL_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def parse_decimal(v: Any) -> Decimal:
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal("0")


# ----------------------------
# ORG RESOLUTION
# ----------------------------

def build_user_index(org: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """
    Returns: user_id -> {team, branch, division, country, role}
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
    Finds all members for teams where supervisor_id is listed as supervisor.
    Branch-tied by construction.
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
                supervisors = team_obj.get("supervisors", []) or []
                if supervisor_id in [str(x).strip() for x in supervisors]:
                    members.extend([str(x).strip() for x in (team_obj.get("members", []) or [])])

    # unique preserve order
    seen = set()
    out = []
    for m in members:
        if m and m not in seen:
            seen.add(m)
            out.append(m)
    return out


# ----------------------------
# REPORTS
# ----------------------------

def write_text(path: Path, lines: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def report_supervisor_daily_review(
    *,
    journal: List[Dict[str, Any]],
    org: Dict[str, Any],
    user_index: Dict[str, Dict[str, str]],
    report_date: str,
) -> Tuple[Dict[str, Any], List[str]]:
    supervisors = [u for u, meta in user_index.items() if meta.get("role") == "SUPERVISOR"]

    pack: Dict[str, Any] = {
        "generated_on_utc": datetime.now(timezone.utc).isoformat(),
        "date": report_date,
        "report": "SUPERVISOR_DAILY_REVIEW",
        "supervisors": {},
    }
    lines: List[str] = []

    by_maker = defaultdict(list)
    for r in journal:
        d = str(r.get("execution_date", ""))[:10]
        if d != report_date:
            continue
        maker = str(r.get("maker_user_id", "")).strip() or "UNKNOWN_MAKER"
        by_maker[maker].append(r)

    for s in supervisors:
        subs = supervisor_members(org, s)
        s_meta = user_index.get(s, {})
        s_block = {
            "meta": s_meta,
            "subordinates": {},
            "total_lines": 0,
        }

        lines.append("\f")
        lines.append(f"SUPERVISOR: {s}")
        lines.append(
            f"BRANCH: {s_meta.get('branch')} | TEAM: {s_meta.get('team')} | "
            f"DIV: {s_meta.get('division')} | COUNTRY: {s_meta.get('country')}"
        )
        lines.append(f"DATE: {report_date}")
        lines.append("=" * 80)
        lines.append("SIGN-OFF: ______________________    DATE: ________________")
        lines.append("")

        for sub in subs:
            txns = by_maker.get(sub, [])
            sub_meta = user_index.get(sub, {})
            s_block["subordinates"][sub] = {
                "meta": sub_meta,
                "count": len(txns),
                "entries": txns,
            }
            s_block["total_lines"] += len(txns)

            lines.append("\f")
            lines.append(f"SUBORDINATE: {sub}")
            lines.append(
                f"BRANCH: {sub_meta.get('branch')} | TEAM: {sub_meta.get('team')} | "
                f"DIV: {sub_meta.get('division')} | COUNTRY: {sub_meta.get('country')}"
            )
            lines.append(f"DATE: {report_date}")
            lines.append("-" * 80)

            if not txns:
                lines.append("NIL: No transactions for this subordinate on this date.")
            else:
                for r in txns:
                    lines.append(json.dumps(r, ensure_ascii=False))

            lines.append("-" * 80)
            lines.append(f"SUBORDINATE TOTAL LINES: {len(txns)}")

        pack["supervisors"][s] = s_block

    return pack, lines


def report_gl_daily_movement(
    *,
    journal: List[Dict[str, Any]],
    account_master: Dict[str, Any],
    report_date: str,
) -> Tuple[Dict[str, Any], List[str]]:
    universe = sorted([str(k) for k in (account_master or {}).keys()])
    active: Set[str] = set()
    movements = defaultdict(lambda: {"dr": Decimal("0"), "cr": Decimal("0"), "count": 0})

    for r in journal:
        d = str(r.get("execution_date", ""))[:10]
        if d != report_date:
            continue

        acct = str(r.get("account_no", "")).strip()
        if not acct:
            continue
        active.add(acct)

        side = str(r.get("side", "")).upper()
        amt = parse_decimal(r.get("amount", "0"))
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
    lines.append("=" * 80)
    lines.append("ACTIVE ACCOUNTS")
    lines.append("-" * 80)

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
    lines.append("-" * 80)
    lines.append("NIL ACCOUNTS (NO MOVEMENT)")
    lines.append("-" * 80)
    for acct in nil:
        meta = account_master.get(acct, {}) if isinstance(account_master, dict) else {}
        name = meta.get("name", "")
        lines.append(f"{acct} {name}")

    return pack, lines


def report_interbranch(
    *,
    journal: List[Dict[str, Any]],
    user_index: Dict[str, Dict[str, str]],
    account_master: Dict[str, Any],
    report_date: str,
) -> Tuple[Dict[str, Any], List[str]]:
    pack = {
        "generated_on_utc": datetime.now(timezone.utc).isoformat(),
        "date": report_date,
        "report": "INTERBRANCH_MOVEMENTS",
        "items": [],
    }

    lines: List[str] = []
    lines.append(f"INTERBRANCH MOVEMENT REPORT | DATE: {report_date}")
    lines.append("=" * 80)

    items = []
    for r in journal:
        d = str(r.get("execution_date", ""))[:10]
        if d != report_date:
            continue

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

    pack["items"] = items

    if not items:
        lines.append("NIL: No interbranch items detected for this date.")
        return pack, lines

    grouped = defaultdict(list)
    for it in items:
        k = f"{it.get('_maker_branch')} -> {it.get('_domiciled_branch')}"
        grouped[k].append(it)

    for k in sorted(grouped.keys()):
        lines.append("")
        lines.append("-" * 80)
        lines.append(f"ROUTE: {k}")
        lines.append("-" * 80)
        for it in grouped[k]:
            lines.append(json.dumps(it, ensure_ascii=False))

    return pack, lines


def main():
    # default: previous working day
    if len(sys.argv) == 2:
        report_date = sys.argv[1].strip()
    else:
        report_date = previous_working_day().isoformat()

    journal = load_journal()
    org = _load_json(ORG_FILE)
    account_master = _load_json(ACCT_FILE)

    user_index = build_user_index(org)

    s_pack, s_lines = report_supervisor_daily_review(
        journal=journal,
        org=org,
        user_index=user_index,
        report_date=report_date,
    )

    g_pack, g_lines = report_gl_daily_movement(
        journal=journal,
        account_master=account_master,
        report_date=report_date,
    )

    i_pack, i_lines = report_interbranch(
        journal=journal,
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

    all_lines: List[str] = []
    all_lines.append(f"SUPERVISORY CONTROL PACK | DATE: {report_date}")
    all_lines.append("=" * 80)
    all_lines.append("")
    all_lines.append("\f")
    all_lines.extend(g_lines)
    all_lines.append("\f")
    all_lines.extend(i_lines)
    all_lines.append("\f")
    all_lines.extend(s_lines)

    write_text(out_txt, all_lines)

    print("Supervisory Control Pack generated:")
    print(out_json)
    print(out_txt)


if __name__ == "__main__":
    main()