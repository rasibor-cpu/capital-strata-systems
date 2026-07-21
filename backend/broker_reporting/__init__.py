"""
Phase 177C — Broker Executive Reporting Suite.

Advisory broker reporting for the Executive Reporting Suite.
Separate from Phase 178 financial arithmetic (no P&L recalculation).
Complies with CSS Enterprise Reporting paginated presentation standard.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
from uuid import uuid4

from backend.app.brokers.canonical_tier1 import (
    TIER1_BROKERS,
    get_canonical_broker_registry,
)
from backend.app.brokers.contamination_isolation import (
    ContaminationReport,
    analyze_environment_contamination,
    analyze_runtime_state_contamination,
    merge_contamination_reports,
)
from backend.app.brokers.live_read_only import build_live_read_only_contract
from backend.broker_reporting.page_layout import (
    EnterpriseReportDocument,
    build_paginated_document,
)

SCHEMA_VERSION = "css.broker.reporting.v1"


@dataclass
class BrokerExecutiveReportPackage:
    report_id: str
    generated_at: str
    css_version: str
    commit_reference: str | None
    advisory_only: bool
    trading_impact: bool
    execution_allowed: bool
    broker_summary: dict[str, Any]
    broker_readiness: dict[str, Any]
    broker_health: dict[str, Any]
    broker_latency: dict[str, Any]
    certification: dict[str, Any]
    connection_history: list[dict[str, Any]]
    account_summary: dict[str, Any]
    market_data_summary: dict[str, Any]
    contamination: dict[str, Any]
    live_read_only: dict[str, Any]
    per_broker: dict[str, Any]
    document: dict[str, Any]
    schema_version: str = SCHEMA_VERSION

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_git_commit() -> str | None:
    try:
        import subprocess

        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=3,
        )
        return out.strip() or None
    except Exception:
        return None


def build_broker_executive_report_package(
    *,
    active_broker: Mapping[str, Any] | None = None,
    runtime_state: Mapping[str, Any] | None = None,
    env: Mapping[str, Any] | None = None,
    css_version: str = "Phase-177C",
    commit_reference: str | None = None,
    connection_history: Sequence[Mapping[str, Any]] | None = None,
) -> BrokerExecutiveReportPackage:
    registry = get_canonical_broker_registry()
    active = dict(active_broker or {})
    selected = str(active.get("selected_broker") or active.get("broker") or "NONE").upper()

    env_report = analyze_environment_contamination(env, selected_broker=selected)
    runtime_report = analyze_runtime_state_contamination(runtime_state or active)
    contamination = merge_contamination_reports(env_report, runtime_report)

    rows = registry.mission_control_rows(
        selected_broker=selected,
        active=active,
        contamination_by_broker=contamination.findings_by_broker(),
    )
    per_broker = {row["broker"]: row for row in rows}

    readiness = {
        broker: {
            "readiness": per_broker[broker]["readiness"],
            "readiness_score": per_broker[broker]["readiness_score"],
            "operational_state": per_broker[broker]["operational_state"],
            "live_read_only_allowed": per_broker[broker]["live_read_only_allowed"],
            "expected_condition": per_broker[broker]["expected_condition"],
            "retryable": per_broker[broker]["retryable"],
            "recommended_action": per_broker[broker]["recommended_action"],
            "last_successful_operation": per_broker[broker]["last_successful_operation"],
            "freshness": per_broker[broker]["freshness"],
        }
        for broker in TIER1_BROKERS
    }
    health = {
        broker: {
            "authentication": per_broker[broker]["authentication"],
            "connection_health": per_broker[broker]["connection_health"],
            "market_data": per_broker[broker]["market_data"],
            "account": per_broker[broker]["account"],
            "error_state": per_broker[broker]["error_state"],
        }
        for broker in TIER1_BROKERS
    }
    latency = {
        broker: {"latency_ms": per_broker[broker]["latency"], "last_sync": per_broker[broker]["last_sync"]}
        for broker in TIER1_BROKERS
    }
    certification = {
        broker: {
            "certification": per_broker[broker]["certification"],
            "execution": per_broker[broker]["execution"],
            "execution_authority": per_broker[broker]["execution_authority"],
        }
        for broker in TIER1_BROKERS
    }

    history = [dict(item) for item in (connection_history or []) if isinstance(item, Mapping)]
    if not history:
        history = [
            {
                "broker": selected,
                "event": "snapshot",
                "status": active.get("connection_status") or active.get("broker_health") or "UNAVAILABLE",
                "timestamp": _utc_now(),
            }
        ]

    account_summary = {
        "selected_broker": selected,
        "account_status": active.get("account_data_health") or active.get("account_status") or "UNAVAILABLE",
        "balances_loaded": bool(active.get("balances_loaded") or active.get("account_loaded")),
        "positions_loaded": bool(active.get("positions_loaded")),
        "advisory_only": True,
    }
    market_data_summary = {
        "selected_broker": selected,
        "market_data_status": active.get("market_data_status") or active.get("market_data_health") or "UNAVAILABLE",
        "products_loaded": active.get("products_loaded", 0),
        "freshness": active.get("last_successful_sync") or "UNAVAILABLE",
    }

    lro = {
        broker: build_live_read_only_contract(broker).as_dict()
        for broker in TIER1_BROKERS
    }

    report_id = f"BRK-{_utc_now().replace('-', '').replace(':', '')}-{uuid4().hex[:8].upper()}"
    commit = commit_reference if commit_reference is not None else _safe_git_commit()
    generated = _utc_now()

    summary = {
        "tier1_brokers": list(TIER1_BROKERS),
        "primary_roles": registry.primary_roles(),
        "selected_broker": selected,
        "roadmap_excluded": sorted(registry.registry_summary()["roadmap_excluded"]),
        "execution_policy": registry.registry_summary()["execution_policy"],
        "contamination_status": contamination.status,
        "registered_count": len(TIER1_BROKERS),
    }

    document = build_paginated_document(
        title="CSS Broker Executive Report",
        report_id=report_id,
        css_version=css_version,
        commit_reference=commit,
        generated_at=generated,
        executive_summary=[
            f"Canonical Tier-1 brokers: {', '.join(TIER1_BROKERS)}.",
            f"Selected broker: {selected}.",
            f"Contamination status: {contamination.status}.",
            "Execution remains blocked for all brokers. LIVE_READ_ONLY is validation-only.",
            "IBKR is excluded from the active implementation roadmap (Revision B).",
        ],
        sections=[
            ("Broker Summary", summary),
            ("Broker Readiness", readiness),
            ("Broker Health", health),
            ("Broker Latency", latency),
            ("Certification", certification),
            ("Connection History", {"events": history}),
            ("Account Summary", account_summary),
            ("Market Data Summary", market_data_summary),
            ("Contamination Analysis", contamination.as_dict()),
            ("LIVE_READ_ONLY Contracts", lro),
            (
                "Operational and Capability States",
                {
                    broker: {
                        "operational_state": per_broker[broker]["operational_state"],
                        "capability_states": per_broker[broker]["capability_states"],
                        "expected_condition": per_broker[broker]["expected_condition"],
                        "recommended_action": per_broker[broker]["recommended_action"],
                        "retryable": per_broker[broker]["retryable"],
                        "last_successful_operation": per_broker[broker]["last_successful_operation"],
                    }
                    for broker in TIER1_BROKERS
                },
            ),
            ("Per-Broker Registry Rows", per_broker),
        ],
    )
    document.presentation.update(
        {
            "page_size": "A4",
            "orientation": "portrait",
            "viewer_hints": {
                "default_mode": "one_page_at_a_time",
                "controls": ["previous", "next", "page_selector", "toc", "print_export"],
                "continuous_scroll_default": False,
            },
        }
    )

    return BrokerExecutiveReportPackage(
        report_id=report_id,
        generated_at=generated,
        css_version=css_version,
        commit_reference=commit,
        advisory_only=True,
        trading_impact=False,
        execution_allowed=False,
        broker_summary=summary,
        broker_readiness=readiness,
        broker_health=health,
        broker_latency=latency,
        certification=certification,
        connection_history=history,
        account_summary=account_summary,
        market_data_summary=market_data_summary,
        contamination=contamination.as_dict(),
        live_read_only=lro,
        per_broker=per_broker,
        document=document.as_dict(),
    )


__all__ = [
    "BrokerExecutiveReportPackage",
    "SCHEMA_VERSION",
    "build_broker_executive_report_package",
]
