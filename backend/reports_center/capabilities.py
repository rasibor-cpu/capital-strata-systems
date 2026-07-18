"""Canonical report capability evaluation for Desktop/Mobile UI (Phase 176F).

Server-side only. UI may display results; it cannot grant authorization.
"""

from __future__ import annotations

from typing import Any, Mapping

from backend.reports_center.definition import CSSReportDefinition
from backend.reports_center.producers import producer_is_registered
from backend.reports_center.rbac import ReportsAccessControl

_STATUS_GENERATE_OK = frozenset({"AVAILABLE", "AVAILABLE_WITH_LIMITATIONS"})
_STATUS_GENERATE_BLOCKED = frozenset(
    {"COMING_SOON", "DATA_UNAVAILABLE", "DISABLED", "DEPRECATED"}
)

# Fields that must survive every UI/API serialization of a report definition.
UI_REPORT_DEFINITION_KEYS: tuple[str, ...] = (
    "report_type",
    "report_code",
    "title",
    "category",
    "status",
    "inventory_class",
    "supported_scopes",
    "supported_formats",
    "producer",
    "validator",
    "limitations",
    "official_report",
    "advisory_only",
    "printable",
    "downloadable",
    "emailable",
    "required_view_permission",
    "required_generate_permission",
    "required_print_permission",
    "required_email_permission",
    "required_admin_action",
    "generatable",
    "can_view",
    "can_generate",
    "can_print",
    "can_email",
    "generate_label",
    "generate_blocked_reason",
    "configuration_error",
    "producer_registered",
    "evidence_contract_supported",
    "filter_fields",
)


def _perm_name(value: Any) -> str | None:
    """Return stripped permission name, or None when absent/invalid."""
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    s = value.strip()
    return s if s else None


def evaluate_report_capabilities(
    definition: CSSReportDefinition | Mapping[str, Any],
    *,
    role: str,
    access: ReportsAccessControl | None = None,
    staff_grants: set[str] | None = None,
) -> dict[str, Any]:
    """Evaluate registry + producer + evidence + RBAC into effective booleans.

    Fail closed when required permission metadata is missing from a definition
    that claims to be status-eligible for generation.
    """
    access = access or ReportsAccessControl()
    role_u = str(role or "").upper()

    if isinstance(definition, CSSReportDefinition):
        status = str(definition.status or "")
        report_code = definition.report_code
        producer = str(definition.producer or "")
        evidence = list(definition.evidence_sources)
        view_perm = definition.required_view_permission
        gen_perm = definition.required_generate_permission
        print_perm = definition.required_print_permission
        email_perm = definition.required_email_permission
    else:
        status = str(definition.get("status") or "")
        report_code = str(definition.get("report_code") or "")
        producer = str(definition.get("producer") or "")
        evidence = list(definition.get("evidence_sources") or [])
        view_perm = definition.get("required_view_permission")
        gen_perm = definition.get("required_generate_permission")
        print_perm = definition.get("required_print_permission")
        email_perm = definition.get("required_email_permission")

    view_name = _perm_name(view_perm)
    gen_name = _perm_name(gen_perm)
    print_name = _perm_name(print_perm) or ""
    email_name = _perm_name(email_perm) or ""

    configuration_error: str | None = None
    status_eligible = status in _STATUS_GENERATE_OK
    status_blocked = status in _STATUS_GENERATE_BLOCKED or not status_eligible

    # Missing permission metadata is never treated as authorization.
    if status_eligible:
        if view_name is None:
            configuration_error = "missing_required_view_permission"
        elif gen_name is None:
            # Empty generate permission is not silently mapped to reports_generate.
            configuration_error = "missing_required_generate_permission"

    producer_present = bool(producer.strip())
    producer_registered = producer_present and producer_is_registered(report_code)
    # Catalogue evidence contract is supported when a concrete producer is registered;
    # per-request evidence (e.g. transaction_ticket) is enforced at generation time.
    evidence_contract_supported = producer_registered

    can_view = False
    can_generate_perm = False
    can_print = False
    can_email = False
    if configuration_error is None and view_name is not None:
        can_view = access.can_view_report(role_u, view_name)
    if configuration_error is None and gen_name is not None:
        can_generate_perm = access.can_generate(role_u, gen_name)
    if print_name:
        can_print = access.can_print(role_u, print_name, staff_grants=staff_grants)
    if email_name:
        can_email = access.can_email(role_u, email_name)

    registry_generatable = (
        status_eligible
        and producer_registered
        and evidence_contract_supported
        and configuration_error is None
    )
    can_generate = bool(registry_generatable and can_generate_perm and can_view)

    blocked_reason = ""
    if configuration_error:
        blocked_reason = configuration_error
    elif status_blocked:
        blocked_reason = status or "STATUS_INELIGIBLE"
    elif not producer_registered:
        blocked_reason = "PRODUCER_UNAVAILABLE"
    elif not evidence_contract_supported:
        blocked_reason = "EVIDENCE_CONTRACT_UNSUPPORTED"
    elif not can_view:
        blocked_reason = "VIEW_DENIED"
    elif not can_generate_perm:
        blocked_reason = "GENERATE_DENIED"

    if can_generate:
        if status == "AVAILABLE_WITH_LIMITATIONS":
            generate_label = "Enabled with limitations"
        else:
            generate_label = "Enabled"
    else:
        generate_label = "Disabled"

    return {
        "report_code": report_code,
        "status": status,
        "required_view_permission": view_name,
        "required_generate_permission": gen_name,
        "required_print_permission": print_name or None,
        "required_email_permission": email_name or None,
        "status_eligible": status_eligible,
        "producer_present": producer_present,
        "producer_registered": producer_registered,
        "evidence_sources": evidence,
        "evidence_contract_supported": evidence_contract_supported,
        "configuration_error": configuration_error,
        "generatable": registry_generatable,
        "can_view": can_view,
        "can_generate": can_generate,
        "can_print": can_print,
        "can_email": can_email,
        "generate_label": generate_label,
        "generate_blocked_reason": blocked_reason,
    }


