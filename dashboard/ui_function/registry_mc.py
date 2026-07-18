"""Mission Control UI function definitions (Phase 176C)."""

from __future__ import annotations

from dashboard.mission_control.navigation import MISSION_CONTROL_SECTIONS
from dashboard.ui_function.models import CSSUIFunctionDefinition, defn
from backend.reports_center.constants import CATEGORIES


def _mc_nav() -> list[CSSUIFunctionDefinition]:
    out: list[CSSUIFunctionDefinition] = []
    for section in MISSION_CONTROL_SECTIONS:
        out.append(
            defn(
                control_id=f"mc.nav.{section.key}",
                page_id="mission_control_shell",
                section="navigation",
                label=section.label,
                control_type="nav",
                desktop_route=section.route,
                expected_action="navigate_ssr_page",
                expected_service="dashboard.mission_control.layout.render_mission_control_shell",
                expected_api=f"GET {section.route}",
                expected_success_state="page_renders_with_aria_current",
                expected_failure_state="fallback_or_404",
                evidence_source="dashboard/mission_control/navigation.py",
                implementation_status="FUNCTIONAL",
                test_id="test_mc_nav_routes_render",
                safety_classification="ADVISORY_READ_ONLY",
                desktop_mobile="DESKTOP_ONLY",
            )
        )
    return out


def _mc_readonly_page(page_id: str, label: str, route: str, limitation: str) -> list[CSSUIFunctionDefinition]:
    return [
        defn(
            control_id=f"mc.page.{page_id}.ssr",
            page_id=page_id,
            section="page",
            label=f"{label} SSR view",
            control_type="display",
            desktop_route=route,
            expected_action="render_canonical_state",
            expected_service="dashboard.mission_control.contracts.build_mission_control_state",
            expected_api=f"GET {route}",
            expected_success_state="metrics_and_tables_render",
            expected_failure_state="UNAVAILABLE_or_offline_banner",
            evidence_source=f"dashboard/mission_control/pages/{page_id}.py",
            implementation_status="FUNCTIONAL_WITH_LIMITATIONS",
            test_id="test_mc_readonly_pages_ssr",
            limitation=limitation,
            desktop_mobile="DESKTOP_ONLY",
        ),
        defn(
            control_id=f"mc.page.{page_id}.mutations",
            page_id=page_id,
            section="governance",
            label=f"{label} mutation controls",
            control_type="display",
            desktop_route=route,
            expected_action="remain_disabled",
            expected_success_state="no_writable_controls",
            expected_failure_state="N/A",
            evidence_source=f"dashboard/mission_control/pages/{page_id}.py",
            implementation_status="FAIL_CLOSED",
            test_id="test_mc_readonly_pages_ssr",
            limitation="Mission Control is GET-only; mutations are intentionally absent.",
            desktop_mobile="DESKTOP_ONLY",
            safety_classification="FAIL_CLOSED_NO_WRITE",
        ),
    ]


