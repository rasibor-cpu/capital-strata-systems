"""
Execution Decision Envelope
===========================

Authoritative trade decision object for REA Capital Trading Engine.

Purpose:
- Aggregate ALL gate decisions into a single immutable outcome
- Prevent accidental or partial execution
- Provide audit-safe, UI-safe, and execution-safe decision output

RULE:
- NO order execution may occur unless decision.can_execute == True
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


@dataclass(frozen=True)
class GateResult:
    gate_name: str
    decision: str            # "ALLOW", "BLOCK", "WARN"
    reason: str


@dataclass(frozen=True)
class ExecutionDecision:
    """
    Canonical execution decision envelope.
    """

    can_execute: bool
    final_decision: str                  # "ALLOW" | "BLOCK"
    primary_reason: str

    engine_run_id: str
    timestamp_utc: str

    blocked_by: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    gate_results: Dict[str, GateResult] = field(default_factory=dict)

    override_used: bool = False
    override_reason: Optional[str] = None

    mode: str = "TEST"                   # TEST | LIVE

    def as_dict(self) -> Dict:
        return {
            "can_execute": self.can_execute,
            "final_decision": self.final_decision,
            "primary_reason": self.primary_reason,
            "engine_run_id": self.engine_run_id,
            "timestamp_utc": self.timestamp_utc,
            "blocked_by": self.blocked_by,
            "warnings": self.warnings,
            "override_used": self.override_used,
            "override_reason": self.override_reason,
            "mode": self.mode,
            "gate_results": {
                k: {
                    "decision": v.decision,
                    "reason": v.reason,
                }
                for k, v in self.gate_results.items()
            },
        }


def build_execution_decision(
    *,
    engine_run_id: str,
    gate_results: Dict[str, GateResult],
    mode: str,
    override_used: bool = False,
    override_reason: Optional[str] = None,
) -> ExecutionDecision:
    """
    Build the authoritative execution decision from gate results.

    Safe defaults:
    - Missing gates => BLOCK
    - Any BLOCK => BLOCK
    """

    if not engine_run_id:
        raise ValueError("ENGINE_RUN_ID is required")

    blocked_by: List[str] = []
    warnings: List[str] = []

    for gate_name, result in gate_results.items():
        if result.decision.upper() == "BLOCK":
            blocked_by.append(gate_name)
        elif result.decision.upper() == "WARN":
            warnings.append(f"{gate_name}: {result.reason}")

    can_execute = (len(blocked_by) == 0)

    # Override logic (explicit and visible)
    if override_used:
        can_execute = True
        blocked_by = []
        final_decision = "ALLOW"
        primary_reason = "HUMAN_OVERRIDE"
    else:
        final_decision = "ALLOW" if can_execute else "BLOCK"
        primary_reason = (
            "ALL_GATES_ALLOW"
            if can_execute
            else f"BLOCKED_BY_{blocked_by[0].upper()}"
        )

    return ExecutionDecision(
        can_execute=can_execute,
        final_decision=final_decision,
        primary_reason=primary_reason,
        engine_run_id=engine_run_id,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        blocked_by=blocked_by,
        warnings=warnings,
        gate_results=gate_results,
        override_used=override_used,
        override_reason=override_reason,
        mode=mode,
    )
