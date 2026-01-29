"""
REA Capital — Counters Summary (Canonical)
=========================================

Task 6.3: Define and implement the standard counters/metrics summary format.

Usage:
------
from counters_summary import build_summary_text, print_summary

summary = build_summary_text(counters=my_counters, meta={"symbol":"EURUSD", "mode":"replay"})
print(summary)

This module is intentionally dependency-light and safe to import anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class SummaryGate:
    """
    A 'gate' is a pass/fail condition that must hold for the run to be considered healthy.
    """
    name: str
    passed: bool
    detail: str


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_int(x: Any, default: int = 0) -> int:
    try:
        if x is None:
            return default
        if isinstance(x, bool):
            return int(x)
        return int(x)
    except Exception:
        return default


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def _pct(n: int, d: int) -> str:
    if d <= 0:
        return "0.00%"
    return f"{(100.0 * n / d):.2f}%"


def _sorted_items(d: Dict[str, Any]) -> List[Tuple[str, Any]]:
    return sorted(d.items(), key=lambda kv: kv[0].lower())


def reconcile_totals(
    counters: Dict[str, Any],
    total_key: str,
    component_keys: Iterable[str],
) -> SummaryGate:
    """
    Ensures total_key == sum(component_keys). Missing keys treated as 0.
    """
    total = _safe_int(counters.get(total_key, 0))
    comp_sum = sum(_safe_int(counters.get(k, 0)) for k in component_keys)
    passed = (total == comp_sum)
    detail = f"{total_key}={total} vs components_sum={comp_sum} ({', '.join(component_keys)})"
    return SummaryGate(name=f"Reconcile: {total_key}", passed=passed, detail=detail)


def monotonic_nonnegative_gate(counters: Dict[str, Any]) -> SummaryGate:
    """
    Basic integrity gate: no counter should be negative.
    """
    negatives = [k for k, v in counters.items() if isinstance(v, (int, float)) and _safe_float(v) < 0]
    passed = (len(negatives) == 0)
    detail = "no negative counters" if passed else f"negative counters found: {', '.join(negatives)}"
    return SummaryGate(name="Integrity: nonnegative counters", passed=passed, detail=detail)


def build_default_gates(counters: Dict[str, Any]) -> List[SummaryGate]:
    """
    Default gates aligned to Task 6.2 spec. These are conservative and may be extended by callers.
    """
    bars_5m = _safe_int(counters.get("bars_5m", counters.get("bars_5m_total", 0)))
    allow = _safe_int(counters.get("regime_allow", counters.get("regime_allow_count", 0)))
    block = _safe_int(counters.get("regime_block", counters.get("regime_block_count", 0)))
    total_regime = allow + block

    gates: List[SummaryGate] = []
    gates.append(monotonic_nonnegative_gate(counters))

    # Regime gate readiness
    gates.append(
        SummaryGate(
            name="Gate: sufficient 5m bars (>=40)",
            passed=(bars_5m >= 40),
            detail=f"bars_5m={bars_5m}",
        )
    )

    # Regime allow ratio cap (<= 40%)
    allow_ratio = (allow / total_regime) if total_regime > 0 else 0.0
    gates.append(
        SummaryGate(
            name="Gate: regime allow ratio <= 0.40",
            passed=(allow_ratio <= 0.40),
            detail=f"allow={allow}, block={block}, allow_ratio={allow_ratio:.4f}",
        )
    )

    # Replay stability (if provided)
    exc = _safe_int(counters.get("exceptions", counters.get("exceptions_count", 0)))
    nan = _safe_int(counters.get("nan_or_inf", counters.get("nan_or_inf_count", 0)))
    late = _safe_int(counters.get("late_bar_events", 0))

    gates.append(
        SummaryGate(
            name="Gate: exceptions == 0",
            passed=(exc == 0),
            detail=f"exceptions={exc}",
        )
    )
    gates.append(
        SummaryGate(
            name="Gate: nan/inf == 0",
            passed=(nan == 0),
            detail=f"nan_or_inf={nan}",
        )
    )
    gates.append(
        SummaryGate(
            name="Gate: late bars == 0",
            passed=(late == 0),
            detail=f"late_bar_events={late}",
        )
    )

    return gates


def build_summary_text(
    counters: Dict[str, Any],
    meta: Optional[Dict[str, Any]] = None,
    gates: Optional[List[SummaryGate]] = None,
    include_raw: bool = True,
) -> str:
    """
    Canonical summary format. Prints:
    - header with UTC timestamp
    - meta fields (symbol/mode/etc)
    - key counters highlights
    - gates pass/fail
    - optional raw counters listing (sorted)
    """
    meta = meta or {}
    gates = gates or build_default_gates(counters)

    # Highlights (best-effort keys; callers may pass richer meta)
    bars_1m = _safe_int(counters.get("bars_1m", counters.get("bars_1m_total", 0)))
    bars_5m = _safe_int(counters.get("bars_5m", counters.get("bars_5m_total", 0)))

    allow = _safe_int(counters.get("regime_allow", counters.get("regime_allow_count", 0)))
    block = _safe_int(counters.get("regime_block", counters.get("regime_block_count", 0)))
    total_regime = allow + block

    signals = _safe_int(counters.get("signals_generated", counters.get("signals_generated_total", 0)))
    suppressed = _safe_int(counters.get("signals_suppressed", counters.get("signals_suppressed_by_regime", 0)))

    lines: List[str] = []
    lines.append("=== REA COUNTERS SUMMARY (CANONICAL) ===")
    lines.append(f"utc_time: {_now_utc_iso()}")

    # Meta
    if meta:
        lines.append("--- meta ---")
        for k, v in _sorted_items(meta):
            lines.append(f"{k}: {v}")

    # Highlights
    lines.append("--- highlights ---")
    lines.append(f"bars_1m_total: {bars_1m}")
    lines.append(f"bars_5m_total: {bars_5m}")
    lines.append(f"regime_allow: {allow}")
    lines.append(f"regime_block: {block}")
    lines.append(f"regime_allow_ratio: {_pct(allow, total_regime)}")
    lines.append(f"signals_generated_total: {signals}")
    lines.append(f"signals_suppressed_by_regime: {suppressed}")

    # Gates
    lines.append("--- gates ---")
    passed_all = True
    for g in gates:
        status = "PASS" if g.passed else "FAIL"
        passed_all = passed_all and g.passed
        lines.append(f"[{status}] {g.name} :: {g.detail}")

    lines.append(f"overall_status: {'PASS' if passed_all else 'FAIL'}")

    # Raw counters
    if include_raw:
        lines.append("--- raw_counters (sorted) ---")
        for k, v in _sorted_items(counters):
            lines.append(f"{k}: {v}")

    return "\n".join(lines)


def print_summary(
    counters: Dict[str, Any],
    meta: Optional[Dict[str, Any]] = None,
    gates: Optional[List[SummaryGate]] = None,
    include_raw: bool = True,
) -> None:
    """
    Convenience wrapper.
    """
    print(build_summary_text(counters=counters, meta=meta, gates=gates, include_raw=include_raw))


if __name__ == "__main__":
    # Minimal self-test (safe to run)
    demo = {
        "bars_1m_total": 260,
        "bars_5m_total": 52,
        "regime_allow_count": 13,
        "regime_block_count": 39,
        "signals_generated_total": 0,
        "signals_suppressed_by_regime": 0,
        "exceptions_count": 0,
        "nan_or_inf_count": 0,
        "late_bar_events": 0,
    }
    print_summary(demo, meta={"mode": "demo"})