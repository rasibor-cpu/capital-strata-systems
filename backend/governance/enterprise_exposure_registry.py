"""PPF-002 Enterprise Exposure Registry.

The registry is the canonical advisory-only authority for enterprise exposure
accounting. It accepts budget from EnterpriseProfitProtectionManager decisions
and never computes, persists, or increases budget.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Mapping

from backend.governance.enterprise_profit_protection_contracts import (
    PPFEnforcementStatus,
    PPFRiskDecision,
)


SCHEMA_VERSION = "css.ppf002.enterprise_exposure_registry.v1"


class ExposureReservationStatus(str, Enum):
    RESERVED = "RESERVED"
    COMMITTED = "COMMITTED"
    RELEASED = "RELEASED"
    EXPIRED = "EXPIRED"


class ExposureOperationStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    IDEMPOTENT = "IDEMPOTENT"
    REJECTED = "REJECTED"


class ExposureReasonCode(str, Enum):
    OK = "OK"
    ADVISORY_ONLY = "ADVISORY_ONLY"
    BUDGET_SOURCE_PPF = "BUDGET_SOURCE_PPF"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    DUPLICATE_RESERVATION = "DUPLICATE_RESERVATION"
    IDEMPOTENT_REPLAY = "IDEMPOTENT_REPLAY"
    REGISTRY_STALE = "REGISTRY_STALE"
    INCONSISTENT_RESERVATION_STATE = "INCONSISTENT_RESERVATION_STATE"
    MISSING_RESERVATION = "MISSING_RESERVATION"
    INVALID_RESERVATION = "INVALID_RESERVATION"
    INVALID_IDENTIFIER = "INVALID_IDENTIFIER"
    UNKNOWN_MODULE = "UNKNOWN_MODULE"
    NEGATIVE_EXPOSURE = "NEGATIVE_EXPOSURE"
    INPUT_NOT_FINITE = "INPUT_NOT_FINITE"
    ORPHAN_RESERVATION_DETECTED = "ORPHAN_RESERVATION_DETECTED"
    RECONCILIATION_MISMATCH = "RECONCILIATION_MISMATCH"
    RESERVATION_EXPIRED = "RESERVATION_EXPIRED"
    OWNER_MISMATCH = "OWNER_MISMATCH"
    PRINCIPAL_EXCLUDED = "PRINCIPAL_EXCLUDED"


DEFAULT_ALLOWED_MODULES = (
    "GOVERNANCE",
    "RISK",
    "PORTFOLIO",
    "TRADING_RUNTIME",
    "OPTIONS",
    "FUTURES",
    "MISSION_CONTROL",
)

DEFAULT_OWNER_ID = "ENTERPRISE_GOVERNANCE"


@dataclass(frozen=True)
class EnterpriseExposureReservation:
    reservation_id: str
    module: str
    owner_id: str
    amount: Decimal
    status: ExposureReservationStatus
    created_at: str
    expires_at: str | None
    committed_at: str | None = None
    released_at: str | None = None
    expired_at: str | None = None
    metadata: Mapping[str, Any] | None = None
    advisory_only: bool = True
    execution_allowed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "reservation_id": self.reservation_id,
            "module": self.module,
            "owner_id": self.owner_id,
            "amount": str(self.amount),
            "status": self.status.value,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "committed_at": self.committed_at,
            "released_at": self.released_at,
            "expired_at": self.expired_at,
            "metadata": dict(self.metadata or {}),
            "advisory_only": True,
            "execution_allowed": False,
        }


@dataclass(frozen=True)
class EnterpriseExposureState:
    schema_version: str
    enterprise_risk_budget: Decimal
    current_enterprise_exposure: Decimal
    reserved_exposure: Decimal
    remaining_enterprise_risk_budget: Decimal
    active_reservation_count: int
    reservation_count: int
    module_attribution: Mapping[str, Mapping[str, Decimal]]
    stale: bool
    reason_codes: tuple[ExposureReasonCode, ...]
    advisory_only: bool = True
    execution_allowed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "enterprise_risk_budget": str(self.enterprise_risk_budget),
            "current_enterprise_exposure": str(self.current_enterprise_exposure),
            "reserved_exposure": str(self.reserved_exposure),
            "remaining_enterprise_risk_budget": str(self.remaining_enterprise_risk_budget),
            "active_reservation_count": self.active_reservation_count,
            "reservation_count": self.reservation_count,
            "module_attribution": {
                module: {key: str(value) for key, value in values.items()}
                for module, values in self.module_attribution.items()
            },
            "stale": self.stale,
            "reason_codes": [code.value for code in self.reason_codes],
            "advisory_only": True,
            "execution_allowed": False,
        }


@dataclass(frozen=True)
class ExposureRegistryOperationResult:
    status: ExposureOperationStatus
    accepted: bool
    reason_codes: tuple[ExposureReasonCode, ...]
    reservation: EnterpriseExposureReservation | None
    state: EnterpriseExposureState
    advisory_only: bool = True
    execution_allowed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "accepted": self.accepted,
            "reason_codes": [code.value for code in self.reason_codes],
            "reservation": self.reservation.as_dict() if self.reservation else None,
            "state": self.state.as_dict(),
            "advisory_only": True,
            "execution_allowed": False,
        }


class EnterpriseExposureRegistry:
    """Thread-safe in-memory registry for advisory exposure accounting."""

    def __init__(
        self,
        *,
        profit_protection_decision: PPFRiskDecision,
        allowed_modules: tuple[str, ...] = DEFAULT_ALLOWED_MODULES,
        max_registry_age_seconds: int = 300,
        created_at: datetime | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self.allowed_modules = tuple(_normalize_module(module) for module in allowed_modules)
        self.max_registry_age_seconds = int(max_registry_age_seconds)
        self.created_at = _iso(created_at or _now())
        self._reservations: dict[str, EnterpriseExposureReservation] = {}
        self._budget = self._budget_from_decision(profit_protection_decision)

    @property
    def enterprise_risk_budget(self) -> Decimal:
        return self._budget

    def reserve_exposure(
        self,
        *,
        reservation_id: str,
        module: str,
        amount: Decimal | str | int | float,
        owner_id: str = DEFAULT_OWNER_ID,
        ttl_seconds: int | None = None,
        metadata: Mapping[str, Any] | None = None,
        now: datetime | None = None,
    ) -> ExposureRegistryOperationResult:
        with self._lock:
            now_dt = now or _now()
            failed = self._preflight(now_dt)
            if failed:
                return self._result(ExposureOperationStatus.REJECTED, failed, None, now_dt)
            valid = self._validate_new_reservation(reservation_id, module, owner_id, amount)
            if valid["errors"]:
                return self._result(ExposureOperationStatus.REJECTED, valid["errors"], None, now_dt)

            normalized_id = str(reservation_id).strip()
            normalized_module = _normalize_module(module)
            normalized_owner = valid["owner_id"]
            exposure_amount = valid["amount"]
            existing = self._reservations.get(normalized_id)
            if existing is not None:
                if (
                    existing.status is ExposureReservationStatus.RESERVED
                    and existing.module == normalized_module
                    and existing.owner_id == normalized_owner
                    and existing.amount == exposure_amount
                    and not self._reservation_expired(existing, now_dt)
                ):
                    return self._result(
                        ExposureOperationStatus.IDEMPOTENT,
                        (ExposureReasonCode.IDEMPOTENT_REPLAY,),
                        existing,
                        now_dt,
                    )
                return self._result(
                    ExposureOperationStatus.REJECTED,
                    (ExposureReasonCode.DUPLICATE_RESERVATION,),
                    existing,
                    now_dt,
                )

            if self.remaining_budget(now=now_dt) < exposure_amount:
                return self._result(
                    ExposureOperationStatus.REJECTED,
                    (ExposureReasonCode.BUDGET_EXCEEDED,),
                    None,
                    now_dt,
                )

            expires_at = _iso(now_dt + timedelta(seconds=ttl_seconds)) if ttl_seconds is not None else None
            reservation = EnterpriseExposureReservation(
                reservation_id=normalized_id,
                module=normalized_module,
                owner_id=normalized_owner,
                amount=exposure_amount,
                status=ExposureReservationStatus.RESERVED,
                created_at=_iso(now_dt),
                expires_at=expires_at,
                metadata=dict(metadata or {}),
            )
            self._reservations[normalized_id] = reservation
            return self._result(ExposureOperationStatus.ACCEPTED, (ExposureReasonCode.OK,), reservation, now_dt)

    def commit_reservation(
        self,
        reservation_id: str,
        *,
        owner_id: str = DEFAULT_OWNER_ID,
        now: datetime | None = None,
    ) -> ExposureRegistryOperationResult:
        with self._lock:
            now_dt = now or _now()
            failed = self._preflight(now_dt)
            if failed:
                return self._result(ExposureOperationStatus.REJECTED, failed, None, now_dt)
            reservation = self._reservations.get(str(reservation_id).strip())
            if reservation is None:
                return self._result(
                    ExposureOperationStatus.REJECTED,
                    (ExposureReasonCode.MISSING_RESERVATION,),
                    None,
                    now_dt,
                )
            owner_error = self._validate_owner(reservation, owner_id)
            if owner_error:
                return self._result(ExposureOperationStatus.REJECTED, owner_error, reservation, now_dt)
            if reservation.status is ExposureReservationStatus.COMMITTED:
                return self._result(
                    ExposureOperationStatus.IDEMPOTENT,
                    (ExposureReasonCode.IDEMPOTENT_REPLAY,),
                    reservation,
                    now_dt,
                )
            if reservation.status is not ExposureReservationStatus.RESERVED:
                return self._result(
                    ExposureOperationStatus.REJECTED,
                    (ExposureReasonCode.INCONSISTENT_RESERVATION_STATE,),
                    reservation,
                    now_dt,
                )
            if self._reservation_expired(reservation, now_dt):
                expired = self._replace(reservation, status=ExposureReservationStatus.EXPIRED, expired_at=_iso(now_dt))
                self._reservations[expired.reservation_id] = expired
                return self._result(
                    ExposureOperationStatus.REJECTED,
                    (ExposureReasonCode.RESERVATION_EXPIRED,),
                    expired,
                    now_dt,
                )
            committed = self._replace(
                reservation,
                status=ExposureReservationStatus.COMMITTED,
                committed_at=_iso(now_dt),
            )
            self._reservations[committed.reservation_id] = committed
            return self._result(ExposureOperationStatus.ACCEPTED, (ExposureReasonCode.OK,), committed, now_dt)

    def release_reservation(
        self,
        reservation_id: str,
        *,
        owner_id: str = DEFAULT_OWNER_ID,
        now: datetime | None = None,
    ) -> ExposureRegistryOperationResult:
        with self._lock:
            now_dt = now or _now()
            failed = self._preflight(now_dt)
            if failed:
                return self._result(ExposureOperationStatus.REJECTED, failed, None, now_dt)
            reservation = self._reservations.get(str(reservation_id).strip())
            if reservation is None:
                return self._result(
                    ExposureOperationStatus.REJECTED,
                    (ExposureReasonCode.MISSING_RESERVATION,),
                    None,
                    now_dt,
                )
            owner_error = self._validate_owner(reservation, owner_id)
            if owner_error:
                return self._result(ExposureOperationStatus.REJECTED, owner_error, reservation, now_dt)
            if reservation.status is ExposureReservationStatus.RELEASED:
                return self._result(
                    ExposureOperationStatus.IDEMPOTENT,
                    (ExposureReasonCode.IDEMPOTENT_REPLAY,),
                    reservation,
                    now_dt,
                )
            if reservation.status is ExposureReservationStatus.EXPIRED:
                return self._result(
                    ExposureOperationStatus.REJECTED,
                    (ExposureReasonCode.INCONSISTENT_RESERVATION_STATE,),
                    reservation,
                    now_dt,
                )
            released = self._replace(
                reservation,
                status=ExposureReservationStatus.RELEASED,
                released_at=_iso(now_dt),
            )
            self._reservations[released.reservation_id] = released
            return self._result(ExposureOperationStatus.ACCEPTED, (ExposureReasonCode.OK,), released, now_dt)

    def expire_reservation(
        self,
        reservation_id: str,
        *,
        owner_id: str = DEFAULT_OWNER_ID,
        now: datetime | None = None,
    ) -> ExposureRegistryOperationResult:
        with self._lock:
            now_dt = now or _now()
            failed = self._preflight(now_dt)
            if failed:
                return self._result(ExposureOperationStatus.REJECTED, failed, None, now_dt)
            reservation = self._reservations.get(str(reservation_id).strip())
            if reservation is None:
                return self._result(
                    ExposureOperationStatus.REJECTED,
                    (ExposureReasonCode.MISSING_RESERVATION,),
                    None,
                    now_dt,
                )
            owner_error = self._validate_owner(reservation, owner_id)
            if owner_error:
                return self._result(ExposureOperationStatus.REJECTED, owner_error, reservation, now_dt)
            if reservation.status is ExposureReservationStatus.EXPIRED:
                return self._result(
                    ExposureOperationStatus.IDEMPOTENT,
                    (ExposureReasonCode.IDEMPOTENT_REPLAY,),
                    reservation,
                    now_dt,
                )
            if reservation.status is not ExposureReservationStatus.RESERVED:
                return self._result(
                    ExposureOperationStatus.REJECTED,
                    (ExposureReasonCode.INCONSISTENT_RESERVATION_STATE,),
                    reservation,
                    now_dt,
                )
            expired = self._replace(
                reservation,
                status=ExposureReservationStatus.EXPIRED,
                expired_at=_iso(now_dt),
            )
            self._reservations[expired.reservation_id] = expired
            return self._result(ExposureOperationStatus.ACCEPTED, (ExposureReasonCode.RESERVATION_EXPIRED,), expired, now_dt)

    def reconcile(
        self,
        observed_committed_exposure: Mapping[str, Decimal | str | int | float] | None = None,
        *,
        now: datetime | None = None,
    ) -> ExposureRegistryOperationResult:
        with self._lock:
            now_dt = now or _now()
            failed = self._preflight(now_dt)
            if failed:
                return self._result(ExposureOperationStatus.REJECTED, failed, None, now_dt)
            for reservation in list(self._reservations.values()):
                if reservation.status is ExposureReservationStatus.RESERVED and self._reservation_expired(reservation, now_dt):
                    self._reservations[reservation.reservation_id] = self._replace(
                        reservation,
                        status=ExposureReservationStatus.EXPIRED,
                        expired_at=_iso(now_dt),
                    )

            errors: list[ExposureReasonCode] = []
            observed: dict[str, Decimal] = {}
            for key, value in dict(observed_committed_exposure or {}).items():
                reservation_id = str(key).strip()
                amount = _decimal(value)
                if not reservation_id:
                    errors.append(ExposureReasonCode.INVALID_IDENTIFIER)
                elif amount is None:
                    errors.append(ExposureReasonCode.INPUT_NOT_FINITE)
                elif amount < Decimal("0"):
                    errors.append(ExposureReasonCode.NEGATIVE_EXPOSURE)
                else:
                    observed[reservation_id] = amount

            for reservation_id, amount in observed.items():
                reservation = self._reservations.get(reservation_id)
                if reservation is None:
                    errors.append(ExposureReasonCode.ORPHAN_RESERVATION_DETECTED)
                elif reservation.status is not ExposureReservationStatus.COMMITTED:
                    errors.append(ExposureReasonCode.RECONCILIATION_MISMATCH)
                elif reservation.amount != amount:
                    errors.append(ExposureReasonCode.RECONCILIATION_MISMATCH)

            if observed:
                for reservation in self._reservations.values():
                    if (
                        reservation.status is ExposureReservationStatus.COMMITTED
                        and reservation.reservation_id not in observed
                    ):
                        errors.append(ExposureReasonCode.RECONCILIATION_MISMATCH)

            if errors:
                return self._result(ExposureOperationStatus.REJECTED, tuple(_dedupe(errors)), None, now_dt)
            return self._result(ExposureOperationStatus.ACCEPTED, (ExposureReasonCode.OK,), None, now_dt)

    def current_state(self, *, now: datetime | None = None) -> EnterpriseExposureState:
        with self._lock:
            return self._state(now or _now())

    def remaining_budget(self, *, now: datetime | None = None) -> Decimal:
        state = self.current_state(now=now)
        return state.remaining_enterprise_risk_budget

    def active_reservations(self, *, module: str | None = None, now: datetime | None = None) -> tuple[EnterpriseExposureReservation, ...]:
        with self._lock:
            now_dt = now or _now()
            normalized_module = _normalize_module(module) if module else None
            return tuple(
                reservation
                for reservation in sorted(self._reservations.values(), key=lambda item: item.reservation_id)
                if reservation.status is ExposureReservationStatus.RESERVED
                and not self._reservation_expired(reservation, now_dt)
                and (normalized_module is None or reservation.module == normalized_module)
            )

    def reservations(self) -> tuple[EnterpriseExposureReservation, ...]:
        with self._lock:
            return tuple(sorted(self._reservations.values(), key=lambda item: item.reservation_id))

    def _budget_from_decision(self, decision: PPFRiskDecision) -> Decimal:
        if decision.enforcement_status is PPFEnforcementStatus.FAIL_CLOSED:
            return Decimal("0")
        budget = _decimal(decision.adjusted_budget)
        if budget is None or budget < Decimal("0"):
            return Decimal("0")
        return budget

    def _preflight(self, now: datetime) -> tuple[ExposureReasonCode, ...]:
        if self._registry_stale(now):
            return (ExposureReasonCode.REGISTRY_STALE,)
        return ()

    def _validate_new_reservation(
        self,
        reservation_id: str,
        module: str,
        owner_id: str,
        amount: Decimal | str | int | float,
    ) -> dict[str, Any]:
        errors: list[ExposureReasonCode] = []
        if not str(reservation_id or "").strip():
            errors.append(ExposureReasonCode.INVALID_IDENTIFIER)
        normalized_owner = str(owner_id or "").strip()
        if not normalized_owner:
            errors.append(ExposureReasonCode.INVALID_IDENTIFIER)
        normalized_module = _normalize_module(module)
        if not normalized_module:
            errors.append(ExposureReasonCode.INVALID_IDENTIFIER)
        elif normalized_module not in self.allowed_modules:
            errors.append(ExposureReasonCode.UNKNOWN_MODULE)
        converted = _decimal(amount)
        if converted is None:
            errors.append(ExposureReasonCode.INPUT_NOT_FINITE)
        elif converted < Decimal("0"):
            errors.append(ExposureReasonCode.NEGATIVE_EXPOSURE)
        elif converted == Decimal("0"):
            errors.append(ExposureReasonCode.INVALID_RESERVATION)
        return {"amount": converted, "owner_id": normalized_owner, "errors": tuple(_dedupe(errors))}

    @staticmethod
    def _validate_owner(
        reservation: EnterpriseExposureReservation,
        owner_id: str,
    ) -> tuple[ExposureReasonCode, ...]:
        normalized_owner = str(owner_id or "").strip()
        if not normalized_owner:
            return (ExposureReasonCode.INVALID_IDENTIFIER,)
        if reservation.owner_id != normalized_owner:
            return (ExposureReasonCode.OWNER_MISMATCH,)
        return ()

    def _registry_stale(self, now: datetime) -> bool:
        created = _parse_time(self.created_at)
        if created is None:
            return True
        return (now.astimezone(timezone.utc) - created).total_seconds() > self.max_registry_age_seconds

    def _state(self, now: datetime) -> EnterpriseExposureState:
        committed = Decimal("0")
        reserved = Decimal("0")
        modules: dict[str, dict[str, Decimal]] = {}
        for reservation in self._reservations.values():
            module = modules.setdefault(
                reservation.module,
                {"committed": Decimal("0"), "reserved": Decimal("0"), "total": Decimal("0")},
            )
            if reservation.status is ExposureReservationStatus.COMMITTED:
                committed += reservation.amount
                module["committed"] += reservation.amount
                module["total"] += reservation.amount
            elif (
                reservation.status is ExposureReservationStatus.RESERVED
                and not self._reservation_expired(reservation, now)
            ):
                reserved += reservation.amount
                module["reserved"] += reservation.amount
                module["total"] += reservation.amount
        used = committed + reserved
        remaining = max(Decimal("0"), self._budget - used)
        stale = self._registry_stale(now)
        reasons = [ExposureReasonCode.ADVISORY_ONLY, ExposureReasonCode.BUDGET_SOURCE_PPF, ExposureReasonCode.PRINCIPAL_EXCLUDED]
        if stale:
            reasons.append(ExposureReasonCode.REGISTRY_STALE)
        else:
            reasons.append(ExposureReasonCode.OK)
        return EnterpriseExposureState(
            schema_version=SCHEMA_VERSION,
            enterprise_risk_budget=self._budget,
            current_enterprise_exposure=committed,
            reserved_exposure=reserved,
            remaining_enterprise_risk_budget=remaining,
            active_reservation_count=sum(
                1
                for reservation in self._reservations.values()
                if reservation.status is ExposureReservationStatus.RESERVED
                and not self._reservation_expired(reservation, now)
            ),
            reservation_count=len(self._reservations),
            module_attribution=modules,
            stale=stale,
            reason_codes=tuple(reasons),
        )

    def _result(
        self,
        status: ExposureOperationStatus,
        reasons: tuple[ExposureReasonCode, ...],
        reservation: EnterpriseExposureReservation | None,
        now: datetime,
    ) -> ExposureRegistryOperationResult:
        all_reasons = tuple(_dedupe((ExposureReasonCode.ADVISORY_ONLY, *reasons)))
        return ExposureRegistryOperationResult(
            status=status,
            accepted=status in {ExposureOperationStatus.ACCEPTED, ExposureOperationStatus.IDEMPOTENT},
            reason_codes=all_reasons,
            reservation=reservation,
            state=self._state(now),
        )

    @staticmethod
    def _replace(
        reservation: EnterpriseExposureReservation,
        **changes: Any,
    ) -> EnterpriseExposureReservation:
        payload = reservation.as_dict()
        payload.update(changes)
        payload["status"] = changes.get("status", reservation.status)
        payload["amount"] = reservation.amount
        payload["metadata"] = dict(reservation.metadata or {})
        return EnterpriseExposureReservation(**payload)

    @staticmethod
    def _reservation_expired(reservation: EnterpriseExposureReservation, now: datetime) -> bool:
        if not reservation.expires_at:
            return False
        expires_at = _parse_time(reservation.expires_at)
        return expires_at is None or now.astimezone(timezone.utc) >= expires_at


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


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _dedupe(reasons: tuple[ExposureReasonCode, ...] | list[ExposureReasonCode]) -> tuple[ExposureReasonCode, ...]:
    result: list[ExposureReasonCode] = []
    for reason in reasons:
        if reason not in result:
            result.append(reason)
    return tuple(result)


__all__ = [
    "DEFAULT_ALLOWED_MODULES",
    "DEFAULT_OWNER_ID",
    "SCHEMA_VERSION",
    "EnterpriseExposureRegistry",
    "EnterpriseExposureReservation",
    "EnterpriseExposureState",
    "ExposureOperationStatus",
    "ExposureReasonCode",
    "ExposureRegistryOperationResult",
    "ExposureReservationStatus",
]
