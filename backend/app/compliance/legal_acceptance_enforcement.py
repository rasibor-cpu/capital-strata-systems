"""Acceptance enforcement helper for trading-enabled session readiness.

This module is the safest Phase 1B integration point for session/runtime startup:
call ``enforce_trading_session_acceptance`` after authenticated user identity is
known and before marking a trading-enabled session ready.

The helper is fail-safe and additive. It does not import or modify broker
adapters, execution adapters, dashboard code, analytics code, reporting code, or
PnL code. Dashboard/reporting/analytics override claims are intentionally ignored
because legal/trading-risk acceptance remains the sole authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from backend.app.compliance.legal_acceptance import AcceptanceValidationResult
from backend.app.compliance.legal_acceptance_service import (
    LegalAcceptanceService,
    RequiredAcceptanceValidation,
)

TRADING_ENABLED_MODES = frozenset({"PAPER", "PRACTICE", "LIVE"})
NON_TRADING_MODES = frozenset({"SIMULATION", "DEMO", "ANALYTICS", "REPORTING"})
NON_AUTHORITY_SOURCES = frozenset({"dashboard", "reporting", "analytics"})


class AcceptanceEnforcementStatus(str, Enum):
    """Canonical enforcement status for session/runtime readiness."""

    ALLOW = "ALLOW"
    BLOCK = "BLOCK"


@dataclass(frozen=True)
class TradingSessionReadinessRequest:
    """Request context for acceptance readiness enforcement.

    ``override_claims`` is retained only for audit/debug visibility. The
    enforcement helper never trusts it as authority.
    """

    user_id: str
    mode: str
    source: str = "runtime_startup"
    trading_enabled: bool | None = None
    override_claims: dict[str, Any] = field(default_factory=dict)

    def normalized_mode(self) -> str:
        """Return the uppercase execution/session mode."""

        return self.mode.strip().upper()

    def requires_acceptance(self) -> bool:
        """Return True when session readiness is trading-enabled."""

        if self.trading_enabled is not None:
            return self.trading_enabled

        return self.normalized_mode() in TRADING_ENABLED_MODES


@dataclass(frozen=True)
class AcceptanceEnforcementDecision:
    """Final readiness decision after legal acceptance enforcement."""

    status: AcceptanceEnforcementStatus
    user_id: str
    mode: str
    trading_enabled: bool
    source: str
    validation: RequiredAcceptanceValidation | None
    message: str
    ignored_override_claims: dict[str, Any] = field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        """Return True when the session/runtime readiness may proceed."""

        return self.status == AcceptanceEnforcementStatus.ALLOW

    @property
    def blocked(self) -> bool:
        """Return True when the session/runtime readiness must fail closed."""

        return self.status == AcceptanceEnforcementStatus.BLOCK

    @property
    def blocking_results(self) -> tuple[AcceptanceValidationResult, ...]:
        """Return blocking acceptance validation results, if any."""

        if self.validation is None:
            return ()

        return self.validation.blocking_results

    def as_readiness_payload(self) -> dict[str, Any]:
        """Return a JSON-serializable readiness payload for callers/loggers."""

        return {
            "status": self.status.value,
            "allowed": self.allowed,
            "blocked": self.blocked,
            "user_id": self.user_id,
            "mode": self.mode,
            "trading_enabled": self.trading_enabled,
            "source": self.source,
            "message": self.message,
            "ignored_override_claims": dict(self.ignored_override_claims),
            "blocking_acceptance_types": [
                result.acceptance_type for result in self.blocking_results
            ],
            "blocking_reasons": [
                result.block_reason.value
                for result in self.blocking_results
                if result.block_reason is not None
            ],
        }


def enforce_trading_session_acceptance(
    *,
    request: TradingSessionReadinessRequest,
    acceptance_service: LegalAcceptanceService,
) -> AcceptanceEnforcementDecision:
    """Enforce Phase 1 legal acceptance before trading-enabled readiness.

    Fail-safe behavior:
    - Trading-enabled readiness validates all required acceptances.
    - Missing, invalid, or outdated acceptance blocks readiness.
    - Current legal terms plus current trading-risk disclosure allows readiness.
    - Dashboard/reporting/analytics override claims are ignored.
    - Non-trading modes are allowed without changing broker/live/dashboard state.
    """

    mode = request.normalized_mode()
    trading_enabled = request.requires_acceptance()
    ignored_override_claims = dict(request.override_claims)

    if not request.user_id or not request.user_id.strip():
        return AcceptanceEnforcementDecision(
            status=AcceptanceEnforcementStatus.BLOCK,
            user_id=request.user_id,
            mode=mode,
            trading_enabled=trading_enabled,
            source=request.source,
            validation=None,
            message="Missing user identity for acceptance enforcement",
            ignored_override_claims=ignored_override_claims,
        )

    if not trading_enabled:
        return AcceptanceEnforcementDecision(
            status=AcceptanceEnforcementStatus.ALLOW,
            user_id=request.user_id,
            mode=mode,
            trading_enabled=False,
            source=request.source,
            validation=None,
            message="Non-trading session readiness does not require Phase 1 acceptance",
            ignored_override_claims=ignored_override_claims,
        )

    validation = acceptance_service.validate_required_acceptances(
        user_id=request.user_id,
    )

    if validation.blocked:
        return AcceptanceEnforcementDecision(
            status=AcceptanceEnforcementStatus.BLOCK,
            user_id=request.user_id,
            mode=mode,
            trading_enabled=True,
            source=request.source,
            validation=validation,
            message="Trading-enabled session readiness blocked by Phase 1 acceptance",
            ignored_override_claims=ignored_override_claims,
        )

    return AcceptanceEnforcementDecision(
        status=AcceptanceEnforcementStatus.ALLOW,
        user_id=request.user_id,
        mode=mode,
        trading_enabled=True,
        source=request.source,
        validation=validation,
        message="Trading-enabled session readiness allowed by current acceptances",
        ignored_override_claims=ignored_override_claims,
    )