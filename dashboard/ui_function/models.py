"""Phase 176C — canonical UI function registry models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

FunctionalStatus = Literal[
    "FUNCTIONAL",
    "FUNCTIONAL_WITH_LIMITATIONS",
    "FAIL_CLOSED",
    "DISABLED",
    "COMING_SOON",
    "BROKEN",
    "UNVERIFIED",
]

ControlType = Literal[
    "nav",
    "subtab",
    "disclosure",
    "button",
    "link",
    "form",
    "select",
    "filter",
    "refresh",
    "metric",
    "table",
    "card_action",
    "api_action",
    "display",
]


@dataclass(frozen=True)
class CSSUIFunctionDefinition:
    control_id: str
    page_id: str
    section: str
    label: str
    control_type: ControlType
    desktop_route: str = ""
    mobile_route: str = ""
    required_role: str = "ANY"
    required_permission: str = ""
    expected_action: str = ""
    expected_service: str = ""
    expected_api: str = ""
    expected_success_state: str = ""
    expected_failure_state: str = ""
    evidence_source: str = ""
    availability_status: str = "AVAILABLE"
    implementation_status: FunctionalStatus = "UNVERIFIED"
    test_id: str = ""
    safety_classification: str = "ADVISORY_READ_ONLY"
    desktop_mobile: str = "BOTH"  # BOTH | DESKTOP_ONLY | MOBILE_ONLY
    limitation: str = ""
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def defn(**kwargs: Any) -> CSSUIFunctionDefinition:
    return CSSUIFunctionDefinition(**kwargs)
