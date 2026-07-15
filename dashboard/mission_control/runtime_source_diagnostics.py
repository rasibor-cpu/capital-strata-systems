from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from typing import Any

from dashboard.mission_control.active_runtime_source import RuntimeSourceCandidate


def source_diagnostics(
    *,
    selected: RuntimeSourceCandidate | None,
    candidates: Iterable[RuntimeSourceCandidate],
    resolver_name: str = "dashboard.mission_control.runtime_source_resolver",
) -> dict[str, Any]:
    candidate_list = [candidate.diagnostics() for candidate in candidates]
    selected_diag = selected.diagnostics() if selected is not None else {}
    return {
        "resolver": resolver_name,
        "selected_source": selected_diag.get("source_type", "UNAVAILABLE"),
        "selected_name": selected_diag.get("name", "UNAVAILABLE"),
        "selected_available": bool(selected_diag.get("available", False)),
        "selected_freshness_status": selected_diag.get("freshness_status", "UNAVAILABLE"),
        "selected_state_hash": selected_diag.get("state_hash", "UNAVAILABLE"),
        "candidate_sources": candidate_list,
        "candidate_count": len(candidate_list),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "process_boundary": selected_diag.get("process_relationship", "NONE"),
        "fallback": selected_diag.get("fallback_reason", ""),
        "read_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }


def safety_projection(payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    source = payload if isinstance(payload, Mapping) else {}
    return {
        "execution_allowed": bool(source.get("execution_allowed")) if source.get("execution_allowed") is True else False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }


__all__ = ["safety_projection", "source_diagnostics"]
