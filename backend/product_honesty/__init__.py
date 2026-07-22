"""Wave 4 product honesty contracts — customer-visible capability truth."""

from __future__ import annotations

import os
from typing import Any

from backend.reports_center.catalogue import CATALOGUE

GATE2_HONESTY_DOC = "docs/release/CSS_WAVE4_PRODUCT_HONESTY_SCOPE.md"

BOARD_INVESTOR_REGULATORY_CODES = frozenset(
    {
        "investor_client_statement",
        "board_pack",
        "investor_report",
        "regulatory_report",
        "regulatory_filings",
    }
)


def catalogue_honesty_summary() -> dict[str, Any]:
    """Single source of truth for registered vs generatable honesty."""
    total = len(CATALOGUE)
    available = sum(1 for d in CATALOGUE if d.status == "AVAILABLE")
    limited = sum(1 for d in CATALOGUE if d.status == "AVAILABLE_WITH_LIMITATIONS")
    generatable = sum(1 for d in CATALOGUE if d.generatable)
    coming_soon = sum(1 for d in CATALOGUE if d.status == "COMING_SOON")
    unavailable = sum(1 for d in CATALOGUE if d.status == "DATA_UNAVAILABLE")
    disabled = sum(1 for d in CATALOGUE if d.status == "DISABLED")
    return {
        "schema_version": "css.product_honesty.catalogue.v1",
        "remediation_ids": ["AR-017", "AR-047"],
        "honesty_doc": GATE2_HONESTY_DOC,
        "registered_count": total,
        "available_count": available,
        "available_with_limitations_count": limited,
        "generatable_count": generatable,
        "coming_soon_count": coming_soon,
        "data_unavailable_count": unavailable,
        "disabled_count": disabled,
        "mvp_eligible_count": generatable,
        "registered_implies_delivered": False,
        "catalogue_completeness_means": "registry_inventory_not_product_coverage",
        "board_investor_regulatory_scope": "OUT_OF_SCOPE",
        "customer_banner": (
            f"Gate 2 institutional reporting MVP: {generatable} generatable of "
            f"{total} registered catalogue entries. Registered ≠ delivered. "
            "Board/investor/regulatory packs are OUT OF SCOPE."
        ),
        "execution_allowed": False,
        "certification_claimed": False,
    }


def eis_dashboard_honesty() -> dict[str, Any]:
    return {
        "schema_version": "css.product_honesty.eis.v1",
        "remediation_ids": ["AR-018", "AR-042"],
        "honesty_doc": GATE2_HONESTY_DOC,
        "full_eis_182a_released": False,
        "gate2_disposition": "DEFERRED",
        "mission_control_executive_overview": "advisory_operational_visibility_only",
        "management_report": True,
        "not_audited_statutory_statements": True,
        "board_investor_regulatory_scope": "OUT_OF_SCOPE",
        "customer_banner": (
            "Executive surfaces are management/advisory only. "
            "Full EIS/182A dashboard is DEFERRED for Gate 2. "
            "Not audited statutory statements. Board/investor/regulatory packs OUT OF SCOPE."
        ),
        "execution_allowed": False,
        "certification_claimed": False,
    }


def notifications_operational() -> bool:
    return os.getenv("CSS_NOTIFICATIONS_OPERATIONAL", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def notification_honesty_status() -> dict[str, Any]:
    operational = notifications_operational()
    return {
        "schema_version": "css.product_honesty.notifications.v1",
        "remediation_ids": ["AR-022"],
        "honesty_doc": GATE2_HONESTY_DOC,
        "notifications_operational": operational,
        "delivery_simulated_by_default": not operational,
        "silent_success_prohibited_when_non_operational": True,
        "customer_banner": (
            "Customer notifications are NON-OPERATIONAL unless "
            "CSS_NOTIFICATIONS_OPERATIONAL=1 with real transports configured."
            if not operational
            else "Notifications marked operational via CSS_NOTIFICATIONS_OPERATIONAL."
        ),
        "execution_allowed": False,
        "certification_claimed": False,
    }


def deployment_honesty_status() -> dict[str, Any]:
    """AR-016 / RB-011 — CI present; automated production CD absent."""
    return {
        "schema_version": "css.product_honesty.deployment.v1",
        "remediation_ids": ["AR-016"],
        "honesty_doc": "docs/governance/CSS_DEPLOYMENT_APPROVAL_FRAMEWORK.md",
        "playbook": "docs/operations/CSS_PRODUCTION_DEPLOYMENT_PLAYBOOK.md",
        "ci_workflows": [
            ".github/workflows/css_gate2_release_ci.yml",
            ".github/workflows/css_governance.yml",
        ],
        "ci_cd_automation_present": False,
        "automated_production_deploy": False,
        "cd_mode": "manual_with_approvals",
        "gate2_ci_gates": ["compileall_scoped", "bounded_pytest"],
        "customer_banner": (
            "Gate 2 CD mode is manual_with_approvals. "
            "CI enforces compile + bounded pytest only. "
            "No automated production deploy pipeline is present."
        ),
        "execution_allowed": False,
        "certification_claimed": False,
        "live_trading": "BLOCKED",
    }


def product_honesty_bundle() -> dict[str, Any]:
    return {
        "schema_version": "css.product_honesty.bundle.v1",
        "gate": "Release Gate 2",
        "wave": "Final Close-Out",
        "catalogue": catalogue_honesty_summary(),
        "eis": eis_dashboard_honesty(),
        "notifications": notification_honesty_status(),
        "deployment": deployment_honesty_status(),
        "options_advisory": {
            "remediation_ids": ["AR-031"],
            "status": "CLOSED_WAVE2",
            "empty_registry_blocked": True,
            "execution_allowed": False,
            "advisory_only": True,
        },
        "pwa": {
            "remediation_ids": ["AR-025"],
            "status": "PARTIALLY_CLOSED",
            "canonical_doc": "docs/operations/CSS_PWA_CANONICAL_INSTALL.md",
        },
        "execution_allowed": False,
        "certification_claimed": False,
        "live_trading": "BLOCKED",
    }


__all__ = [
    "BOARD_INVESTOR_REGULATORY_CODES",
    "catalogue_honesty_summary",
    "deployment_honesty_status",
    "eis_dashboard_honesty",
    "notification_honesty_status",
    "notifications_operational",
    "product_honesty_bundle",
]
