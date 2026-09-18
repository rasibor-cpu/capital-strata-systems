from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Tuple

from backend.commercialization.production_evidence_handoff import (
    ProductionEvidenceValidation,
)


class ClosureWorkstream(str, Enum):
    LEGAL_REGULATORY = "LEGAL_REGULATORY"
    SERVICE_MODES = "SERVICE_MODES"
    PRICING_POLICY = "PRICING_POLICY"
    PAYMENT_PROVIDER = "PAYMENT_PROVIDER"
    PAYMENT_AUTHORITY = "PAYMENT_AUTHORITY"
    NOTIFICATION_PROVIDER = "NOTIFICATION_PROVIDER"
    NOTIFICATION_POLICY = "NOTIFICATION_POLICY"
    SECURITY_OPERATIONS = "SECURITY_OPERATIONS"
    BACKUP_RESTORE = "BACKUP_RESTORE"
    INCIDENT_RESPONSE = "INCIDENT_RESPONSE"
    PRODUCTION_UAT = "PRODUCTION_UAT"
    RECONCILIATION = "RECONCILIATION"
    RELEASE_OWNER = "RELEASE_OWNER"


@dataclass(frozen=True, slots=True)
class ClosureItem:
    workstream: ClosureWorkstream
    owner_role: str
    evidence_category: str
    acceptance_criterion: str
    externally_controlled: bool


@dataclass(frozen=True, slots=True)
class ProductionClosureStatus:
    work_items_closed: bool
    production_authorized: bool
    internal_engineering_complete: bool
    external_evidence_valid_for_review: bool
    open_workstreams: Tuple[str, ...]
    blocker_reasons: Tuple[str, ...]
    target_deadline: str

    @property
    def money_movement_authorized(self) -> bool:
        return False

    @property
    def trading_execution_authority(self) -> bool:
        return False


CLOSURE_ITEMS: Tuple[ClosureItem, ...] = (
    ClosureItem(
        ClosureWorkstream.LEGAL_REGULATORY,
        "External counsel / compliance",
        "JURISDICTION_LEGAL_REVIEW",
        "Exact agreement/version and target jurisdiction reviewed with immutable approval reference.",
        True,
    ),
    ClosureItem(
        ClosureWorkstream.SERVICE_MODES,
        "External counsel / compliance",
        "SERVICE_MODE_APPROVALS",
        "DISCOVER, CONFIRM and AUTO each have APPROVED/RESTRICTED/PROHIBITED determination.",
        True,
    ),
    ClosureItem(
        ClosureWorkstream.PRICING_POLICY,
        "Commercial owner + counsel",
        "CUSTOMER_AGREEMENT",
        "Independent/customer-directed charge formula is approved and matches the agreement/pricing schedule.",
        True,
    ),
    ClosureItem(
        ClosureWorkstream.PAYMENT_PROVIDER,
        "Payments / finance operations",
        "PAYMENT_PROVIDER",
        "Production provider contract/account/configuration approved; provider environment is production.",
        True,
    ),
    ClosureItem(
        ClosureWorkstream.PAYMENT_AUTHORITY,
        "Payments / finance + counsel",
        "PAYMENT_COLLECTION_AUTHORITY",
        "Collection authority is approved for exact agreement/version/jurisdiction.",
        True,
    ),
    ClosureItem(
        ClosureWorkstream.NOTIFICATION_PROVIDER,
        "Operations / communications",
        "NOTIFICATION_PROVIDER",
        "Production notification provider/channel approved and configured.",
        True,
    ),
    ClosureItem(
        ClosureWorkstream.NOTIFICATION_POLICY,
        "Counsel / compliance",
        "NOTIFICATION_POLICY",
        "Jurisdiction-specific notices, timing and required content are approved.",
        True,
    ),
    ClosureItem(
        ClosureWorkstream.SECURITY_OPERATIONS,
        "Security / operations reviewer",
        "SECURITY_OPERATIONS",
        "All required production security and operational controls independently verified.",
        True,
    ),
    ClosureItem(
        ClosureWorkstream.BACKUP_RESTORE,
        "Infrastructure / operations",
        "BACKUP_RESTORE",
        "Real-environment encrypted off-site backup and restore/rollback drill evidence approved.",
        True,
    ),
    ClosureItem(
        ClosureWorkstream.INCIDENT_RESPONSE,
        "Incident owner / operations",
        "INCIDENT_TABLETOP",
        "Production incident tabletop completed with accountable operators and evidence.",
        True,
    ),
    ClosureItem(
        ClosureWorkstream.PRODUCTION_UAT,
        "UAT owner / business owner",
        "PRODUCTION_UAT",
        "Production-like UAT against selected live integrations passes.",
        True,
    ),
    ClosureItem(
        ClosureWorkstream.RECONCILIATION,
        "Finance / operations",
        "RECONCILIATION",
        "Provider settlement/customer ledger reconciliation passes in production-like environment.",
        True,
    ),
    ClosureItem(
        ClosureWorkstream.RELEASE_OWNER,
        "Authorized release owner",
        "OWNER_SIGNOFF",
        "Explicit APPROVE decision after all preceding evidence is reviewed.",
        True,
    ),
)


