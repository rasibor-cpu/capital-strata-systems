from __future__ import annotations

from typing import Any, Mapping


READY_BLOCKED_EXTERNAL = "READY_FOR_LIVE_READ_VALIDATION_BLOCKED_EXTERNAL"
LIVE_READ_VALIDATED = "LIVE_READ_VALIDATED"
FAILED_CLOSED = "FAILED_CLOSED"


def _false(value: Any) -> bool:
    return value is False


def _true(value: Any) -> bool:
    return value is True


def build_session10_readiness(
    mission_control: Mapping[str, Any] | None,
    continuity: Mapping[str, Any] | None,
    *,
    live_validation_evidence: bool = False,
    external_blocker: str | None = "BLOCKED_EXTERNAL_403_CLOUDFLARE_1010",
) -> dict[str, Any]:
    """Build the canonical fail-closed Session-10 readiness projection.

    Software readiness is intentionally distinct from real-account validation.
    The projection can report structural readiness while provider authentication
    remains externally blocked, but it cannot claim LIVE_READ_VALIDATED unless
    explicit live-validation evidence is supplied and the broker state is both
    authenticated and current.
    """

    mission = dict(mission_control or {})
    continuity_state = dict(continuity or {})

    safety_ok = (
        _false(mission.get("execution_allowed"))
        and _true(mission.get("live_trading_blocked"))
        and _false(mission.get("broker_execution_armed"))
        and _true(mission.get("advisory_only"))
        and _true(mission.get("read_only"))
        and _false(continuity_state.get("execution_allowed"))
        and _true(continuity_state.get("live_trading_blocked"))
        and _false(continuity_state.get("broker_execution_armed"))
        and _true(continuity_state.get("advisory_only"))
        and _true(continuity_state.get("read_only"))
    )

    structural_ready = (
        safety_ok
        and continuity_state.get("snapshot_status") != "CORRUPT"
        and continuity_state.get("ledger_status") in {"AVAILABLE", "UNAVAILABLE"}
    )

    broker_live_read_ready = (
        mission.get("broker_name") == "QUESTRADE"
        and _true(mission.get("broker_connected"))
        and _true(mission.get("broker_authenticated"))
        and mission.get("data_freshness") == "CURRENT"
        and mission.get("capital_provenance") == "REAL_BROKER"
        and _true(mission.get("state_complete"))
    )

    validated = bool(
        live_validation_evidence
        and structural_ready
        and broker_live_read_ready
    )

    if validated:
        status = LIVE_READ_VALIDATED
        blocker = None
    elif structural_ready:
        status = READY_BLOCKED_EXTERNAL
        blocker = external_blocker
    else:
        status = FAILED_CLOSED
        blocker = external_blocker

    return {
        "schema": "css.session10.readiness.v1",
        "status": status,
        "software_structural_readiness": structural_ready,
        "real_account_validation": validated,
        "live_validation_evidence": bool(live_validation_evidence),
        "external_blocker": blocker,
        "broker_name": mission.get("broker_name", "UNKNOWN"),
        "broker_connected": bool(mission.get("broker_connected", False)),
        "broker_authenticated": bool(mission.get("broker_authenticated", False)),
        "broker_data_freshness": mission.get("data_freshness", "UNAVAILABLE"),
        "capital_provenance": mission.get("capital_provenance", "UNKNOWN"),
        "continuity_snapshot_status": continuity_state.get(
            "snapshot_status", "UNAVAILABLE"
        ),
        "continuity_ledger_status": continuity_state.get(
            "ledger_status", "UNAVAILABLE"
        ),
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
        "read_only": True,
    }


__all__ = [
    "FAILED_CLOSED",
    "LIVE_READ_VALIDATED",
    "READY_BLOCKED_EXTERNAL",
    "build_session10_readiness",
]
