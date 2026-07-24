"""PPF-003 Enterprise Execution Governance Gateway.

The gateway is the advisory-only governance entry point for execution engines.
It delegates constitutional budget decisions to PPF-001 and exposure accounting
to PPF-002. It does not calculate budget, calculate exposure, submit orders,
persist state, or grant live execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Mapping

from backend.governance.enterprise_exposure_registry import (
    DEFAULT_ALLOWED_MODULES,
    DEFAULT_OWNER_ID,
    EnterpriseExposureRegistry,
    EnterpriseExposureReservation,
    EnterpriseExposureState,
    ExposureOperationStatus,
    ExposureReasonCode,
    ExposureRegistryOperationResult,
)
from backend.governance.enterprise_profit_protection_contracts import (
    EnterpriseProfitProtectionPolicy,
    PPFEnforcementStatus,
    PPFRiskDecision,
    PPFRiskRequest,
)
from backend.governance.enterprise_profit_protection_manager import (
    EnterpriseProfitProtectionManager,
)


SCHEMA_VERSION = "css.ppf003.enterprise_execution_gateway.v1"


class EnterpriseExecutionGatewayStatus(str, Enum):
    ADVISORY_APPROVED = "ADVISORY_APPROVED"
    ADVISORY_REJECTED = "ADVISORY_REJECTED"
    FAIL_CLOSED = "FAIL_CLOSED"


class EnterpriseExecutionGatewayReasonCode(str, Enum):
    OK = "OK"
    ADVISORY_ONLY = "ADVISORY_ONLY"
    PPF_EVALUATED = "PPF_EVALUATED"
    PPF_APPROVED = "PPF_APPROVED"
    CONSTITUTIONAL_POLICY_REJECTED = "CONSTITUTIONAL_POLICY_REJECTED"
    EXPOSURE_REGISTRY_ACCEPTED = "EXPOSURE_REGISTRY_ACCEPTED"
    EXPOSURE_REGISTRY_REJECTED = "EXPOSURE_REGISTRY_REJECTED"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    DUPLICATE_RESERVATION = "DUPLICATE_RESERVATION"
    EXPOSURE_RESERVED = "EXPOSURE_RESERVED"
    EXPOSURE_COMMITTED = "EXPOSURE_COMMITTED"
    EXPOSURE_RELEASED = "EXPOSURE_RELEASED"
    EXECUTION_REJECTED = "EXECUTION_REJECTED"
    MISSING_GOVERNANCE_STATE = "MISSING_GOVERNANCE_STATE"
    STALE_GOVERNANCE_STATE = "STALE_GOVERNANCE_STATE"
    INVALID_EXECUTION_REQUEST = "INVALID_EXECUTION_REQUEST"
    UNKNOWN_MODULE = "UNKNOWN_MODULE"
    INVALID_RISK_REQUEST = "INVALID_RISK_REQUEST"
    RESERVATION_OWNER_INVALID = "RESERVATION_OWNER_INVALID"
    MISSING_RESERVATION = "MISSING_RESERVATION"
    BUDGET_SOURCE_PPF = "BUDGET_SOURCE_PPF"
    PRINCIPAL_EXCLUDED = "PRINCIPAL_EXCLUDED"


@dataclass(frozen=True)
class EnterpriseExecutionRequest:
    request_id: str
    reservation_id: str
    module: str
    owner_id: str
    requested_exposure: Decimal | str | int | float
    risk_request: PPFRiskRequest | None
    ttl_seconds: int | None = None
    metadata: Mapping[str, Any] | None = None
    source: str = "PPF003_EXECUTION_REQUEST"

    def as_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "reservation_id": self.reservation_id,
            "module": self.module,
            "owner_id": self.owner_id,
            "requested_exposure": str(self.requested_exposure),
            "risk_request": self.risk_request.request_id if self.risk_request else None,
            "ttl_seconds": self.ttl_seconds,
            "metadata": dict(self.metadata or {}),
            "source": self.source,
        }


@dataclass(frozen=True)
class EnterpriseExecutionGatewayState:
    schema_version: str
    ppf_decision: PPFRiskDecision | None
    exposure_state: EnterpriseExposureState | None
    stale: bool
    reason_codes: tuple[EnterpriseExecutionGatewayReasonCode, ...]
    upstream_reason_codes: tuple[str, ...]
    advisory_only: bool = True
    execution_allowed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "ppf_decision": self.ppf_decision.as_dict() if self.ppf_decision else None,
            "exposure_state": self.exposure_state.as_dict() if self.exposure_state else None,
            "stale": self.stale,
            "reason_codes": [code.value for code in self.reason_codes],
            "upstream_reason_codes": list(self.upstream_reason_codes),
            "advisory_only": True,
            "execution_allowed": False,
        }


@dataclass(frozen=True)
class EnterpriseExecutionGatewayDecision:
    request_id: str
    operation: str
    status: EnterpriseExecutionGatewayStatus
    accepted: bool
    reason_codes: tuple[EnterpriseExecutionGatewayReasonCode, ...]
    upstream_reason_codes: tuple[str, ...]
    ppf_decision: PPFRiskDecision | None
    registry_result: ExposureRegistryOperationResult | None
    reservation: EnterpriseExposureReservation | None
    state: EnterpriseExecutionGatewayState
    advisory_only: bool = True
    execution_allowed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "request_id": self.request_id,
            "operation": self.operation,
            "status": self.status.value,
            "accepted": self.accepted,
            "reason_codes": [code.value for code in self.reason_codes],
            "upstream_reason_codes": list(self.upstream_reason_codes),
            "ppf_decision": self.ppf_decision.as_dict() if self.ppf_decision else None,
            "registry_result": self.registry_result.as_dict() if self.registry_result else None,
            "reservation": self.reservation.as_dict() if self.reservation else None,
            "state": self.state.as_dict(),
            "advisory_only": True,
            "execution_allowed": False,
        }


class EnterpriseExecutionGateway:
    """Advisory-only gateway for execution governance orchestration."""

    def __init__(
        self,
        *,
        profit_protection_manager: EnterpriseProfitProtectionManager | None = None,
        exposure_registry: EnterpriseExposureRegistry | None = None,
        allowed_modules: tuple[str, ...] = DEFAULT_ALLOWED_MODULES,
        max_registry_age_seconds: int = 300,
    ) -> None:
        self.profit_protection_manager = profit_protection_manager or EnterpriseProfitProtectionManager()
        self.exposure_registry = exposure_registry
        self.allowed_modules = tuple(_normalize_module(module) for module in allowed_modules)
        self.max_registry_age_seconds = int(max_registry_age_seconds)
        self._latest_ppf_decision: PPFRiskDecision | None = None

    def evaluate_trade_request(
        self,
        request: EnterpriseExecutionRequest,
        *,
        policy: EnterpriseProfitProtectionPolicy | None = None,
        now: datetime | None = None,
    ) -> EnterpriseExecutionGatewayDecision:
        now_dt = now or _now()
        evaluated = self._evaluate_request(request, policy=policy, now=now_dt)
        if evaluated["errors"]:
            return self._decision(
                request_id=_request_id(request),
                operation="evaluate_trade_request",
                status=self._status_from_errors(evaluated["errors"]),
                reasons=evaluated["errors"],
                ppf_decision=evaluated.get("ppf_decision"),
                registry_result=None,
                now=now_dt,
                upstream=evaluated["upstream"],
            )
        return self._decision(
            request_id=request.request_id,
            operation="evaluate_trade_request",
            status=EnterpriseExecutionGatewayStatus.ADVISORY_APPROVED,
            reasons=(
                EnterpriseExecutionGatewayReasonCode.PPF_EVALUATED,
                EnterpriseExecutionGatewayReasonCode.PPF_APPROVED,
                EnterpriseExecutionGatewayReasonCode.BUDGET_SOURCE_PPF,
                EnterpriseExecutionGatewayReasonCode.PRINCIPAL_EXCLUDED,
                EnterpriseExecutionGatewayReasonCode.OK,
            ),
            ppf_decision=evaluated["ppf_decision"],
            registry_result=None,
            now=now_dt,
            upstream=evaluated["upstream"],
        )

    def request_exposure_reservation(
        self,
        request: EnterpriseExecutionRequest,
        *,
        policy: EnterpriseProfitProtectionPolicy | None = None,
        now: datetime | None = None,
    ) -> EnterpriseExecutionGatewayDecision:
        now_dt = now or _now()
        evaluated = self._evaluate_request(request, policy=policy, now=now_dt)
        if evaluated["errors"]:
            return self._decision(
                request_id=_request_id(request),
                operation="request_exposure_reservation",
                status=self._status_from_errors(evaluated["errors"]),
                reasons=evaluated["errors"],
                ppf_decision=evaluated.get("ppf_decision"),
                registry_result=None,
                now=now_dt,
                upstream=evaluated["upstream"],
            )

        registry = self.exposure_registry
        if registry is None:
            return self._missing_state("request_exposure_reservation", request_id=request.request_id, now=now_dt)
        registry_result = registry.reserve_exposure(
            reservation_id=request.reservation_id,
            module=request.module,
            amount=evaluated["requested_exposure"],
            owner_id=request.owner_id,
            ttl_seconds=request.ttl_seconds,
            metadata=request.metadata,
            now=now_dt,
        )
        if registry_result.accepted:
            reasons = (
                EnterpriseExecutionGatewayReasonCode.PPF_EVALUATED,
                EnterpriseExecutionGatewayReasonCode.PPF_APPROVED,
                EnterpriseExecutionGatewayReasonCode.BUDGET_SOURCE_PPF,
                EnterpriseExecutionGatewayReasonCode.PRINCIPAL_EXCLUDED,
                EnterpriseExecutionGatewayReasonCode.EXPOSURE_REGISTRY_ACCEPTED,
                EnterpriseExecutionGatewayReasonCode.EXPOSURE_RESERVED,
                EnterpriseExecutionGatewayReasonCode.OK,
            )
            status = EnterpriseExecutionGatewayStatus.ADVISORY_APPROVED
        else:
            reasons = (
                EnterpriseExecutionGatewayReasonCode.EXPOSURE_REGISTRY_REJECTED,
                *self._registry_reason_codes(registry_result),
            )
            status = EnterpriseExecutionGatewayStatus.ADVISORY_REJECTED
        return self._decision(
            request_id=request.request_id,
            operation="request_exposure_reservation",
            status=status,
            reasons=reasons,
            ppf_decision=evaluated["ppf_decision"],
            registry_result=registry_result,
            now=now_dt,
            upstream=(*evaluated["upstream"], *_reason_values(registry_result.reason_codes)),
        )

    def commit_execution(
        self,
        reservation_id: str,
        *,
        owner_id: str = DEFAULT_OWNER_ID,
        now: datetime | None = None,
    ) -> EnterpriseExecutionGatewayDecision:
        return self._mutate_reservation(
            operation="commit_execution",
            reservation_id=reservation_id,
            owner_id=owner_id,
            registry_method="commit_reservation",
            success_reason=EnterpriseExecutionGatewayReasonCode.EXPOSURE_COMMITTED,
            now=now,
        )

    def release_execution(
        self,
        reservation_id: str,
        *,
        owner_id: str = DEFAULT_OWNER_ID,
        now: datetime | None = None,
    ) -> EnterpriseExecutionGatewayDecision:
        return self._mutate_reservation(
            operation="release_execution",
            reservation_id=reservation_id,
            owner_id=owner_id,
            registry_method="release_reservation",
            success_reason=EnterpriseExecutionGatewayReasonCode.EXPOSURE_RELEASED,
            now=now,
        )

    def reject_execution(
        self,
        reservation_id: str,
        *,
        owner_id: str = DEFAULT_OWNER_ID,
        now: datetime | None = None,
    ) -> EnterpriseExecutionGatewayDecision:
        return self._mutate_reservation(
            operation="reject_execution",
            reservation_id=reservation_id,
            owner_id=owner_id,
            registry_method="release_reservation",
            success_reason=EnterpriseExecutionGatewayReasonCode.EXECUTION_REJECTED,
            now=now,
        )

    def current_governance_state(
        self,
        *,
        now: datetime | None = None,
    ) -> EnterpriseExecutionGatewayState:
        now_dt = now or _now()
        exposure_state = self.exposure_registry.current_state(now=now_dt) if self.exposure_registry else None
        stale = exposure_state.stale if exposure_state else True
        reasons: list[EnterpriseExecutionGatewayReasonCode] = [EnterpriseExecutionGatewayReasonCode.ADVISORY_ONLY]
        if self._latest_ppf_decision is None or exposure_state is None:
            reasons.append(EnterpriseExecutionGatewayReasonCode.MISSING_GOVERNANCE_STATE)
        elif stale:
            reasons.append(EnterpriseExecutionGatewayReasonCode.STALE_GOVERNANCE_STATE)
        else:
            reasons.extend(
                (
                    EnterpriseExecutionGatewayReasonCode.PPF_EVALUATED,
                    EnterpriseExecutionGatewayReasonCode.BUDGET_SOURCE_PPF,
                    EnterpriseExecutionGatewayReasonCode.PRINCIPAL_EXCLUDED,
                    EnterpriseExecutionGatewayReasonCode.OK,
                )
            )
        upstream: tuple[str, ...] = ()
        if self._latest_ppf_decision:
            upstream = (*upstream, *_reason_values(self._latest_ppf_decision.reason_codes))
        if exposure_state:
            upstream = (*upstream, *_reason_values(exposure_state.reason_codes))
        return EnterpriseExecutionGatewayState(
            schema_version=SCHEMA_VERSION,
            ppf_decision=self._latest_ppf_decision,
            exposure_state=exposure_state,
            stale=stale,
            reason_codes=_dedupe(reasons),
            upstream_reason_codes=_dedupe_str(upstream),
        )

    def _evaluate_request(
        self,
        request: EnterpriseExecutionRequest,
        *,
        policy: EnterpriseProfitProtectionPolicy | None,
        now: datetime,
    ) -> dict[str, Any]:
        errors, exposure_amount = self._validate_execution_request(request)
        upstream: tuple[str, ...] = ()
        if errors:
            return {
                "errors": errors,
                "ppf_decision": None,
                "requested_exposure": exposure_amount,
                "upstream": upstream,
            }
        try:
            ppf_decision = self.profit_protection_manager.evaluate(
                request.risk_request,
                policy=policy,
                now=now,
            )
        except Exception:
            return {
                "errors": (EnterpriseExecutionGatewayReasonCode.INVALID_RISK_REQUEST,),
                "ppf_decision": None,
                "requested_exposure": exposure_amount,
                "upstream": upstream,
            }

        self._latest_ppf_decision = ppf_decision
        upstream = _reason_values(ppf_decision.reason_codes)
        if ppf_decision.enforcement_status is not PPFEnforcementStatus.ADVISORY_APPROVED:
            return {
                "errors": (
                    EnterpriseExecutionGatewayReasonCode.PPF_EVALUATED,
                    EnterpriseExecutionGatewayReasonCode.CONSTITUTIONAL_POLICY_REJECTED,
                ),
                "ppf_decision": ppf_decision,
                "requested_exposure": exposure_amount,
                "upstream": upstream,
            }

        registry_errors = self._ensure_registry(ppf_decision, now=now)
        if registry_errors:
            return {
                "errors": registry_errors,
                "ppf_decision": ppf_decision,
                "requested_exposure": exposure_amount,
                "upstream": upstream,
            }

        return {
            "errors": (),
            "ppf_decision": ppf_decision,
            "requested_exposure": exposure_amount,
            "upstream": upstream,
        }

    def _validate_execution_request(
        self,
        request: EnterpriseExecutionRequest,
    ) -> tuple[tuple[EnterpriseExecutionGatewayReasonCode, ...], Decimal | None]:
        errors: list[EnterpriseExecutionGatewayReasonCode] = []
        if not isinstance(request, EnterpriseExecutionRequest):
            return ((EnterpriseExecutionGatewayReasonCode.INVALID_EXECUTION_REQUEST,), None)
        if not str(request.request_id or "").strip() or not str(request.reservation_id or "").strip():
            errors.append(EnterpriseExecutionGatewayReasonCode.INVALID_EXECUTION_REQUEST)
        if not str(request.owner_id or "").strip():
            errors.append(EnterpriseExecutionGatewayReasonCode.RESERVATION_OWNER_INVALID)
        normalized_module = _normalize_module(request.module)
        if not normalized_module:
            errors.append(EnterpriseExecutionGatewayReasonCode.INVALID_EXECUTION_REQUEST)
        elif normalized_module not in self.allowed_modules:
            errors.append(EnterpriseExecutionGatewayReasonCode.UNKNOWN_MODULE)
        exposure_amount = _decimal(request.requested_exposure)
        if exposure_amount is None or exposure_amount <= Decimal("0"):
            errors.append(EnterpriseExecutionGatewayReasonCode.INVALID_EXECUTION_REQUEST)
        if request.risk_request is None:
            errors.append(EnterpriseExecutionGatewayReasonCode.INVALID_RISK_REQUEST)
        return _dedupe(errors), exposure_amount

    def _ensure_registry(
        self,
        ppf_decision: PPFRiskDecision,
        *,
        now: datetime,
    ) -> tuple[EnterpriseExecutionGatewayReasonCode, ...]:
        if self.exposure_registry is None:
            self.exposure_registry = EnterpriseExposureRegistry(
                profit_protection_decision=ppf_decision,
                allowed_modules=self.allowed_modules,
                max_registry_age_seconds=self.max_registry_age_seconds,
                created_at=now,
            )
            return ()
        exposure_state = self.exposure_registry.current_state(now=now)
        if exposure_state.stale:
            return (EnterpriseExecutionGatewayReasonCode.STALE_GOVERNANCE_STATE,)
        if exposure_state.enterprise_risk_budget != ppf_decision.adjusted_budget:
            return (EnterpriseExecutionGatewayReasonCode.STALE_GOVERNANCE_STATE,)
        return ()

    def _mutate_reservation(
        self,
        *,
        operation: str,
        reservation_id: str,
        owner_id: str,
        registry_method: str,
        success_reason: EnterpriseExecutionGatewayReasonCode,
        now: datetime | None,
    ) -> EnterpriseExecutionGatewayDecision:
        now_dt = now or _now()
        missing = self._validate_existing_state(now_dt)
        if missing:
            return self._decision(
                request_id=str(reservation_id or "").strip(),
                operation=operation,
                status=EnterpriseExecutionGatewayStatus.FAIL_CLOSED,
                reasons=missing,
                ppf_decision=self._latest_ppf_decision,
                registry_result=None,
                now=now_dt,
                upstream=(),
            )
        registry = self.exposure_registry
        if registry is None:
            return self._missing_state(operation, request_id=reservation_id, now=now_dt)
        method = getattr(registry, registry_method)
        registry_result = method(str(reservation_id or "").strip(), owner_id=owner_id, now=now_dt)
        if registry_result.accepted:
            reasons = (
                EnterpriseExecutionGatewayReasonCode.EXPOSURE_REGISTRY_ACCEPTED,
                success_reason,
                EnterpriseExecutionGatewayReasonCode.OK,
            )
            status = EnterpriseExecutionGatewayStatus.ADVISORY_APPROVED
        else:
            reasons = (
                EnterpriseExecutionGatewayReasonCode.EXPOSURE_REGISTRY_REJECTED,
                *self._registry_reason_codes(registry_result),
            )
            status = EnterpriseExecutionGatewayStatus.FAIL_CLOSED
        return self._decision(
            request_id=str(reservation_id or "").strip(),
            operation=operation,
            status=status,
            reasons=reasons,
            ppf_decision=self._latest_ppf_decision,
            registry_result=registry_result,
            now=now_dt,
            upstream=_reason_values(registry_result.reason_codes),
        )

    def _validate_existing_state(
        self,
        now: datetime,
    ) -> tuple[EnterpriseExecutionGatewayReasonCode, ...]:
        if self._latest_ppf_decision is None or self.exposure_registry is None:
            return (EnterpriseExecutionGatewayReasonCode.MISSING_GOVERNANCE_STATE,)
        exposure_state = self.exposure_registry.current_state(now=now)
        if exposure_state.stale:
            return (EnterpriseExecutionGatewayReasonCode.STALE_GOVERNANCE_STATE,)
        return ()

    def _missing_state(
        self,
        operation: str,
        *,
        request_id: str,
        now: datetime,
    ) -> EnterpriseExecutionGatewayDecision:
        return self._decision(
            request_id=request_id,
            operation=operation,
            status=EnterpriseExecutionGatewayStatus.FAIL_CLOSED,
            reasons=(EnterpriseExecutionGatewayReasonCode.MISSING_GOVERNANCE_STATE,),
            ppf_decision=self._latest_ppf_decision,
            registry_result=None,
            now=now,
            upstream=(),
        )

    def _decision(
        self,
        *,
        request_id: str,
        operation: str,
        status: EnterpriseExecutionGatewayStatus,
        reasons: tuple[EnterpriseExecutionGatewayReasonCode, ...],
        ppf_decision: PPFRiskDecision | None,
        registry_result: ExposureRegistryOperationResult | None,
        now: datetime,
        upstream: tuple[str, ...],
    ) -> EnterpriseExecutionGatewayDecision:
        reason_codes = _dedupe((EnterpriseExecutionGatewayReasonCode.ADVISORY_ONLY, *reasons))
        state = self.current_governance_state(now=now)
        return EnterpriseExecutionGatewayDecision(
            request_id=request_id,
            operation=operation,
            status=status,
            accepted=status is EnterpriseExecutionGatewayStatus.ADVISORY_APPROVED,
            reason_codes=reason_codes,
            upstream_reason_codes=_dedupe_str(upstream),
            ppf_decision=ppf_decision,
            registry_result=registry_result,
            reservation=registry_result.reservation if registry_result else None,
            state=state,
        )

    @staticmethod
    def _registry_reason_codes(
        registry_result: ExposureRegistryOperationResult,
    ) -> tuple[EnterpriseExecutionGatewayReasonCode, ...]:
        reasons: list[EnterpriseExecutionGatewayReasonCode] = []
        if ExposureReasonCode.OWNER_MISMATCH in registry_result.reason_codes:
            reasons.append(EnterpriseExecutionGatewayReasonCode.RESERVATION_OWNER_INVALID)
        if ExposureReasonCode.MISSING_RESERVATION in registry_result.reason_codes:
            reasons.append(EnterpriseExecutionGatewayReasonCode.MISSING_RESERVATION)
        if ExposureReasonCode.BUDGET_EXCEEDED in registry_result.reason_codes:
            reasons.append(EnterpriseExecutionGatewayReasonCode.BUDGET_EXCEEDED)
        if ExposureReasonCode.DUPLICATE_RESERVATION in registry_result.reason_codes:
            reasons.append(EnterpriseExecutionGatewayReasonCode.DUPLICATE_RESERVATION)
        if ExposureReasonCode.REGISTRY_STALE in registry_result.reason_codes:
            reasons.append(EnterpriseExecutionGatewayReasonCode.STALE_GOVERNANCE_STATE)
        if ExposureReasonCode.UNKNOWN_MODULE in registry_result.reason_codes:
            reasons.append(EnterpriseExecutionGatewayReasonCode.UNKNOWN_MODULE)
        if not reasons:
            reasons.append(EnterpriseExecutionGatewayReasonCode.INVALID_EXECUTION_REQUEST)
        return _dedupe(reasons)

    @staticmethod
    def _status_from_errors(
        errors: tuple[EnterpriseExecutionGatewayReasonCode, ...],
    ) -> EnterpriseExecutionGatewayStatus:
        fail_closed = {
            EnterpriseExecutionGatewayReasonCode.MISSING_GOVERNANCE_STATE,
            EnterpriseExecutionGatewayReasonCode.STALE_GOVERNANCE_STATE,
            EnterpriseExecutionGatewayReasonCode.INVALID_EXECUTION_REQUEST,
            EnterpriseExecutionGatewayReasonCode.UNKNOWN_MODULE,
            EnterpriseExecutionGatewayReasonCode.INVALID_RISK_REQUEST,
            EnterpriseExecutionGatewayReasonCode.RESERVATION_OWNER_INVALID,
        }
        if any(error in fail_closed for error in errors):
            return EnterpriseExecutionGatewayStatus.FAIL_CLOSED
        return EnterpriseExecutionGatewayStatus.ADVISORY_REJECTED


def _request_id(request: Any) -> str:
    return str(getattr(request, "request_id", "") or "").strip()


def _decimal(value: Any) -> Decimal | None:
    text = repr(value) if isinstance(value, float) else str(value)
    try:
        converted = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    if not converted.is_finite():
        return None
    return converted


def _normalize_module(module: str | None) -> str:
    return str(module or "").strip().upper()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _reason_values(reasons: tuple[Any, ...]) -> tuple[str, ...]:
    return tuple(reason.value if hasattr(reason, "value") else str(reason) for reason in reasons)


def _dedupe(
    reasons: tuple[EnterpriseExecutionGatewayReasonCode, ...] | list[EnterpriseExecutionGatewayReasonCode],
) -> tuple[EnterpriseExecutionGatewayReasonCode, ...]:
    result: list[EnterpriseExecutionGatewayReasonCode] = []
    for reason in reasons:
        if reason not in result:
            result.append(reason)
    return tuple(result)


def _dedupe_str(reasons: tuple[str, ...]) -> tuple[str, ...]:
    result: list[str] = []
    for reason in reasons:
        if reason not in result:
            result.append(reason)
    return tuple(result)


__all__ = [
    "SCHEMA_VERSION",
    "EnterpriseExecutionGateway",
    "EnterpriseExecutionGatewayDecision",
    "EnterpriseExecutionGatewayReasonCode",
    "EnterpriseExecutionGatewayState",
    "EnterpriseExecutionGatewayStatus",
    "EnterpriseExecutionRequest",
]
