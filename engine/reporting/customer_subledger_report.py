"""
Customer Subledger Report – Phase 1C (Auto-Discover Journal)
Capital Strata Systems

Fix:
- Do NOT assume backend/data/journal.jsonl exists.
- Auto-discover primary journal JSONL in repo.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parents[2]


def _safe_date_str(s: Any) -> Optional[str]:
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
        return date(int(s[0:4]), int(s[5:7]), int(s[8:10]))
    except Exception:
        return None


def _in_range(d: Optional[str], from_date: Optional[str], to_date: Optional[str]) -> bool:
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
    out: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                v = json.loads(line)
                if isinstance(v, dict):
                    out.append(v)
            except Exception:
                continue
    return out


def _pick(d: Dict[str, Any], keys: List[str]) -> Any:
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def _extract_lines(entry: Dict[str, Any]) -> List[Dict[str, Any]]:
    for key in ("lines", "entries", "postings", "legs"):
        v = entry.get(key)
        if isinstance(v, list) and v:
            return [x for x in v if isinstance(x, dict)]
    return [entry]


def _line_matches_customer(line: Dict[str, Any], customer_id: str) -> bool:
    candidates = [
        "customer_id", "entity_id", "counterparty_id", "party_id",
        "client_id", "debtor_id", "subledger_id",
    ]
    cid = str(customer_id).strip()
    for k in candidates:
        if str(line.get(k, "")).strip() == cid:
            return True
    for nest in ("entity", "customer", "party", "counterparty"):
        v = line.get(nest)
        if isinstance(v, dict) and str(v.get("id", "")).strip() == cid:
            return True
    return False


def _extract_dr_cr(line: Dict[str, Any]) -> Tuple[float, float]:
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

    if d == 0.0 and c == 0.0:
        amt = _pick(line, ["amount", "signed_amount", "net_amount", "value"])
        a = _to_float(amt)
        if a >= 0:
            d = a
        else:
            c = abs(a)

    return d, c


def _discover_primary_journal() -> Path:
    """
    Try common locations first; if missing, scan repo for candidate JSONL.
    """
    tried = [
        REPO_ROOT / "backend" / "data" / "journal.jsonl",
        REPO_ROOT / "backend" / "data" / "journals.jsonl",
        REPO_ROOT / "backend" / "journal.jsonl",
        REPO_ROOT / "data" / "journal.jsonl",
        REPO_ROOT / "audit_logs" / "journal.jsonl",
    ]
    for p in tried:
        if p.exists():
            return p

    # Scan for jsonl candidates (limit scope for speed)
    candidates: List[Path] = []
    for base in [REPO_ROOT / "backend", REPO_ROOT / "audit_logs", REPO_ROOT / "data", REPO_ROOT]:
        if base.exists():
            for p in base.rglob("*.jsonl"):
                name = p.name.lower()
                if "journal" in name or "posting" in name:
                    candidates.append(p)

    # If still nothing, allow any jsonl as last resort
    if not candidates:
        for p in REPO_ROOT.rglob("*.jsonl"):
            candidates.append(p)

    if candidates:
        # choose most recently modified
        candidates.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        return candidates[0]

    raise FileNotFoundError(
        "No journal jsonl found. Tried common paths and scanned repo for *.jsonl."
    )


def _override_log_path() -> Optional[Path]:
    p = REPO_ROOT / "audit_logs" / "overrides.jsonl"
    return p if p.exists() else None


def generate_customer_subledger(
    customer_id: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> Dict[str, Any]:

    primary_path = _discover_primary_journal()
    primary_rows = list(_read_jsonl(primary_path))

    ov_path = _override_log_path()
    override_rows = list(_read_jsonl(ov_path)) if ov_path else []
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

    rows.sort(key=lambda r: (r.get("date") or "0000-00-00", str(r.get("journal_id") or "")))

    running2 = 0.0
    for r in rows:
        running2 += float(r.get("debit", 0.0)) - float(r.get("credit", 0.0))
        r["running_balance"] = round(running2, 2)

    return {
        "customer_id": customer_id,
        "from_date": from_date,
        "to_date": to_date,
        "source": {
            "primary_journal": str(primary_path.relative_to(REPO_ROOT)),
            "override_log": str(ov_path.relative_to(REPO_ROOT)) if ov_path else None,
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