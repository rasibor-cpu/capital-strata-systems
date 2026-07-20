"""Phase 179 — deterministic priority ordering and duplicate suppression."""

from __future__ import annotations

from typing import Any

_PRIORITY_RANK = {
    "CRITICAL": 0,
    "HIGH": 1,
    "MEDIUM": 2,
    "LOW": 3,
    "INFO": 4,
}


def priority_sort_key(item: dict[str, Any]) -> tuple:
    pri = str(item.get("priority") or "INFO").upper()
    return (
        _PRIORITY_RANK.get(pri, 99),
        int(item.get("rank") or 0),
        str(item.get("code") or ""),
        str(item.get("title") or ""),
    )


def dedupe_by_code(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep first occurrence of each code (highest priority should be appended first)."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").strip()
        if not code or code in seen:
            continue
        seen.add(code)
        out.append(dict(item))
    out.sort(key=priority_sort_key)
    # Re-number ranks after sort for stable presentation
    for idx, item in enumerate(out, start=1):
        item["rank"] = idx
    return out


def map_action_priority(priority: Any) -> str:
    """Map Phase 178 numeric action priority to EDI bands."""
    try:
        p = int(priority)
    except (TypeError, ValueError):
        return "MEDIUM"
    if p <= 12:
        return "CRITICAL"
    if p <= 16:
        return "HIGH"
    if p <= 25:
        return "MEDIUM"
    if p <= 40:
        return "LOW"
    return "INFO"
