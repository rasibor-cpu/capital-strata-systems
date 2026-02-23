"""
Replay Runner – Read-Only Forensic Replay (Repo-Compatible)
-----------------------------------------------------------

Purpose:
- Load a persisted replay record by ENGINE_RUN_ID
- Print stored envelope / firewall / execution result
- Optionally rebuild the decision ONLY if gate_inputs exist in metadata
- NEVER touch brokers or live systems

Usage:
    python -m engine.replay.run <ENGINE_RUN_ID>
"""
from __future__ import annotations

import sys
import json
from typing import Dict, Any

from engine.audit.replay_loader import ReplayLoader, ReplayLoaderError

# Optional (only used if metadata contains gate_inputs)
try:
    from engine.decision_builder import GateInputs, build_trade_execution_decision
    from engine.gates_registry import get_configured_gates
except Exception:  # pragma: no cover
    GateInputs = None  # type: ignore
    build_trade_execution_decision = None  # type: ignore
    get_configured_gates = None  # type: ignore


class ReplayRunError(RuntimeError):
    pass


def _pretty(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True)


def _compare_key_fields(stored: Dict[str, Any], rebuilt: Dict[str, Any]) -> list[str]:
    mismatches: list[str] = []
    for key in ("final_decision", "primary_reason", "blocked_by", "can_execute"):
        if stored.get(key) != rebuilt.get(key):
            mismatches.append(
                f"{key}: stored={stored.get(key)!r} rebuilt={rebuilt.get(key)!r}"
            )
    return mismatches


def run_replay(engine_run_id: str) -> None:
    loader = ReplayLoader()
    record = loader.load(engine_run_id)

    stored_decision = record["decision_envelope"]
    stored_firewall = record["firewall_result"]
    stored_execution = record["execution_result"]
    metadata = record.get("metadata", {}) or {}

    print("\n=== REPLAY RECORD LOADED ===")
    print(f"ENGINE_RUN_ID: {engine_run_id}")

    print("\n=== STORED DECISION ENVELOPE ===")
    print(_pretty(stored_decision))

    print("\n=== STORED FIREWALL RESULT ===")
    print(_pretty(stored_firewall))

    print("\n=== STORED EXECUTION RESULT ===")
    print(_pretty(stored_execution))

    # ------------------------------------------------------------------
    # Optional deterministic rebuild (ONLY if gate_inputs exist)
    # ------------------------------------------------------------------
    gate_inputs = metadata.get("gate_inputs")

    if (
        gate_inputs
        and GateInputs
        and build_trade_execution_decision
        and get_configured_gates
    ):
        print("\n=== REBUILDING DECISION (REPLAY MODE) ===")

        try:
            inputs = GateInputs(
                instrument=gate_inputs.get("instrument"),
                snapshot=gate_inputs.get("snapshot", {}),
                volatility=gate_inputs.get("volatility", {}),
                liquidity=gate_inputs.get("liquidity", {}),
                slippage=gate_inputs.get("slippage", {}),
                risk=gate_inputs.get("risk", {}),
            )

            gates = get_configured_gates()

            rebuilt_decision = build_trade_execution_decision(
                engine_run_id=engine_run_id,
                mode="REPLAY",
                inputs=inputs,
                gates=gates,
            ).as_dict()

            print("\n=== REBUILT DECISION ENVELOPE ===")
            print(_pretty(rebuilt_decision))

            print("\n=== FORENSIC COMPARISON ===")
            mismatches = _compare_key_fields(stored_decision, rebuilt_decision)

            if mismatches:
                print("❌ MISMATCHES DETECTED:")
                for m in mismatches:
                    print(" -", m)
            else:
                print("✅ Key decision fields match (stored vs rebuilt)")

        except Exception as e:
            print("\n⚠️ REBUILD SKIPPED DUE TO ERROR:")
            print(str(e))

    else:
        print("\n=== REBUILD SKIPPED ===")
        print("Reason: metadata.gate_inputs not present (or replay rebuild deps unavailable).")
        print("This is OK. You still have full stored forensic evidence.")

    print("\n=== REPLAY COMPLETE (NO EXECUTION PERFORMED) ===")


def main(argv: list[str]) -> None:
    if len(argv) != 2:
        raise ReplayRunError("Usage: python -m engine.replay.run <ENGINE_RUN_ID>")
    run_replay(argv[1])


if __name__ == "__main__":
    try:
        main(sys.argv)
    except ReplayLoaderError as e:
        print(f"REPLAY LOADER ERROR: {e}")
        sys.exit(2)
    except Exception as e:
        print(f"REPLAY ERROR: {e}")
        sys.exit(1)