def _mc_reports() -> list[CSSUIFunctionDefinition]:
    out: list[CSSUIFunctionDefinition] = []
    for target, label in (
        ("rc-categories", "Categories"),
        ("rc-frequent", "Generatable"),
        ("rc-create", "Create Report"),
        ("rc-library", "Library"),
        ("rc-detail", "Detail"),
    ):
        out.append(
            defn(
                control_id=f"mc.reports.subtab.{target}",
                page_id="reports_center",
                section="subtabs",
                label=label,
                control_type="subtab",
                desktop_route=f"/mission-control/reports#{target}",
                expected_action="activate_subtab_and_scroll",
                expected_service="dashboard.ui_interaction.CSSUIInteraction",
                expected_success_state="aria_current_and_section_visible",
                expected_failure_state="hash_ignored",
                evidence_source="dashboard/mission_control/pages/reports_center.py",
                implementation_status="FUNCTIONAL",
                test_id="test_reports_subtabs_functional",
                desktop_mobile="DESKTOP_ONLY",
            )
        )
    out.append(
        defn(
            control_id="mc.reports.expand_all",
            page_id="reports_center",
            section="categories",
            label="Expand all",
            control_type="button",
            desktop_route="/mission-control/reports",
            expected_action="open_all_disclosures",
            expected_service="CSSUIInteraction",
            implementation_status="FUNCTIONAL",
            test_id="test_reports_disclosure_workflow",
            desktop_mobile="DESKTOP_ONLY",
        )
    )
    out.append(
        defn(
            control_id="mc.reports.collapse_all",
            page_id="reports_center",
            section="categories",
            label="Collapse all",
            control_type="button",
            desktop_route="/mission-control/reports",
            expected_action="close_all_disclosures",
            expected_service="CSSUIInteraction",
            implementation_status="FUNCTIONAL",
            test_id="test_reports_disclosure_workflow",
            desktop_mobile="DESKTOP_ONLY",
        )
    )
    for key in CATEGORIES:
        out.append(
            defn(
                control_id=f"mc.reports.category.{key}",
                page_id="reports_center",
                section="categories",
                label=f"Category {key}",
                control_type="disclosure",
                desktop_route=f"/mission-control/reports#cat-{key}",
                expected_action="open_category_disclosure",
                expected_service="CSSUIInteraction.openDisclosureForTarget",
                expected_success_state="aria_expanded_true_panel_visible",
                evidence_source="backend/reports_center/ui_contract.py",
                implementation_status="FUNCTIONAL",
                test_id="test_reports_category_deeplink",
                desktop_mobile="DESKTOP_ONLY",
            )
        )
    for action, api, service in (
        ("view_readiness", "GET /mission-control/api/reports/readiness/{code}", "ReportsCenterService.readiness"),
        ("generate", "POST /api/v1/reports/generate", "ReportsCenterService.generate"),
        ("library_refresh", "GET /mission-control/api/reports", "ReportsCenterService.list_library"),
        ("library_open", "GET /mission-control/api/reports/{id}", "ReportsCenterService.retrieve"),
        ("detail_print", "GET /mission-control/api/reports/{id}/print", "ReportsCenterService.print_info"),
        ("detail_pdf", "GET /mission-control/api/reports/{id}/pdf", "ReportsCenterService.pdf_info"),
        ("detail_versions", "GET /mission-control/api/reports/{id}/versions", "ReportsCenterService.versions"),
        ("detail_audit", "GET /mission-control/api/reports/{id}/audit", "ReportsCenterService.audit_history"),
        ("verify_integrity", "POST /api/v1/reports/{id}/verify-integrity", "ReportsCenterService.verify_integrity"),
        ("printable_html", "GET /api/v1/reports/{id}/print", "ReportsCenterService.printable_html"),
    ):
        out.append(
            defn(
                control_id=f"mc.reports.action.{action}",
                page_id="reports_center",
                section="reports_workflow",
                label=action.replace("_", " "),
                control_type="api_action",
                desktop_route="/mission-control/reports",
                required_permission="reports_view|reports_generate|reports_print_*",
                expected_action=action,
                expected_service=service,
                expected_api=api,
                expected_success_state="json_or_html_result_rendered",
                expected_failure_state="DENIED_NOT_FOUND_or_blockers",
                evidence_source="dashboard/mission_control/pages/reports_center.py",
                implementation_status="FUNCTIONAL",
                test_id="test_reports_workflow_e2e",
                desktop_mobile="DESKTOP_ONLY",
                safety_classification="ADVISORY_REPORTS",
            )
        )
    out.append(
        defn(
            control_id="mc.reports.non_generatable",
            page_id="reports_center",
            section="reports_workflow",
            label="Not generatable / unauthorized Generate",
            control_type="button",
            desktop_route="/mission-control/reports",
            expected_action="remain_disabled",
            expected_success_state="disabled_with_reason",
            evidence_source="reports_center._report_card",
            implementation_status="FAIL_CLOSED",
            test_id="test_reports_rbac_generate_disabled",
            desktop_mobile="DESKTOP_ONLY",
        )
    )
    return out


