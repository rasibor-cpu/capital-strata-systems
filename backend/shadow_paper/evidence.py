"""Independent verification and acceptance metrics for a shadow paper journal.

Everything here is recomputed from the journal alone, so a reviewer can check a
shakedown without trusting the runner's in-memory state.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.shadow_paper.journal import JournalIntegrityError, read_journal
from backend.shadow_paper.market_data import MAX_QUOTE_AGE_SECONDS

REQUIRED_ENTRY_STAGES = (
    "runner_entry_permission",
    "signal_direction",
    "min_signal_strength",
    "no_pyramiding",
    "regime_gate",
    "r7_unified_trade_gate",
    "r14f_profitability_gate",
    "anti_bleed_guard",
    "execution_gate",
    "portfolio_capital_controller",
    "anti_bleed_minimum_size",
)


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def summarize(journal_path: Path) -> dict[str, Any]:
    try:
        records = read_journal(Path(journal_path))
    except JournalIntegrityError as exc:
        return {"journal_integrity": "FAIL", "integrity_error": str(exc)}

    by_type = Counter(r["type"] for r in records)
    ticks = [r for r in records if r["type"] == "MARKET_TICK"]
    rejections = [r for r in records if r["type"] == "MARKET_DATA_REJECTED"]
    tick_by_seq = {r["seq"]: r for r in ticks}

    # Feed freshness and continuity
    max_gap: dict[str, float] = {}
    last_seen: dict[str, datetime] = {}
    max_age = 0.0
    for r in ticks:
        p = r["payload"]
        received = _ts(p["received_at_utc"])
        inst = p["instrument"]
        if inst in last_seen:
            max_gap[inst] = max(max_gap.get(inst, 0.0), (received - last_seen[inst]).total_seconds())
        last_seen[inst] = received
        max_age = max(max_age, float(p["age_seconds"]))
    attempts = len(ticks) + len(rejections) + by_type.get("MARKET_DATA_DUPLICATE", 0)

    # Decisions must reference an accepted, fresh tick
    decisions = [r for r in records if r["type"] == "GATE_DECISION"]
    stale_decisions = 0
    for r in decisions:
        tick = tick_by_seq.get(r["payload"].get("tick_seq"))
        if tick is None or float(tick["payload"]["age_seconds"]) > MAX_QUOTE_AGE_SECONDS:
            stale_decisions += 1

    # Trade-gate enforcement: every open preceded by an ENTRY_ALLOWED with all stages passed
    allowed_by_tick = {
        (r["payload"]["instrument"], r["payload"]["tick_seq"]): r
        for r in decisions if r["payload"]["final"] == "ENTRY_ALLOWED"
    }
    opens = [r for r in records if r["type"] == "PAPER_POSITION_OPENED"]
    closes = [r for r in records if r["type"] == "PAPER_POSITION_CLOSED"]
    ungated_opens = []
    undersized_opens = []
    for r in opens:
        p = r["payload"]
        decision = allowed_by_tick.get((p["instrument"], p["tick_seq"]))
        stages = {s["stage"]: s["passed"] for s in (decision or {}).get("payload", {}).get("stages", [])}
        if decision is None or any(stages.get(name) is not True for name in REQUIRED_ENTRY_STAGES):
            ungated_opens.append(p["position_id"])
        if float(p["notional"]) < 50.0 - 1e-9:
            undersized_opens.append(p["position_id"])

    # Lifecycle and accounting
    open_ids = [r["payload"]["position_id"] for r in opens]
    close_ids = [r["payload"]["position_id"] for r in closes]
    orphan_closes = sorted(set(close_ids) - set(open_ids))
    duplicate_closes = sorted(k for k, v in Counter(close_ids).items() if v > 1)
    still_open = sorted(set(open_ids) - set(close_ids))
    lifecycle_errors = []
    for r in closes:
        p = r["payload"]
        if p["side"] == "BUY":
            gross = (p["exit_fill_price"] - p["entry_fill_price"]) * p["quantity"]
        else:
            gross = (p["entry_fill_price"] - p["exit_fill_price"]) * p["quantity"]
        net = gross - p["entry_fee"] - p["exit_fee"]
        if abs(net - p["realized_pnl_net"]) > 1e-6:
            lifecycle_errors.append(p["position_id"])
    for r in opens:
        p = r["payload"]
        if abs(p["quantity"] * p["entry_fill_price"] - p["notional"]) > 1e-6:
            lifecycle_errors.append(p["position_id"])
    closes_without_real_tick = sorted(
        r["payload"]["position_id"] for r in closes if r["payload"].get("tick_seq") not in tick_by_seq
    )
    realized_recomputed = sum(float(r["payload"]["realized_pnl_net"]) for r in closes)
    snapshots = [r for r in records if r["type"] == "PNL_SNAPSHOT"]
    last_snapshot_realized = snapshots[-1]["payload"]["realized_pnl_net"] if snapshots else 0.0

    # Stability / restarts: a "session" is a RUN_STARTED segment that ran at least one cycle,
    # so preflight-only starts in the same evidence folder are not counted as restarts.
    starts = [r for r in records if r["type"] == "RUN_STARTED"]
    sessions_with_cycles = 0
    in_session_has_cycle = False
    for r in records:
        if r["type"] == "RUN_STARTED":
            sessions_with_cycles += int(in_session_has_cycle)
            in_session_has_cycle = False
        elif r["type"] == "PNL_SNAPSHOT":
            in_session_has_cycle = True
    sessions_with_cycles += int(in_session_has_cycle)
    starts_passed = sum(1 for r in starts if r["payload"]["preflight"]["passed"])
    span_seconds = (_ts(records[-1]["ts_utc"]) - _ts(records[0]["ts_utc"])).total_seconds() if records else 0.0
    interval = starts[0]["payload"]["config"]["bar_interval_seconds"] if starts else None

    return {
        "journal_integrity": "PASS",
        "records": len(records),
        "event_counts": dict(sorted(by_type.items())),
        "feed": {
            "attempts": attempts,
            "accepted": len(ticks),
            "acceptance_rate": round(len(ticks) / attempts, 6) if attempts else None,
            "rejections_by_reason": dict(Counter(r["payload"]["reason"] for r in rejections)),
            "max_gap_seconds_by_instrument": {k: round(v, 3) for k, v in max_gap.items()},
            "max_accepted_quote_age_seconds": round(max_age, 3),
        },
        "gates": {
            "decisions": len(decisions),
            "entries_allowed": sum(1 for r in decisions if r["payload"]["final"] == "ENTRY_ALLOWED"),
            "blocked_by": dict(Counter(r["payload"]["blocked_by"] for r in decisions if r["payload"]["blocked_by"])),
            "decisions_on_stale_or_unknown_price": stale_decisions,
            "opens_without_full_gate_pass": ungated_opens,
            "opens_below_anti_bleed_minimum": undersized_opens,
        },
        "lifecycle": {
            "opened": len(opens),
            "closed": len(closes),
            "open_at_end": still_open,
            "orphan_closes": orphan_closes,
            "duplicate_closes": duplicate_closes,
            "arithmetic_errors": sorted(set(lifecycle_errors)),
            "closes_without_real_tick": closes_without_real_tick,
        },
        "ledger": {
            "realized_pnl_net_recomputed": round(realized_recomputed, 8),
            "realized_pnl_net_last_snapshot": round(float(last_snapshot_realized), 8),
            "reconciliation_difference": round(abs(realized_recomputed - float(last_snapshot_realized)), 8),
            "run_sessions_with_cycles": sessions_with_cycles,
            "restarts": max(0, sessions_with_cycles - 1),
            "starts_passing_preflight": starts_passed,
            "reconciliations_completed": by_type.get("RECONCILIATION_COMPLETED", 0),
        },
        "safety": {
            "preflight_failures": by_type.get("SAFETY_PREFLIGHT_FAILED", 0),
            "safety_halts": by_type.get("SAFETY_HALT", 0),
            "entries_halted_events": by_type.get("ENTRIES_HALTED", 0),
            "errors": by_type.get("ERROR", 0),
        },
        "stability": {
            "cycles": len(snapshots),
            "span_seconds": round(span_seconds, 3),
            "bar_interval_seconds": interval,
            "cycle_coverage": round(len(snapshots) * interval / span_seconds, 6) if interval and span_seconds else None,
        },
    }
