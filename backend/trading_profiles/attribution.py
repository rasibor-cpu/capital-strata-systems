"""Copy-trade attribution ledger and reconciliation.

Keeps the copied trader's signal separate from each follower's own decision, fill,
exit and PnL. Records are appended to a SHA-256 hash-chained JSONL ledger, so edits
or deletions are detectable. Reconciliation proves that every follower record maps
to exactly one source signal and that exits only close the follower's own fills.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from backend.certification.ov002_persistence import atomic_append_jsonl
from backend.runtime.interprocess_lock import exclusive_file_lock

GENESIS = "GENESIS"


class AttributionError(RuntimeError):
    """Fail-closed attribution ledger error."""


def _canonical(body: Mapping[str, Any]) -> bytes:
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str).encode("ascii")


class AttributionLedger:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.path = self.root / "copy_trade_attribution.jsonl"
        self.lock_path = self.root / "copy_trade_attribution.lock"

    def records(self) -> list[dict[str, Any]]:
        """All records after verifying the hash chain (raises AttributionError if broken)."""
        if not self.path.exists():
            return []
        prev = GENESIS
        out: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            claimed = record.pop("entry_hash", None)
            if record.get("prev_hash") != prev or hashlib.sha256(_canonical(record)).hexdigest() != claimed:
                raise AttributionError("attribution ledger chain broken")
            record["entry_hash"] = claimed
            prev = claimed
            out.append(record)
        return out

    def append(self, record_type: str, body: Mapping[str, Any]) -> dict[str, Any]:
        self.root.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.lock_path, timeout_seconds=10.0):
            existing = self.records()
            prev = existing[-1]["entry_hash"] if existing else GENESIS
            record = {"record_type": record_type, **dict(body), "prev_hash": prev}
            record["entry_hash"] = hashlib.sha256(_canonical(record)).hexdigest()
            atomic_append_jsonl(self.path, record, expected_root=self.root)
        return record

    def record_source_signal(self, signal: Mapping[str, Any]) -> None:
        """Idempotent: one SOURCE_SIGNAL record per signal id."""
        if any(r["record_type"] == "SOURCE_SIGNAL" and r["signal_id"] == signal["signal_id"] for r in self.records()):
            return
        self.append("SOURCE_SIGNAL", signal)

    def follower_statement(self, user_id: str) -> dict[str, Any]:
        """User-facing view: trader signal vs this follower's own decision, fill and PnL."""
        records = self.records()
        signals = {r["signal_id"]: r for r in records if r["record_type"] == "SOURCE_SIGNAL"}
        exits = {r["position_id"]: r for r in records if r["record_type"] == "FOLLOWER_EXIT" and r["follower_user_id"] == user_id}
        trades, skipped = [], {}
        for r in records:
            if r["record_type"] != "FOLLOWER_DECISION" or r["follower_user_id"] != user_id:
                continue
            source = signals.get(r["signal_id"], {})
            if r["outcome"] in {"COPIED", "SIMULATED"}:
                exit_record = exits.get(r["position_id"])
                trades.append({
                    "signal_id": r["signal_id"],
                    "trader_id": source.get("trader_id"),
                    "trader_signal": {"side": source.get("side"), "reference_price": source.get("reference_price")},
                    "your_personality": r["personality"],
                    "your_fill": r["fill"],
                    "your_exit": None if exit_record is None else {
                        "price": exit_record["exit_price"], "reason": exit_record["reason"], "pnl": exit_record["pnl"]},
                    "outcome": r["outcome"],
                })
            else:
                skipped[r["reason"]] = skipped.get(r["reason"], 0) + 1
        realized = round(sum(e["pnl"] for e in exits.values()), 2)
        return {"user_id": user_id, "trades": trades, "skipped_signals_by_reason": skipped,
                "your_realized_pnl": realized,
                "note": "Your fills and PnL are your own; they differ from the copied trader's."}


def reconcile(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Check copy-trade attribution invariants. Returns {ok, discrepancies, counts}."""
    signals: set[str] = set()
    decisions: dict[tuple[str, str], Mapping[str, Any]] = {}
    open_positions: dict[str, Mapping[str, Any]] = {}
    closed: set[str] = set()
    problems: list[str] = []
    for r in records:
        kind = r.get("record_type")
        if kind == "SOURCE_SIGNAL":
            signals.add(r["signal_id"])
        elif kind == "FOLLOWER_DECISION":
            key = (r["signal_id"], r["follower_user_id"])
            if r["signal_id"] not in signals:
                problems.append(f"decision_without_source_signal:{r['signal_id']}:{r['follower_user_id']}")
            if key in decisions:
                problems.append(f"duplicate_follower_decision:{key[0]}:{key[1]}")
            decisions[key] = r
            if r["outcome"] in {"COPIED", "SIMULATED"}:
                fill = r.get("fill") or {}
                if not fill or not fill.get("notional") or fill["notional"] <= 0:
                    problems.append(f"copied_without_fill:{r['position_id']}")
                if r.get("pipeline_status") not in {"validated_not_executed", "simulated_not_routed"}:
                    problems.append(f"copied_without_governed_pipeline:{r['position_id']}")
                open_positions[r["position_id"]] = r
            elif r.get("fill"):
                problems.append(f"rejected_decision_has_fill:{r['signal_id']}:{r['follower_user_id']}")
        elif kind == "FOLLOWER_EXIT":
            pid = r["position_id"]
            opened = open_positions.get(pid)
            if opened is None:
                problems.append(f"exit_without_copied_position:{pid}")
            elif opened["follower_user_id"] != r["follower_user_id"]:
                problems.append(f"exit_follower_mismatch:{pid}")
            if pid in closed:
                problems.append(f"duplicate_exit:{pid}")
            closed.add(pid)
    copied = sum(1 for d in decisions.values() if d["outcome"] in {"COPIED", "SIMULATED"})
    return {
        "ok": not problems,
        "discrepancies": problems,
        "counts": {"source_signals": len(signals), "follower_decisions": len(decisions), "copied": copied,
                   "rejected": len(decisions) - copied, "exits": len(closed)},
    }