MC_CONTROLS: list[CSSUIFunctionDefinition] = []
MC_CONTROLS.extend(_mc_nav())
MC_CONTROLS.extend(
    _mc_readonly_page(
        "executive_overview",
        "Executive Overview",
        "/mission-control/executive-overview",
        "SSR metrics/tables only; institutional 'links' cells are escaped text (not hyperlinks) by design to avoid absolute path exposure.",
    )
)
MC_CONTROLS.extend(
    _mc_readonly_page(
        "runtime_operations",
        "Runtime Operations",
        "/mission-control/runtime-operations",
        "Read-only runtime evidence; restart/recovery UI not exposed on MC.",
    )
)
MC_CONTROLS.extend(
    _mc_readonly_page(
        "trade_operations",
        "Trade Operations",
        "/mission-control/trade-operations",
        "No executable trade tickets from Mission Control.",
    )
)
MC_CONTROLS.extend(
    _mc_readonly_page(
        "portfolio",
        "Portfolio",
        "/mission-control/portfolio",
        "Read-only portfolio projections from runtime state.",
    )
)
MC_CONTROLS.extend(
    _mc_readonly_page(
        "market_intelligence",
        "Market Intelligence",
        "/mission-control/market-intelligence",
        "Read-only market/overnight intelligence projections.",
    )
)
MC_CONTROLS.extend(
    _mc_readonly_page(
        "risk_command",
        "Risk Command",
        "/mission-control/risk-command",
        "Display-only; limits/gates cannot be changed from MC.",
    )
)
MC_CONTROLS.extend(
    _mc_readonly_page(
        "options_income",
        "Options Income",
        "/mission-control/options-income",
        "Advisory Options Income projections only; no execution.",
    )
)
MC_CONTROLS.extend(
    _mc_readonly_page(
        "broker_management",
        "Broker Management",
        "/mission-control/broker-management",
        "Selection/onboarding controls disabled; display-only registry/status.",
    )
)
MC_CONTROLS.extend(
    _mc_readonly_page(
        "alerts_incidents",
        "Alerts and Incidents",
        "/mission-control/alerts-incidents",
        "Acknowledgement actions are DISABLED_READ_ONLY strings, not buttons.",
    )
)
MC_CONTROLS.extend(
    _mc_readonly_page(
        "certification_readiness",
        "Certification and Readiness",
        "/mission-control/certification-readiness",
        "Readiness summaries from SSR certification projections.",
    )
)
MC_CONTROLS.extend(
    _mc_readonly_page(
        "audit_explainability",
        "Audit and Explainability",
        "/mission-control/audit-explainability",
        "Deletion/editing disabled; read-only audit/evidence tables.",
    )
)
MC_CONTROLS.extend(
    _mc_readonly_page(
        "learning_performance",
        "Learning and Performance",
        "/mission-control/learning-performance",
        "Advisory strategy/learning metrics only.",
    )
)
MC_CONTROLS.extend(
    _mc_readonly_page(
        "users_governance",
        "Users and Governance",
        "/mission-control/users-governance",
        "Role editing disabled on MC; operator console is display-only.",
    )
)
MC_CONTROLS.extend(
    _mc_readonly_page(
        "system_configuration",
        "System Configuration",
        "/mission-control/system-configuration",
        "Cannot edit limits/credentials from MC; editing_enabled=false.",
    )
)
MC_CONTROLS.extend(
    _mc_readonly_page(
        "documentation_runbooks",
        "Documentation / Runbooks",
        "/mission-control/documentation-runbooks",
        "Document index is display-only text (absolute filesystem paths intentionally not hyperlinked).",
    )
)
MC_CONTROLS.extend(_mc_reports())
