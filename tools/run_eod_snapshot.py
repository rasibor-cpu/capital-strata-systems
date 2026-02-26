"""
tools/run_eod_snapshot.py

End-of-Day Snapshot Engine – Phase 14c.2
- Reads journal.jsonl for a given date
- Builds per-user trial balances (from journal entries)
- Builds system-wide trial balance
- Writes snapshot JSON with integrity hash

Usage:
  python tools/run_eod_snapshot.py 2026-02-01
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
        raise ValueError("Invalid side in journal: must be DR or CR")
    tb[acct] = cur


def stable_hash(obj: dict) -> str:
    s = json.dumps(obj, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python tools/run_eod_snapshot.py YYYY-MM-DD")
        return 2

    day = sys.argv[1].strip()
    if not JOURNAL_FILE.exists():
        print(f"Journal file not found: {JOURNAL_FILE}")
        return 1

    # per-user and system TB
    per_user_tb: dict[str, dict[str, Decimal]] = defaultdict(dict)
    system_tb: dict[str, Decimal] = {}

    journal_count = 0
    users_seen = set()

    with JOURNAL_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("execution_date") != day:
                continue

            journal_count += 1

            user = r.get("maker_user_id") or "UNKNOWN_MAKER"
            users_seen.add(user)

            acct = str(r.get("account_no", "")).strip()
            side = str(r.get("side", "")).strip().upper()
            amt = dec(r.get("amount", "0"))

            apply_line(per_user_tb[user], acct, side, amt)
            apply_line(system_tb, acct, side, amt)

    # Convert Decimals to strings for JSON
    per_user_out = {
        u: {acct: str(val) for acct, val in sorted(tb.items())}
        for u, tb in sorted(per_user_tb.items())
    }
    system_out = {acct: str(val) for acct, val in sorted(system_tb.items())}

    snapshot = {
        "schema": "CSS_EOD_SNAPSHOT_V1",
        "date": day,
        "journal_count": journal_count,
        "user_count": len(users_seen),
        "trial_balance_system": system_out,
        "trial_balance_by_user": per_user_out,
    }

    snapshot["integrity_hash"] = stable_hash(snapshot)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"EOD_{day}.json"
    out.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"WROTE: {out}")
    print(f"JOURNAL_COUNT: {journal_count} | USERS: {len(users_seen)}")
    print(f"INTEGRITY_HASH: {snapshot['integrity_hash']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())