"""
Phase 177D — Options Income enterprise paginated reporting.

Uses the CSS Enterprise Reporting page-layout standard (shared with broker reports).
Advisory only — no execution authority.
"""

from __future__ import annotations

from typing import Any, Mapping
from uuid import uuid4

from backend.broker_reporting.page_layout import EnterpriseReportDocument, build_paginated_document
from backend.options.options_income_runtime_service import (
    OptionsIncomeRuntimeContext,
    build_options_income_runtime_snapshot,
)

SCHEMA_VERSION = "css.options_income.report.v1"


def report_safe_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Project account data to report-safe metadata before serialization."""
    root = dict(snapshot)
    advisory = dict(root.get("advisory_data") or {})
    holdings = dict(advisory.get("holdings") or {})
    safe_holdings = {
        key: holdings.get(key)
        for key in (
            "contract",
            "schema_version",
            "status",
            "broker",
            "account_type",
            "base_currency",
            "quality",
            "quality_flags",
            "completeness_pct",
            "missing_fields",
            "failure_reason",
            "freshness",
            "age_seconds",
            "provider_timestamp",
            "received_at",
            "generated_at",
            "provenance",
            "demonstration",
        )
    }
    safe_holdings.update(
        {
            "holding_count": len(holdings.get("holdings") or []),
            "option_position_count": len(holdings.get("option_positions") or []),
            "restricted_position_count": len(holdings.get("restricted_positions") or []),
            "short_position_count": len(holdings.get("short_positions") or []),
            "monetary_values_redacted": True,
            "account_identifier_redacted": True,
            "advisory_only": True,
            "execution_allowed": False,
        }
    )
    collateral = dict(advisory.get("collateral") or root.get("collateral") or {})
    safe_collateral = {
        key: collateral.get(key)
        for key in (
            "contract",
            "schema_version",
            "status",
            "authority_level",
            "source",
            "currency",
            "broker_confirmed",
            "css_derived",
            "failure_reason",
            "provenance",
            "timestamp",
            "generated_at",
            "rejects_simulated_10000_fixture",
        )
    }
    safe_collateral.update(
        {
            "monetary_value_redacted": True,
            "advisory_only": True,
            "execution_allowed": False,
        }
    )
    advisory["holdings"] = safe_holdings
    advisory["collateral"] = safe_collateral
    root["advisory_data"] = advisory
    root["collateral"] = safe_collateral
    return root


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


def build_options_income_executive_report(
    *,
    ctx: OptionsIncomeRuntimeContext | None = None,
    snapshot: Mapping[str, Any] | None = None,
    css_version: str = "Phase-177D",
    commit_reference: str | None = None,
) -> dict[str, Any]:
    snap = report_safe_snapshot(
        snapshot or build_options_income_runtime_snapshot(ctx or OptionsIncomeRuntimeContext(persist=False))
    )
    generated = str(snap.get("generated_at") or "")
    report_id = f"OI-{generated.replace('-', '').replace(':', '')}-{uuid4().hex[:8].upper()}"
    commit = commit_reference if commit_reference is not None else _safe_git_commit()

    summary_lines = [
        f"Engine status: {snap.get('status')} / {snap.get('engine_status')}",
        f"Deployment: {snap.get('deployment_state')}",
        f"Opportunities: {snap.get('opportunity_count')}",
        f"Certification: {(snap.get('certification') or {}).get('outcome') if isinstance(snap.get('certification'), dict) else snap.get('certification')}",
        f"Missing dependencies: {', '.join(snap.get('missing_dependencies') or []) or 'none'}",
        "Execution authority: BLOCKED. Advisory only. No orders queued.",
        "Projected premium is never mixed with collected premium.",
    ]

    sections = [
        ("Income Target and Run-Rate Analysis", snap.get("run_rate") or {}),
        ("Current Opportunities", {
            "opportunity_count": snap.get("opportunity_count"),
            "covered_calls": snap.get("covered_calls"),
            "cash_secured_puts": snap.get("cash_secured_puts"),
            "rejected_candidates": snap.get("rejected_candidates"),
        }),
        ("Premium Accounting", snap.get("premium_accounting") or {}),
        ("Active / Advisory Positions", snap.get("paper_positions") or []),
        ("Collateral and Capital", snap.get("collateral") or {}),
        ("Greeks", snap.get("greeks") or {}),
        ("Assignment and Volatility Risk", {
            "assignment_risk": snap.get("assignment_risk"),
            "volatility_risk": snap.get("volatility_risk"),
        }),
        ("Rolling Recommendations", snap.get("rolling_recommendations") or []),
        ("Portfolio Allocation", snap.get("portfolio_allocation") or {}),
        ("Stress Testing", snap.get("stress_tests") or {}),
        ("Advisory Data Providers", {
            "provider_summary": snap.get("provider_summary"),
            "data_readiness": snap.get("data_readiness"),
            "freshness": (snap.get("advisory_data") or {}).get("option_chains")
            if isinstance(snap.get("advisory_data"), dict)
            else None,
        }),
        ("Holdings Coverage and Collateral Authority", {
            "holdings": (snap.get("advisory_data") or {}).get("holdings")
            if isinstance(snap.get("advisory_data"), dict)
            else None,
            "collateral": (snap.get("advisory_data") or {}).get("collateral")
            if isinstance(snap.get("advisory_data"), dict)
            else snap.get("collateral"),
            "eligibility": (snap.get("advisory_data") or {}).get("eligibility")
            if isinstance(snap.get("advisory_data"), dict)
            else None,
        }),
        ("Symbol Normalization and Provider Limitations", {
            "broker_capability_truth": (snap.get("advisory_data") or {}).get("broker_capability_truth")
            if isinstance(snap.get("advisory_data"), dict)
            else None,
            "questrade_readiness": (snap.get("advisory_data") or {}).get("questrade_readiness")
            if isinstance(snap.get("advisory_data"), dict)
            else None,
            "events": (snap.get("advisory_data") or {}).get("events")
            if isinstance(snap.get("advisory_data"), dict)
            else None,
            "notes": [
                "BTC_USD / BTC-USD aliases are excluded from listed-equity option eligibility",
                "Coinbase, Binance, and OANDA do not provide listed-equity option chains",
                "Demonstration fixtures are never published as live market data",
            ],
        }),
        ("Broker Operational and Capability States", {
            "operational_state": (snap.get("advisory_data") or {}).get("broker_operational_state")
            if isinstance(snap.get("advisory_data"), dict)
            else None,
            "option_chain_state": (snap.get("advisory_data") or {}).get("broker_option_chain_state")
            if isinstance(snap.get("advisory_data"), dict)
            else None,
            "expected_condition": (snap.get("advisory_data") or {}).get("broker_expected_condition")
            if isinstance(snap.get("advisory_data"), dict)
            else None,
            "execution_allowed": False,
        }),
        ("Certification and Operational Readiness", {
            "certification": snap.get("certification"),
            "operational_readiness": snap.get("operational_readiness"),
        }),
        ("Data Provenance and Limitations", {
            "provenance": snap.get("provenance"),
            "missing_dependencies": snap.get("missing_dependencies"),
            "limitations": [
                "No fabricated option-chain opportunities when MARKET_DATA/OPTION_CHAIN absent",
                "Collateral never inferred from simulated 10000 margin fixtures",
                "Runtime mode and broker registry consulted; execution remains blocked",
                "OPTION_CHAIN_PROVIDER_NOT_CONFIGURED until an approved provider is registered",
            ],
        }),
    ]

    document = build_paginated_document(
        title="CSS Options Income Executive Report",
        report_id=report_id,
        css_version=css_version,
        commit_reference=commit,
        generated_at=generated,
        executive_summary=summary_lines,
        sections=sections,
    )
    # Annotate presentation for A4 / print
    presentation = dict(document.presentation)
    presentation.update(
        {
            "page_size": "A4",
            "orientation": "portrait",
            "repeating_table_headers": True,
            "viewer_hints": {
                "default_mode": "one_page_at_a_time",
                "controls": ["previous", "next", "page_selector", "toc", "print_export"],
                "continuous_scroll_default": False,
            },
        }
    )
    doc_dict = document.as_dict()
    doc_dict["presentation"] = presentation

    return {
        "schema_version": SCHEMA_VERSION,
        "report_id": report_id,
        "generated_at": generated,
        "css_version": css_version,
        "commit_reference": commit,
        "advisory_only": True,
        "trading_impact": False,
        "execution_allowed": False,
        "snapshot_status": snap.get("status"),
        "state_hash": snap.get("state_hash"),
        "document": doc_dict,
        "html": EnterpriseReportDocument(
            title=document.title,
            report_id=document.report_id,
            css_version=document.css_version,
            commit_reference=document.commit_reference,
            generated_at=document.generated_at,
            page_count=document.page_count,
            pages=document.pages,
            presentation=presentation,
        ).to_html(),
    }


__all__ = ["SCHEMA_VERSION", "build_options_income_executive_report"]
