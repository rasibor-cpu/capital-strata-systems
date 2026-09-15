from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class CommercializationUatScenario(str, Enum):
    TRIAL_SIGNUP = "TRIAL_SIGNUP"
    TRIAL_CANCEL_BEFORE_EXPIRY = "TRIAL_CANCEL_BEFORE_EXPIRY"
    TRIAL_CONVERSION = "TRIAL_CONVERSION"
    CSS_LOSS_PERIOD = "CSS_LOSS_PERIOD"
    CSS_RECOVERY_ONLY = "CSS_RECOVERY_ONLY"
    CSS_FRESH_GAIN_FEE = "CSS_FRESH_GAIN_FEE"
    INDEPENDENT_CUSTOMER_DIRECTED = "INDEPENDENT_CUSTOMER_DIRECTED"
    FX_CONVERSION = "FX_CONVERSION"
    CORRECTION_REVERSAL = "CORRECTION_REVERSAL"
    DISPUTE_REFUND = "DISPUTE_REFUND"
    CUSTOMER_STATEMENT_RECONCILIATION = "CUSTOMER_STATEMENT_RECONCILIATION"


class UatResultStatus(str, Enum):
    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


REQUIRED_COMMERCIALIZATION_UAT_SCENARIOS = tuple(CommercializationUatScenario)


@dataclass(frozen=True, slots=True)
class CommercializationUatResult:
    run_id: str
    scenario: CommercializationUatScenario
    status: UatResultStatus
    executed_at: str
    environment_reference: str
    evidence_refs: Tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("run_id", "executed_at", "environment_reference"):
            value = getattr(self, name)
            if not value or value != value.strip():
                raise ValueError(f"{name} is required and must be canonical")
        if not isinstance(self.scenario, CommercializationUatScenario):
            raise TypeError("scenario must be CommercializationUatScenario")
        if not isinstance(self.status, UatResultStatus):
            raise TypeError("status must be UatResultStatus")
        if not isinstance(self.evidence_refs, tuple) or not self.evidence_refs:
            raise ValueError("UAT result requires immutable evidence refs")


@dataclass(frozen=True, slots=True)
class CommercializationUatAssessment:
    complete: bool
    missing_scenarios: Tuple[CommercializationUatScenario, ...]
    failed_scenarios: Tuple[CommercializationUatScenario, ...]
    blocked_scenarios: Tuple[CommercializationUatScenario, ...]


def assess_commercialization_uat(
    results: Tuple[CommercializationUatResult, ...],
) -> CommercializationUatAssessment:
    latest: dict[CommercializationUatScenario, CommercializationUatResult] = {}
    for result in results:
        if not isinstance(result, CommercializationUatResult):
            raise TypeError("results must contain CommercializationUatResult values")
        latest[result.scenario] = result

    missing = tuple(
        scenario for scenario in REQUIRED_COMMERCIALIZATION_UAT_SCENARIOS
        if scenario not in latest
    )
    failed = tuple(
        scenario for scenario, result in latest.items()
        if result.status == UatResultStatus.FAILED
    )
    blocked = tuple(
        scenario for scenario, result in latest.items()
        if result.status == UatResultStatus.BLOCKED
    )
    pending = any(
        result.status == UatResultStatus.PENDING
        for result in latest.values()
    )

    return CommercializationUatAssessment(
        complete=not missing and not failed and not blocked and not pending,
        missing_scenarios=missing,
        failed_scenarios=failed,
        blocked_scenarios=blocked,
    )
