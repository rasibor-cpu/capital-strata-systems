"""
tools/posting_reports.py

Posting Lifecycle Reports
-------------------------
Provides regulator-grade reports for:
- Posting Approval Snapshot
- Posting Execution Summary
- Ledger Impact Summary

These reports are authority-gated and reusable through print_report framework.
"""

from __future__ import annotations

from typing import Dict, Any, List
from datetime import datetime

from engine.reporting.report_printer import register_report, ReportResult
from engine.reporting.report_request import ReportRequest


# ============================================================
# Helper (future: replace with real ledger query)
# ============================================================

def _fetch_posting_snapshot(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Placeholder snapshot generator.
    Replace later with real ledger / posting_engine integration.
    """
    return {
        "posting_id": params.get("posting_id"),
        "maker_id": params.get("maker_id"),
        "checker_id": params.get("checker_id"),
        "status": "APPROVED",
        "debit_total": 125000.00,
        "credit_total": 125000.00,
        "currency": params.get("currency", "USD"),
        "accounts_impacted": [
            {"account": "CASH_001", "movement": -125000.00},
            {"account": "LOAN_101", "movement": 125000.00},
        ],
    }


# ============================================================
# Posting Approval Snapshot Report
# ============================================================

@register_report(
    "posting_snapshot",
    title="Posting Approval Snapshot",
    required_roles={"ADMIN", "SUPER_USER", "FINCON_REPORTING"},
    required_permissions={"FINCON_REPORTING"},
    default_sections={"summary", "ledger_impact", "signoff"},
)
def posting_snapshot(req: ReportRequest) -> ReportResult:

    snapshot = _fetch_posting_snapshot(req.params)

    payload: Dict[str, Any] = {
        "report_id": "posting_snapshot",
        "title": "Posting Approval Snapshot",
        "generated_at": datetime.utcnow().isoformat(),
        "snapshot": snapshot,
        "caller": {
            "user_id": req.caller.user_id,
            "display_name": req.caller.display_name,
            "roles": sorted(req.caller.roles),
            "permissions": sorted(req.caller.permissions),
        },
    }

    lines: List[str] = []
    lines.append("=== POSTING APPROVAL SNAPSHOT (REGULATOR FORMAT) ===")
    lines.append(f"Posting ID        : {snapshot.get('posting_id')}")
    lines.append(f"Status            : {snapshot.get('status')}")
    lines.append(f"Maker             : {snapshot.get('maker_id')}")
    lines.append(f"Checker           : {snapshot.get('checker_id')}")
    lines.append(f"Currency          : {snapshot.get('currency')}")
    lines.append(f"Debit Total       : {snapshot.get('debit_total')}")
    lines.append(f"Credit Total      : {snapshot.get('credit_total')}")

    lines.append("")
    lines.append("Ledger Impact:")
    for row in snapshot.get("accounts_impacted", []):
        lines.append(f"  {row['account']:20s} {row['movement']}")

    lines.append("")
    lines.append("Sign-off:")
    lines.append(f"  Printed by      : {req.caller.display_name}")
    lines.append(f"  Roles           : {', '.join(sorted(req.caller.roles))}")
    lines.append(f"  Generated       : {payload['generated_at']}")

    text = "\n".join(lines) + "\n"

    return ReportResult(
        report_id="posting_snapshot",
        title="Posting Approval Snapshot",
        payload=payload,
        text=text,
    )