def ui_report_definition(
    definition: CSSReportDefinition,
    *,
    role: str,
    access: ReportsAccessControl | None = None,
) -> dict[str, Any]:
    """Canonical UI-facing report definition (Desktop + Mobile)."""
    access = access or ReportsAccessControl()
    caps = evaluate_report_capabilities(definition, role=role, access=access)
    base = definition.as_dict()
    return {
        "report_type": base["report_type"],
        "report_code": base["report_code"],
        "title": base["title"],
        "category": base["category"],
        "status": base["status"],
        "inventory_class": base["inventory_class"],
        "supported_scopes": list(base["supported_scopes"]),
        "supported_formats": list(base["supported_formats"]),
        "producer": base["producer"],
        "validator": base["validator"],
        "limitations": base["limitations"],
        "official_report": base["official_report"],
        "advisory_only": base["advisory_only"],
        "printable": base["printable"],
        "downloadable": base["downloadable"],
        "emailable": base["emailable"],
        # Preserve registry permission *names* for diagnostics (never rename).
        "required_view_permission": definition.required_view_permission,
        "required_generate_permission": definition.required_generate_permission,
        "required_print_permission": definition.required_print_permission,
        "required_email_permission": definition.required_email_permission,
        "required_admin_action": definition.required_admin_action,
        "generatable": caps["generatable"],
        "can_view": caps["can_view"],
        "can_generate": caps["can_generate"],
        "can_print": caps["can_print"],
        "can_email": caps["can_email"],
        "generate_label": caps["generate_label"],
        "generate_blocked_reason": caps["generate_blocked_reason"],
        "configuration_error": caps["configuration_error"],
        "producer_registered": caps["producer_registered"],
        "evidence_contract_supported": caps["evidence_contract_supported"],
    }
