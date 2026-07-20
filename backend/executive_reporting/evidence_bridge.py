"""Phase 178 — bridge Phase 177/178 outputs into Phase 176J evidence keys."""

from __future__ import annotations

from typing import Any, Mapping


def financial_evidence_for_176j(phase177_or_178_package: Mapping[str, Any] | None) -> dict[str, Any]:
    """
    Map financial package fields to 176J readiness evidence keys.

    Preserves Phase 176J key names (income_statement, balance_sheet, cash_flow).
    Does not rename or collapse readiness states across layers.
    """
    pkg = phase177_or_178_package if isinstance(phase177_or_178_package, Mapping) else {}
    # Prefer nested Phase 177 statements from an executive package
    income = pkg.get("income_statement")
    balance = pkg.get("balance_sheet")
    cash = pkg.get("cash_flow_statement") or pkg.get("cash_flow")
    readiness = pkg.get("readiness") if isinstance(pkg.get("readiness"), Mapping) else {}
    summary = pkg.get("financial_summary") if isinstance(pkg.get("financial_summary"), Mapping) else {}

    evidence: dict[str, Any] = {}
    if income is not None:
        evidence["income_statement"] = income
    if balance is not None:
        evidence["balance_sheet"] = balance
    if cash is not None:
        evidence["cash_flow"] = cash

    freshness = summary.get("data_freshness") or pkg.get("data_freshness") or pkg.get("generated_at")
    if freshness:
        evidence["reporting_data_freshness"] = {
            "status": "FRESH" if income or balance or cash else "UNAVAILABLE",
            "generated_at": freshness,
            "financial_report_package": True,
        }
    if pkg:
        evidence["financial_report_package"] = {
            "present": True,
            "schema_version": pkg.get("schema_version"),
            "report_id": pkg.get("report_id"),
            "financial_readiness": readiness.get("overall_state")
            or summary.get("reporting_readiness"),
            "advisory_only": True,
            "trading_impact": False,
        }
    return evidence


def merge_financial_evidence_into_176j(
    base_evidence: dict[str, Any] | None,
    phase177_or_178_package: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Overlay financial evidence without wiping other 176J components."""
    out = dict(base_evidence or {})
    fin = financial_evidence_for_176j(phase177_or_178_package)
    for key, value in fin.items():
        if key == "reporting_data_freshness" and isinstance(out.get(key), dict) and isinstance(value, dict):
            merged = dict(out[key])
            merged.update(value)
            out[key] = merged
        elif out.get(key) in (None, {}, []):
            out[key] = value
        elif key in {"income_statement", "balance_sheet", "cash_flow"} and not out.get(key):
            out[key] = value
        elif key == "financial_report_package":
            out[key] = value
        elif key in {"income_statement", "balance_sheet", "cash_flow"}:
            # Prefer explicit Phase 177/178 package when present
            out[key] = value
    return out
