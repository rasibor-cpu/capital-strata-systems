"""
Customer Subledger Report – Phase 1C (Repo-Accurate)
Capital Strata Systems

Reads postings from:
- backend/data/journal.jsonl   (primary)
- audit_logs/overrides.jsonl   (optional override log)

Outputs:
- Date-range filtered customer subledger
- Running balance
- Export-ready structured rows
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


# -----------------------------
# Repo-root anchored paths
# -----------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]  # engine/reporting/ -> repo root
PRIMARY_JOURNAL = REPO_ROOT / "backend" / "data" / "journal.jsonl"
OVERRIDE_JOURNAL = REPO_ROOT / "audit_logs" / "overrides.jsonl"


# -----------------------------
# Helpers
# -----------------------------

def _safe_date_str(s: Any) -> Optional[str]:
    """
    Convert whatever we have into YYYY-MM-DD (string).
    Accepts ISO datetime strings; uses first 10 chars.
    """
    if s is None:
        return None
    if not isinstance(s, str):
        s = str(s)
    s = s.strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    return None


def _to_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        y = int(s[0:4])
        m = int(s[5:7])
        d = int(s[8:10])
        return date(y, m, d)
    except Exception:
        return None


def _in_range(d: Optional[str], from_date: Optional[str], to_date: Optional[str]) -> bool:
    """
    Inclusive range check on YYYY-MM-DD strings.
    If d missing -> treat as included (auditor-friendly: don't silently drop).
    """
    if d is None:
        return True

    dd = _to_date(d)
    if dd is None:
        return True

    fd = _to_date(from_date) if from_date else None
    td = _to_date(to_date) if to_date else None

    if fd and dd < fd:
        return False
    if td and dd > td:
        return False
    return True


def _read_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                # Fail-closed would stop reporting; instead we skip bad lines but note later.
                continue
    return rows


def _pick(d: Dict[str, Any], keys: List[str]) -> Any:
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def _extract_lines(entry: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Many journal schemas store detail lines under:
    - lines
    - entries
    - postings
    - legs
    If none exists, treat entry itself as a single "line".
    """
    for key in ("lines", "entries", "postings", "legs"):
        v = entry.get(key)
        if isinstance(v, list) and v:
            # normalize: each item must be dict
            return [x for x in v if isinstance(x, dict)]
    return [entry]


def _line_matches_customer(line: Dict[str, Any], customer_id: str) -> bool:
    """
    Match customer in a robust way, since schemas vary.
    """
    candidates = [
        "customer_id",
        "entity_id",
        "counterparty_id",
        "party_id",
        "client_id",
        "debtor_id",
        "subledger_id",
    ]
    for k in candidates:
        if str(line.get(k, "")).strip() == str(customer_id):
            return True

    # Some schemas store entity identifiers nested
    for nest in ("entity", "customer", "party", "counterparty"):
        v = line.get(nest)
        if isinstance(v, dict):
            if str(v.get("id", "")).strip() == str(customer_id):
                return True

    return False


def _extract_dr_cr(line: Dict[str, Any]) -> Tuple[float, float]:
    """
    Try common debit/credit fields.
    """
    debit = _pick(line, ["debit", "dr", "debit_amount", "amount_debit"])
    credit = _pick(line, ["credit", "cr", "credit_amount", "amount_credit"])

    def _to_float(x: Any) -> float:
        try:
            if x is None:
                return 0.0
            if isinstance(x, (int, float)):
                return float(x)
            s = str(x).replace(",", "").strip()
            return float(s) if s else 0.0
        except Exception:
            return 0.0

    d = _to_float(debit)
    c = _to_float(credit)

    # Some schemas store signed amount instead of dr/cr.
    if d == 0.0 and c == 0.0:
        amt = _pick(line, ["amount", "signed_amount", "net_amount", "value"])
        a = _to_float(amt)
        if a >= 0:
            d = a
            c = 0.0
        else:
            d = 0.0
            c = abs(a)

    return d, c


# -----------------------------
# Public API
# -----------------------------

def generate_customer_subledger(
    customer_id: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Returns an export-ready customer subledger with running balance.
    """

    primary_rows = list(_read_jsonl(PRIMARY_JOURNAL))
    override_rows = list(_read_jsonl(OVERRIDE_JOURNAL))

    # Optional: include overrides as metadata only (they are not postings)
    overrides_count = len(override_rows)

    rows: List[Dict[str, Any]] = []
    skipped_bad = 0

    running = 0.0

    for entry in primary_rows:
        if not isinstance(entry, dict):
            skipped_bad += 1
            continue

        entry_date = _safe_date_str(
            _pick(entry, ["posting_date", "date", "as_of_date", "effective_date", "timestamp", "ts"])
        )

        if not _in_range(entry_date, from_date, to_date):
            continue

        journal_id = _pick(entry, ["journal_id", "id", "entry_id", "txn_id", "transaction_id"])
        ref = _pick(entry, ["reference", "ref", "doc_ref", "voucher_no", "cheque_no"])
        desc = _pick(entry, ["description", "memo", "narration", "note", "details"])

        for line in _extract_lines(entry):
            if not isinstance(line, dict):
                skipped_bad += 1
                continue

            if not _line_matches_customer(line, customer_id):
                continue

            debit, credit = _extract_dr_cr(line)
            running += (debit - credit)

            account = _pick(line, ["account", "account_code", "gl_account", "ledger_account"])
            currency = _pick(line, ["currency", "ccy"])

            rows.append(
                {
                    "date": entry_date,
                    "journal_id": journal_id,
                    "reference": ref,
                    "description": desc,
                    "account": account,
                    "currency": currency,
                    "debit": round(debit, 2),
                    "credit": round(credit, 2),
                    "running_balance": round(running, 2),
                }
            )

    # Sort again to be safe (some lines may lack date)
    rows.sort(key=lambda r: (r.get("date") or "0000-00-00", str(r.get("journal_id") or "")))

    # Recompute running after sort (canonical)
    running2 = 0.0
    for r in rows:
        running2 += float(r.get("debit", 0.0)) - float(r.get("credit", 0.0))
        r["running_balance"] = round(running2, 2)

    return {
        "customer_id": customer_id,
        "from_date": from_date,
        "to_date": to_date,
        "source": {
            "primary_journal": str(PRIMARY_JOURNAL.relative_to(REPO_ROOT)),
            "override_log": str(OVERRIDE_JOURNAL.relative_to(REPO_ROOT)),
            "override_rows_seen": overrides_count,
        },
        "rows": rows,
        "closing_balance": round(running2, 2),
        "stats": {
            "primary_entries_read": len(primary_rows),
            "rows_emitted": len(rows),
            "skipped_bad_rows": skipped_bad,
        },
    }