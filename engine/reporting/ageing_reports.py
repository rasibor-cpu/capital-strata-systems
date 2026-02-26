"""
engine/reporting/ageing_reports.py

Ageing Reports (Auditor-Grade, Reproducible)
--------------------------------------------
Goal: Provide AR/AP/GL ageing views that can be printed via the global report gateway.

Important:
- This module is deliberately conservative + dependency-light.
- It expects "ledger-like" rows passed in via filters OR via a store adapter later.
- For Phase 15: we implement the engine + formatter now; wiring to actual stores is next.

Supported:
- AR ageing (customer receivables)
- AP ageing (vendor payables)
- GL ageing (accounts, incl suspense/sundry buckets)

Buckets default:
0-30, 31-60, 61-90, 91-180, 181+
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date
from typing import Any, Dict, List, Tuple, Optional


DEFAULT_BUCKETS = [(0, 30), (31, 60), (61, 90), (91, 180), (181, 10_000)]


def _parse_ymd(d: str) -> date:
    return datetime.strptime(d, "%Y-%m-%d").date()


def _as_of_date(filters: Dict[str, Any], as_of_date: Optional[str]) -> date:
    if as_of_date:
        return _parse_ymd(as_of_date)
    f = filters.get("as_of_date")
    if isinstance(f, str) and f:
        return _parse_ymd(f)
    # default: today (UTC date)
    return datetime.utcnow().date()


def _buckets(filters: Dict[str, Any]) -> List[Tuple[int, int]]:
    """
    filters['buckets'] can be:
      - list of [start,end] pairs, e.g. [[0,30],[31,60],...]
    """
    b = filters.get("buckets")
    if isinstance(b, list) and b:
        out: List[Tuple[int, int]] = []
        for item in b:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                out.append((int(item[0]), int(item[1])))
        if out:
            return out
    return list(DEFAULT_BUCKETS)


def _bucket_label(lo: int, hi: int) -> str:
    if hi >= 10_000:
        return f"{lo}+"
    return f"{lo}-{hi}"


@dataclass(frozen=True)
class AgeingRow:
    entity_id: str          # customer_id / vendor_id / account_code
    entity_name: str        # display name
    currency: str
    doc_date: date
    amount: float           # positive absolute exposure (already normalized)


def _load_rows(filters: Dict[str, Any]) -> List[AgeingRow]:
    """
    Phase 15 approach:
    - Allow caller to pass rows directly for reproducible prints.
      filters['rows'] is a list of dicts with keys:
        entity_id, entity_name, currency, doc_date (YYYY-MM-DD), amount
    """
    rows = filters.get("rows")
    if not isinstance(rows, list):
        return []

    out: List[AgeingRow] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        try:
            out.append(
                AgeingRow(
                    entity_id=str(r.get("entity_id", "")),
                    entity_name=str(r.get("entity_name", "")),
                    currency=str(r.get("currency", "")),
                    doc_date=_parse_ymd(str(r.get("doc_date"))),
                    amount=float(r.get("amount", 0.0)),
                )
            )
        except Exception:
            continue

    # Drop invalid
    out = [x for x in out if x.entity_id and x.currency and x.amount != 0.0]
    return out


def compute_ageing(filters: Dict[str, Any], as_of: date) -> Dict[str, Any]:
    """
    Returns structured ageing:
      - per entity totals by bucket + total
      - portfolio totals by bucket + total
    """
    buckets = _buckets(filters)
    rows = _load_rows(filters)

    # Optional filters
    currency_filter = filters.get("currency")
    if isinstance(currency_filter, str) and currency_filter:
        rows = [r for r in rows if r.currency == currency_filter]

    # Build
    entity_map: Dict[str, Dict[str, Any]] = {}
    portfolio_totals: Dict[str, float] = {_bucket_label(lo, hi): 0.0 for lo, hi in buckets}
    portfolio_totals["TOTAL"] = 0.0

    for r in rows:
        age_days = (as_of - r.doc_date).days
        if age_days < 0:
            # future-dated docs go to 0-30 bucket (auditor-safe default)
            age_days = 0

        bucket_name = None
        for lo, hi in buckets:
            if lo <= age_days <= hi:
                bucket_name = _bucket_label(lo, hi)
                break
        if bucket_name is None:
            bucket_name = _bucket_label(buckets[-1][0], buckets[-1][1])

        ent = entity_map.setdefault(
            r.entity_id,
            {
                "entity_id": r.entity_id,
                "entity_name": r.entity_name,
                "currency": r.currency,
                "buckets": {_bucket_label(lo, hi): 0.0 for lo, hi in buckets},
                "total": 0.0,
                "lines": 0,
            },
        )

        ent["buckets"][bucket_name] += float(r.amount)
        ent["total"] += float(r.amount)
        ent["lines"] += 1

        portfolio_totals[bucket_name] += float(r.amount)
        portfolio_totals["TOTAL"] += float(r.amount)

    # Sort entities by total desc
    entities = sorted(entity_map.values(), key=lambda x: float(x["total"]), reverse=True)

    return {
        "as_of": as_of.isoformat(),
        "bucket_scheme": [_bucket_label(lo, hi) for lo, hi in buckets],
        "entities": entities,
        "portfolio_totals": portfolio_totals,
        "row_count": len(rows),
    }


def format_ageing_report(title: str, data: Dict[str, Any], max_entities: int = 50) -> str:
    """
    Human-readable print format (auditor-friendly).
    """
    lines: List[str] = []
    lines.append(f"=== {title} ===")
    lines.append(f"As-of date          : {data.get('as_of')}")
    lines.append(f"Rows processed      : {data.get('row_count')}")
    lines.append("")

    scheme = data.get("bucket_scheme") or []
    totals = data.get("portfolio_totals") or {}

    lines.append("Portfolio totals:")
    for b in scheme:
        lines.append(f"  {b:10s}: {totals.get(b, 0.0):,.2f}")
    lines.append(f"  {'TOTAL':10s}: {totals.get('TOTAL', 0.0):,.2f}")
    lines.append("")

    entities = data.get("entities") or []
    lines.append(f"Top entities (max {max_entities}):")
    header = "  " + " | ".join([f"{b:>10s}" for b in scheme] + [f"{'TOTAL':>10s}"]) + " | Entity"
    lines.append(header)
    lines.append("  " + "-" * (len(header) - 2))

    for ent in entities[:max_entities]:
        bmap = ent.get("buckets") or {}
        row = "  " + " | ".join([f"{float(bmap.get(b, 0.0)):>10,.2f}" for b in scheme] + [f"{float(ent.get('total', 0.0)):>10,.2f}"])
        row += f" | {ent.get('entity_name','')} ({ent.get('entity_id','')}) [{ent.get('currency','')}]"
        lines.append(row)

    if len(entities) > max_entities:
        lines.append("")
        lines.append(f"... {len(entities) - max_entities} more entities omitted (use filters/max_entities).")

    return "\n".join(lines)