def assess_production_closure(
    *,
    internal_engineering_complete: bool,
    evidence_validation: ProductionEvidenceValidation | None,
    pricing_policy_approved: bool,
    deadline: str = "2026-09-20T18:00:00-04:00",
) -> ProductionClosureStatus:
    reasons: list[str] = []
    open_workstreams: list[str] = []

    if not internal_engineering_complete:
        reasons.append("INTERNAL_ENGINEERING_NOT_COMPLETE")

    valid_for_review = bool(
        evidence_validation is not None
        and evidence_validation.valid_for_review
    )

    if evidence_validation is None:
        reasons.append("PRODUCTION_EVIDENCE_PACKAGE_MISSING")
        open_workstreams.extend(item.workstream.value for item in CLOSURE_ITEMS)
    else:
        if evidence_validation.missing_categories:
            reasons.extend(
                f"MISSING_EVIDENCE:{category}"
                for category in evidence_validation.missing_categories
            )
        reasons.extend(
            f"INVALID_EVIDENCE:{reason}"
            for reason in evidence_validation.invalid_reasons
        )
        missing_or_invalid = set(evidence_validation.missing_categories)
        invalid_categories = {
            reason.split(":", 1)[0]
            for reason in evidence_validation.invalid_reasons
            if ":" in reason
        }
        blocked_categories = missing_or_invalid | invalid_categories
        for item in CLOSURE_ITEMS:
            if item.evidence_category in blocked_categories:
                open_workstreams.append(item.workstream.value)

    if not pricing_policy_approved:
        reasons.append("INDEPENDENT_CHARGE_POLICY_APPROVAL_MISSING")
        if ClosureWorkstream.PRICING_POLICY.value not in open_workstreams:
            open_workstreams.append(ClosureWorkstream.PRICING_POLICY.value)

    # This assessment intentionally cannot grant production authority. Final
    # production authorization remains a separately controlled human action
    # after package validation and canonical evidence import.
    production_authorized = False

    work_items_closed = (
        internal_engineering_complete
        and valid_for_review
        and pricing_policy_approved
        and not open_workstreams
    )

    if work_items_closed:
        reasons.append(
            "READY_FOR_CONTROLLED_HUMAN_EVIDENCE_IMPORT_AND_FINAL_AUTHORIZATION"
        )

    return ProductionClosureStatus(
        work_items_closed=work_items_closed,
        production_authorized=production_authorized,
        internal_engineering_complete=internal_engineering_complete,
        external_evidence_valid_for_review=valid_for_review,
        open_workstreams=tuple(dict.fromkeys(open_workstreams)),
        blocker_reasons=tuple(reasons),
        target_deadline=deadline,
    )
