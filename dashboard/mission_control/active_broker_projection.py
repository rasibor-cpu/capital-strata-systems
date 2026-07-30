"""MW-002 — align Mission Control active-broker projection to runtime profile.

Overall readiness must follow the broker that is actually active for the
current runtime profile (e.g. PAPER + CSS_PAPER / OANDA Practice). Inactive,
disabled, or stale live selections (e.g. unconfigured Coinbase FAIL) remain
visible as advisory registry detail and must not drive overall health colour.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

DATA_UNAVAILABLE = "UNAVAILABLE"

_PAPER_RUNTIME_MODES = frozenset({"PAPER", "PRACTICE", "DEMO", "SIM", "SIMULATION", "SANDBOX"})
_PAPER_BROKER_NAMES = frozenset({"NONE", "PAPER", "DEMO", "CSS_PAPER", ""})
_PAPER_BROKER_MODES = frozenset({"paper", "practice", "demo", "sim", "simulation", "sandbox"})
_TIER1_LIVE_CANDIDATES = frozenset({"COINBASE", "BINANCE", "OANDA", "QUESTRADE"})
_FAIL_STATUSES = frozenset({"FAIL", "FAILED", "RED", "BROKER_UNAVAILABLE", "UNAVAILABLE"})
_READY_STATUSES = frozenset({"PASS", "READY", "CONNECTED", "OK", "GREEN", "AVAILABLE", "READY_FOR_PAPER"})


def normalize_runtime_mode(value: Any) -> str:
    text = str(value or "").strip().upper()
    if text in {"PAPER", "PRACTICE", "DEMO", "SIM", "SIMULATION", "SANDBOX"}:
        return "PAPER"
    return text


def is_paper_runtime_mode(value: Any) -> bool:
    return normalize_runtime_mode(value) == "PAPER"


def broker_compatible_with_runtime_profile(
    *,
    selected_broker: Any,
    broker_mode: Any,
    runtime_mode: Any,
) -> bool:
    """Return True when the projected selection is the campaign-active broker."""
    selected = str(selected_broker or "").strip().upper()
    mode = str(broker_mode or "").strip().lower()
    if not is_paper_runtime_mode(runtime_mode):
        return True
    if selected in _PAPER_BROKER_NAMES:
        return True
    if mode in _PAPER_BROKER_MODES:
        return True
    # Stale live Tier-1 selection during PAPER is not campaign-active.
    if selected in _TIER1_LIVE_CANDIDATES and mode in {"live", "live_read_only", "live-read-only", ""}:
        return False
    if selected in _TIER1_LIVE_CANDIDATES:
        return mode in _PAPER_BROKER_MODES
    return selected not in {DATA_UNAVAILABLE, "UNAVAILABLE"}


def resolve_paper_campaign_broker(
    broker: Mapping[str, Any],
    runtime_snapshot: Mapping[str, Any],
) -> tuple[str, str, str]:
    """Choose the paper/practice broker identity and readiness for remapping."""
    runtime_broker = runtime_snapshot.get("broker") if isinstance(runtime_snapshot.get("broker"), Mapping) else {}
    candidates: list[tuple[str, str, str]] = []

    for source in (broker, runtime_broker, runtime_snapshot):
        if not isinstance(source, Mapping):
            continue
        for key in ("campaign_broker", "paper_broker", "active_paper_broker", "practice_broker"):
            name = str(source.get(key) or "").strip().upper()
            if name:
                mode = str(source.get("paper_broker_mode") or source.get("broker_mode") or "paper").strip().lower()
                if mode not in _PAPER_BROKER_MODES:
                    mode = "paper"
                status = str(
                    source.get("paper_connection_status")
                    or source.get("practice_connection_status")
                    or source.get("connection_status")
                    or "PASS"
                ).strip().upper()
                candidates.append((name, mode, status or "PASS"))

        selected = str(source.get("selected_broker") or source.get("broker") or "").strip().upper()
        mode = str(source.get("broker_mode") or "").strip().lower()
        if selected == "OANDA" and mode in _PAPER_BROKER_MODES:
            status = str(source.get("connection_status") or source.get("transport") or "PASS").strip().upper()
            candidates.append(("OANDA", mode or "paper", status or "PASS"))
        if selected in _PAPER_BROKER_NAMES and selected:
            status = str(source.get("connection_status") or source.get("transport") or "PASS").strip().upper()
            candidates.append((selected if selected != "NONE" else "CSS_PAPER", "paper", status or "PASS"))

    for name, mode, status in candidates:
        if name in _PAPER_BROKER_NAMES or name == "OANDA" or name == "CSS_PAPER":
            if status in _FAIL_STATUSES and name in _TIER1_LIVE_CANDIDATES:
                # Prefer explicit paper FAIL only for the paper/practice identity.
                return name, mode, status
            if status not in _FAIL_STATUSES or name in _PAPER_BROKER_NAMES or name == "CSS_PAPER":
                return name, mode, status if status else "PASS"

    # Default campaign paper ticket broker when a stale live selection is discarded.
    return "CSS_PAPER", "paper", "PASS"


def project_active_broker_for_runtime_profile(
    active: Mapping[str, Any],
    *,
    broker: Mapping[str, Any],
    runtime_snapshot: Mapping[str, Any],
    runtime_mode: Any = None,
) -> dict[str, Any]:
    """Return active_broker aligned to the current runtime profile.

    When PAPER runtime projects a stale live/disabled broker as selected, remap
    active_broker to the paper/practice campaign broker. Superseded evidence is
    retained under ``inactive_projected_broker`` for advisory visibility.
    """
    projected = dict(active)
    mode = runtime_mode
    if mode in (None, ""):
        mode = (
            runtime_snapshot.get("runtime_mode")
            or broker.get("runtime_mode")
            or projected.get("runtime_mode")
            or ""
        )
    selected = projected.get("selected_broker", DATA_UNAVAILABLE)
    broker_mode = projected.get("broker_mode", DATA_UNAVAILABLE)
    if broker_compatible_with_runtime_profile(
        selected_broker=selected,
        broker_mode=broker_mode,
        runtime_mode=mode,
    ):
        projected["profile_aligned"] = True
        projected["projection_source"] = "runtime_selection"
        return projected

    paper_name, paper_mode, paper_status = resolve_paper_campaign_broker(broker, runtime_snapshot)
    superseded = {
        "selected_broker": selected,
        "broker_mode": broker_mode,
        "connection_status": projected.get("connection_status", DATA_UNAVAILABLE),
        "authentication_status": projected.get("authentication_status", DATA_UNAVAILABLE),
        "failure_reason": projected.get("failure_reason", DATA_UNAVAILABLE),
        "warnings": list(projected.get("warnings") or []),
        "not_active_for_runtime_profile": True,
        "advisory_only": True,
    }
    projected["selected_broker"] = paper_name
    projected["broker_mode"] = paper_mode
    projected["connection_status"] = paper_status
    # Paper simulation does not inherit live-adapter FAIL transport.
    if paper_name in _PAPER_BROKER_NAMES or paper_name == "CSS_PAPER":
        if str(projected.get("authentication_status") or "").upper() in _FAIL_STATUSES:
            projected["authentication_status"] = "NOT_REQUIRED"
        if str(projected.get("account_status") or "").upper() in _FAIL_STATUSES:
            projected["account_status"] = "SIMULATION"
        if str(projected.get("market_data_status") or "").upper() in _FAIL_STATUSES:
            projected["market_data_status"] = "SIMULATION"
        projected["failure_reason"] = DATA_UNAVAILABLE
    projected["profile_aligned"] = True
    projected["projection_source"] = "paper_runtime_profile_alignment"
    projected["inactive_projected_broker"] = superseded
    warnings = list(projected.get("warnings") or [])
    warnings.append("inactive_broker_excluded_from_overall_readiness")
    projected["warnings"] = warnings
    return projected


def annotate_broker_list_with_inactive_evidence(
    broker_list: list[dict[str, Any]],
    *,
    active_broker: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Keep inactive/superseded brokers visible without marking them selected."""
    rows = [dict(row) for row in broker_list]
    active_name = str(active_broker.get("selected_broker") or "").strip().upper()
    superseded = active_broker.get("inactive_projected_broker")
    if not isinstance(superseded, Mapping):
        return rows

    inactive_name = str(superseded.get("selected_broker") or "").strip().upper()
    if not inactive_name or inactive_name in _PAPER_BROKER_NAMES:
        return rows

    connection = str(superseded.get("connection_status") or DATA_UNAVAILABLE).upper()
    failure = superseded.get("failure_reason", DATA_UNAVAILABLE)
    updated = False
    for row in rows:
        name = str(row.get("broker") or "").strip().upper()
        if name == inactive_name:
            row["selected"] = False
            row["status"] = connection if connection in _FAIL_STATUSES else row.get("status", "REGISTERED")
            row["operational_state"] = "DEGRADED" if connection in _FAIL_STATUSES else row.get("operational_state", "REGISTERED")
            row["readiness"] = "NOT_READY" if connection in _FAIL_STATUSES else row.get("readiness", "UNCONFIGURED")
            row["connection_health"] = connection
            row["error_state"] = failure
            row["advisory_only"] = True
            row["inactive_reason"] = "not_active_for_runtime_profile"
            row["not_active_for_runtime_profile"] = True
            updated = True
        elif name == active_name or (active_name in {"CSS_PAPER", "PAPER", "DEMO", "NONE"} and name == "PAPER"):
            row["selected"] = True
    if not updated:
        rows.append(
            {
                "broker": inactive_name,
                "role": "ADVISORY_INACTIVE",
                "broker_type": "EXTERNAL",
                "status": connection,
                "operational_state": "DEGRADED" if connection in _FAIL_STATUSES else "REGISTERED",
                "mode": str(superseded.get("broker_mode") or "unavailable"),
                "readiness": "NOT_READY" if connection in _FAIL_STATUSES else "UNCONFIGURED",
                "connection_health": connection,
                "error_state": failure,
                "selected": False,
                "priority": 90,
                "execution_blocked": True,
                "advisory_only": True,
                "inactive_reason": "not_active_for_runtime_profile",
                "not_active_for_runtime_profile": True,
            }
        )

    if active_name in {"CSS_PAPER", "PAPER", "DEMO", "NONE"} and not any(
        str(row.get("broker") or "").upper() in {"PAPER", "CSS_PAPER"} and row.get("selected") for row in rows
    ):
        rows.append(
            {
                "broker": "CSS_PAPER" if active_name == "CSS_PAPER" else "PAPER",
                "role": "SIMULATION_LANE",
                "broker_type": "SIMULATION",
                "status": "AVAILABLE",
                "operational_state": "AVAILABLE",
                "mode": "paper",
                "readiness": "READY_FOR_PAPER",
                "connection_health": str(active_broker.get("connection_status") or "PASS"),
                "selected": True,
                "priority": 99,
                "execution_blocked": True,
                "advisory_only": True,
                "profile_aligned": True,
            }
        )
    return rows


def canonical_broker_connection_state(value: Any) -> str:
    """Map broker connection/readiness vocabulary onto canonical health buckets."""
    text = str(value or "").strip().upper()
    if text in _FAIL_STATUSES or text in {"DISCONNECTED", "DOWN", "ERROR"}:
        return "FAIL"
    if text in {"DEGRADED", "AMBER", "YELLOW", "PARTIAL", "WARN", "WARNING"}:
        return "DEGRADED"
    if text in _READY_STATUSES or text in {"CONNECTED", "HEALTHY"}:
        return "READY"
    if not text:
        return "UNKNOWN"
    return "UNKNOWN"


__all__ = [
    "annotate_broker_list_with_inactive_evidence",
    "broker_compatible_with_runtime_profile",
    "canonical_broker_connection_state",
    "is_paper_runtime_mode",
    "normalize_runtime_mode",
    "project_active_broker_for_runtime_profile",
    "resolve_paper_campaign_broker",
]
