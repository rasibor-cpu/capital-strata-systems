"""A4 reports for the Enterprise Broker advisory runtime."""

from __future__ import annotations

from typing import Any, Mapping
import uuid

from backend.broker_reporting.page_layout import build_paginated_document
from backend.brokers.runtime.enterprise_broker_runtime import EnterpriseBrokerRuntime
from backend.brokers.runtime.runtime_certification import (
    certify_enterprise_broker_runtime,
)
from backend.options.options_income_freshness import utc_now

BROKER_RUNTIME_REPORT_TITLES = {
    "broker_readiness": "Enterprise Broker Readiness",
    "provider_readiness": "Advisory Provider Readiness",
    "holdings_certification": "Holdings Authority Certification",
    "market_data_certification": "Market Data Certification",
    "runtime_dependency_matrix": "Runtime Dependency Matrix",
    "options_income_readiness": "Options Income Readiness",
    "advisory_runtime_certification": "Advisory Runtime Certification",
}


def build_broker_runtime_report(
    report_type: str,
    *,
    runtime: EnterpriseBrokerRuntime,
    advisory_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    key = str(report_type).lower()
    if key not in BROKER_RUNTIME_REPORT_TITLES:
        raise KeyError("BROKER_RUNTIME_REPORT_TYPE_UNKNOWN")
    evidence = dict(advisory_evidence or {})
    certification = certify_enterprise_broker_runtime(
        runtime,
        advisory_evidence=evidence,
    )
    health = runtime.health()
    sections = {
        "broker_readiness": [
            ("Broker Runtime Health", health),
            ("Broker Bindings", health["bindings"]),
        ],
        "provider_readiness": [
            ("Provider Registry", evidence.get("provider_registry", {})),
            ("Provider States", _provider_states(evidence)),
        ],
        "holdings_certification": [
            ("Holdings", evidence.get("holdings", {})),
            ("Collateral", evidence.get("collateral", {})),
        ],
        "market_data_certification": [
            ("Market Data", evidence.get("market_data_rows", [])),
            ("Option Chains", evidence.get("option_chain_rows", [])),
        ],
        "runtime_dependency_matrix": [
            ("Dependencies", evidence.get("missing_dependencies", [])),
            ("Runtime State", {"readiness_status": evidence.get("readiness_status")}),
        ],
        "options_income_readiness": [
            ("Options Income", evidence),
            ("Eligibility", evidence.get("eligibility", {})),
        ],
        "advisory_runtime_certification": [
            ("Certification", certification),
            ("Runtime Health", health),
        ],
    }[key]
    generated = utc_now()
    report_id = f"EBR-{key.upper()}-{uuid.uuid4().hex[:10].upper()}"
    document = build_paginated_document(
        title=BROKER_RUNTIME_REPORT_TITLES[key],
        report_id=report_id,
        css_version="Phase-179D",
        commit_reference=None,
        generated_at=generated,
        executive_summary=[
            f"Certification outcome: {certification['outcome']}",
            f"Broker count: {health['broker_count']}",
            f"Advisory status: {certification['advisory_status']}",
            "Execution posture: DISABLED",
            "Execution authority: BLOCKED",
            "Runtime posture: FAIL_CLOSED / ADVISORY_ONLY",
        ],
        sections=sections,
    )
    return {
        "schema_version": "css.enterprise_broker_runtime.report.v1",
        "report_type": key,
        "report_id": report_id,
        "generated_at": generated,
        "document": document.as_dict(),
        "viewer_compatible": True,
        "execution_allowed": False,
    }


def build_broker_runtime_report_suite(
    *,
    runtime: EnterpriseBrokerRuntime,
    advisory_evidence: Mapping[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    return {
        report_type: build_broker_runtime_report(
            report_type,
            runtime=runtime,
            advisory_evidence=advisory_evidence,
        )
        for report_type in BROKER_RUNTIME_REPORT_TITLES
    }


def _provider_states(evidence: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "dataset": dataset,
            "status": row.get("status"),
            "provenance": row.get("provenance"),
            "freshness": row.get("freshness"),
        }
        for dataset, rows in (
            ("MARKET_DATA", evidence.get("market_data_rows", [])),
            ("OPTION_CHAIN", evidence.get("option_chain_rows", [])),
        )
        for row in list(rows or [])
        if isinstance(row, Mapping)
    ]


__all__ = [
    "BROKER_RUNTIME_REPORT_TITLES",
    "build_broker_runtime_report",
    "build_broker_runtime_report_suite",
]
