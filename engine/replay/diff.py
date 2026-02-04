"""
Replay Diff – Structural, Typed Differences
-------------------------------------------

Purpose:
- Compute deterministic diffs between two replay records
- Highlight key decision divergences and deep structural drift
- Output human-readable and machine-readable results

Usage:
    python -m engine.replay.diff <RUN_ID_A> <RUN_ID_B>
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from engine.audit.replay_loader import ReplayLoader, ReplayLoaderError


@dataclass(frozen=True)
class DiffItem:
    path: str
    a: Any
    b: Any
    kind: str  # "missing_in_a", "missing_in_b", "type_mismatch", "value_mismatch"


def _pretty(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True)


def _diff(a: Any, b: Any, path: str = "") -> List[DiffItem]:
    diffs: List[DiffItem] = []

    if a is None and b is None:
        return diffs

    if a is None and b is not None:
        diffs.append(DiffItem(path=path, a=a, b=b, kind="missing_in_a"))
        return diffs

    if b is None and a is not None:
        diffs.append(DiffItem(path=path, a=a, b=b, kind="missing_in_b"))
        return diffs

    if type(a) != type(b):
        diffs.append(DiffItem(path=path, a=type(a).__name__, b=type(b).__name__, kind="type_mismatch"))
        return diffs

    if isinstance(a, dict):
        keys = set(a.keys()) | set(b.keys())
        for k in sorted(keys):
            p = f"{path}.{k}" if path else str(k)
            diffs.extend(_diff(a.get(k), b.get(k), p))
        return diffs

    if isinstance(a, list):
        # List diff: compare length then element-wise up to min length
        if len(a) != len(b):
            diffs.append(DiffItem(path=f"{path}.__len__", a=len(a), b=len(b), kind="value_mismatch"))
        n = min(len(a), len(b))
        for i in range(n):
            p = f"{path}[{i}]"
            diffs.extend(_diff(a[i], b[i], p))
        return diffs

    # Scalars
    if a != b:
        diffs.append(DiffItem(path=path, a=a, b=b, kind="value_mismatch"))

    return diffs


def diff_runs(run_id_a: str, run_id_b: str) -> Tuple[Dict[str, Any], List[DiffItem]]:
    loader = ReplayLoader()
    a = loader.load(run_id_a)
    b = loader.load(run_id_b)

    a_dec = a["decision_envelope"]
    b_dec = b["decision_envelope"]

    a_fw = a["firewall_result"]
    b_fw = b["firewall_result"]

    a_exec = a["execution_result"]
    b_exec = b["execution_result"]

    # Focus diff object is the "decision+firewall+execution" bundle
    bundle_a = {"decision_envelope": a_dec, "firewall_result": a_fw, "execution_result": a_exec}
    bundle_b = {"decision_envelope": b_dec, "firewall_result": b_fw, "execution_result": b_exec}

    diffs = _diff(bundle_a, bundle_b, path="bundle")

    summary = {
        "run_id_a": run_id_a,
        "run_id_b": run_id_b,
        "a_final_decision": a_dec.get("final_decision"),
        "b_final_decision": b_dec.get("final_decision"),
        "a_primary_reason": a_dec.get("primary_reason"),
        "b_primary_reason": b_dec.get("primary_reason"),
        "a_firewall_allowed": a_fw.get("allowed"),
        "b_firewall_allowed": b_fw.get("allowed"),
        "diff_count": len(diffs),
    }

    return summary, diffs


def main(argv: List[str]) -> None:
    if len(argv) != 3:
        print("Usage: python -m engine.replay.diff <RUN_ID_A> <RUN_ID_B>")
        sys.exit(1)

    run_id_a = argv[1]
    run_id_b = argv[2]

    try:
        summary, diffs = diff_runs(run_id_a, run_id_b)
    except ReplayLoaderError as e:
        print(f"REPLAY LOADER ERROR: {e}")
        sys.exit(2)

    print("\n=== DIFF SUMMARY ===")
    print(_pretty(summary))

    print("\n=== DIFF ITEMS ===")
    if not diffs:
        print("✅ No differences detected.")
        sys.exit(0)

    for d in diffs[:200]:
        print(f"- {d.kind}: {d.path}")
        print(f"    A: {d.a!r}")
        print(f"    B: {d.b!r}")

    if len(diffs) > 200:
        print(f"\n... truncated ({len(diffs)-200} more diffs) ...")

    # Non-zero exit code when diffs exist can be useful for CI later
    sys.exit(3)


if __name__ == "__main__":
    main(sys.argv)
