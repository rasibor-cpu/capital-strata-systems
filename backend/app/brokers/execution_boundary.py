"""
Fail-closed broker mode and execution-boundary helpers.

The legacy dashboard still owns CLI prompts and process shutdown behavior, but
the live/paper consistency rules live here so they can be tested and reused by
non-dashboard runtimes.
"""

from __future__ import annotations

from dataclasses import dataclass


VALID_BROKER_MODES = {"paper", "live"}


@dataclass(frozen=True)
class ModeDominanceDecision:
    selected_mode: str
    corrected: bool
    reason: str


@dataclass(frozen=True)
class ExecutionBoundaryDecision:
    allowed: bool
    reason: str


def resolve_mode_dominance(
    *,
    global_mode: str,
    selected_mode: str,
) -> ModeDominanceDecision:
    global_key = str(global_mode or "").strip().lower()
    selected_key = str(selected_mode or "").strip().lower()

    if global_key == "live" and selected_key != "live":
        return ModeDominanceDecision(
            selected_mode="live",
            corrected=True,
            reason="global_live_mode_requires_live_broker_mode",
        )

    return ModeDominanceDecision(
        selected_mode=selected_key or "paper",
        corrected=False,
        reason="mode_consistent",
    )


def validate_execution_boundary(
    *,
    selected_mode: str,
    capital_source_label: str,
) -> ExecutionBoundaryDecision:
    mode = str(selected_mode or "").strip().lower()
    capital_source = str(capital_source_label or "").strip().upper()

    if mode not in VALID_BROKER_MODES:
        return ExecutionBoundaryDecision(
            allowed=False,
            reason=f"unknown_broker_mode:{mode}",
        )

    if mode == "live" and capital_source == "SIMULATED":
        return ExecutionBoundaryDecision(
            allowed=False,
            reason="live_mode_cannot_use_simulated_capital",
        )

    return ExecutionBoundaryDecision(
        allowed=True,
        reason="execution_boundary_ok",
    )
