"""
tools/run_eod_snapshot_by_dimension.py

EOD Snapshot grouped by dimension.

Usage:
  python tools/run_eod_snapshot_by_dimension.py 2026-02-01 maker_user_id
  python tools/run_eod_snapshot_by_dimension.py 2026-02-01 dims.branch
  python tools/run_eod_snapshot_by_dimension.py 2026-02-01 dims.country
"""

from __future__ import annotations

import sys
import json
import hashlib
from decimal import Decimal
from pathlib import Path
from collections import defaultdict

JOURNAL_FILE = Path("audit_logs") / "journal.jsonl"
OUT_DIR = Path("audit_logs") / "eod_snapshots"


def dec(x) -> Decimal:
    return Decimal(str(x))


def apply_line(tb: dict[str, Decimal], acct: str, side: str, amt: Decimal) -> None:
    cur = tb.get(acct, Decimal("0"))
    if side == "DR":
        cur += amt
    elif side == "CR":
        cur -= amt
    else:
        raise ValueError("Invalid side: must be DR/CR")
    tb[acct] = cur


def stable_hash(obj: dict) -> str:
    s = json.dumps(obj, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def get_group(row: dict, key: str) -> str:
    if key == "maker_user_id":
        return row.get("maker_user_id") or "UNKNOWN_MAKER"
    if key == "checker_user_id":
        return row.get("checker_user_id") or "UNKNOWN_CHECKER"
    if key.startswith("dims."):
        k = key.split(".", 1)[1]
        dims = row.get("dims") or {}
        v = dims.get(k)
        return str(v) if v else f"UNKNOWN_{k.upper()}"
    return "UNKNOWN_KEY"


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: python tools/run_eod_snapshot_by_dimension.py YYYY-MM-DD <maker_user_id|checker_user_id|dims.branch|dims.country|...>")
        return 2

    day = sys.argv[1].strip()
    group_key = sys.argv[2].strip()

    if not JOURNAL_FILE.exists():
        print(f"Journal file not found: {JOURNAL_FILE}")
        return 1

    system_tb: dict[str, Decimal] = {}
    grouped_tb: dict[str, dict[str, Decimal]] = defaultdict(dict)

    journal_count = 0
    groups_seen = set()

    with JOURNAL_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("execution_date") != day:
                continue

            journal_count += 1
            grp = get_group(r, group_key)
            groups_seen.add(grp)

            acct = str(r.get("account_no", "")).strip()
            side = str(r.get("side", "")).strip().upper()
            amt = dec(r.get("amount", "0"))

            apply_line(system_tb, acct, side, amt)
            apply_line(grouped_tb[grp], acct, side, amt)

    snapshot = {
        "schema": "CSS_EOD_SNAPSHOT_DIM_V1",
        "date": day,
        "group_key": group_key,
        "journal_count": journal_count,
        "group_count": len(groups_seen),
        "trial_balance_system": {a: str(v) for a, v in sorted(system_tb.items())},
        "trial_balance_by_group": {
            g: {a: str(v) for a, v in sorted(tb.items())}
            for g, tb in sorted(grouped_tb.items())
        },
    }

    snapshot["integrity_hash"] = stable_hash(snapshot)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"EOD_{day}_BY_{group_key.replace('.','_')}.json"
    out.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"WROTE: {out}")
    print(f"JOURNAL_COUNT: {journal_count} | GROUPS: {len(groups_seen)}")
    print(f"INTEGRITY_HASH: {snapshot['integrity_hash']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())