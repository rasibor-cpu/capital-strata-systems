"""CSSReportDefinition — canonical report catalogue entry."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class CSSReportDefinition:
    report_type: str
    report_code: str
    title: str
    description: str
    category: str
    supported_scopes: tuple[str, ...] = ()
    supported_formats: tuple[str, ...] = ("HTML", "JSON")
    producer: str = ""
    evidence_sources: tuple[str, ...] = ()
    validator: str = ""
    archive_policy: str = "immutable_final_v1"
    retention_policy: str = "retain_indefinite_v1"
    official_report: bool = False
    advisory_only: bool = True
    contains_financial_values: bool = False
    contains_personal_data: bool = False
    printable: bool = False
    downloadable: bool = True
    emailable: bool = False
    email_policy: str = "EMAIL_DISABLED"
    required_view_permission: str = "reports_view"
    required_generate_permission: str = "reports_generate"
    required_print_permission: str = "reports_print_all"
    required_email_permission: str = ""
    required_admin_action: str = "reports_admin"
    status: str = "COMING_SOON"
    schema_version: str = "css.report_definition.v1"
    inventory_class: str = "FUTURE_CAPABILITY"
    limitations: str = ""
    implementation_phase: str = "176"
    menu_path: str = ""

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        for key in (
            "supported_scopes",
            "supported_formats",
            "evidence_sources",
        ):
            d[key] = list(d[key])
        # Property — not a dataclass field; must be explicit for API/UI payloads.
        d["generatable"] = self.generatable
        return d

    @property
    def generatable(self) -> bool:
        return self.status in {"AVAILABLE", "AVAILABLE_WITH_LIMITATIONS"} and bool(self.producer)


def defn(**kwargs: Any) -> CSSReportDefinition:
    return CSSReportDefinition(**kwargs)
