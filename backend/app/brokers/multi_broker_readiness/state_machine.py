"""Phase 189 — broker-agnostic certification state machine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

CERTIFICATION_STATES: tuple[str, ...] = (
    "NOT_STARTED",
    "CONFIG_PRESENT",
    "CONFIG_VALIDATED",
    "DNS_OK",
    "TLS_OK",
    "AUTH_PENDING",
    "AUTH_OK",
    "ACCOUNT_OK",
    "ACCOUNT_SCOPE_OK",
    "MARKETDATA_OK",
    "READ_ONLY_CERTIFIED",
    "REVALIDATION_PENDING",
    "REVALIDATION_RUNNING",
    "REVALIDATED",
    "FAILED",
    "BLOCKED",
)

_FORWARD_PATH: tuple[str, ...] = (
    "NOT_STARTED",
    "CONFIG_PRESENT",
    "CONFIG_VALIDATED",
    "DNS_OK",
    "TLS_OK",
    "AUTH_PENDING",
    "AUTH_OK",
    "ACCOUNT_OK",
    "ACCOUNT_SCOPE_OK",
    "MARKETDATA_OK",
    "READ_ONLY_CERTIFIED",
)

_ADVANCE_REQUIREMENTS: Mapping[str, str] = {
    "NOT_STARTED": "config_present",
    "CONFIG_PRESENT": "config_validated",
    "CONFIG_VALIDATED": "dns_ok",
    "DNS_OK": "tls_ok",
    "TLS_OK": "auth_pending",
    "AUTH_PENDING": "auth_ok",
    "AUTH_OK": "account_ok",
    "ACCOUNT_OK": "account_scope_ok",
    "ACCOUNT_SCOPE_OK": "marketdata_ok",
    "MARKETDATA_OK": "read_only_certified",
}

_REVALIDATION_PATH: Mapping[str, tuple[str, str]] = {
    "REVALIDATION_PENDING": ("revalidation_start", "REVALIDATION_RUNNING"),
    "REVALIDATION_RUNNING": ("revalidation_complete", "REVALIDATED"),
}


@dataclass(frozen=True)
class TransitionResult:
    from_state: str
    to_state: str
    success: bool
    failure_reason: str = ""


class BrokerCertificationStateMachine:
    """Deterministic broker-agnostic state machine. Offline evaluation only."""

    def __init__(self, initial_state: str = "NOT_STARTED") -> None:
        if initial_state not in CERTIFICATION_STATES:
            raise ValueError(f"unknown state: {initial_state}")
        self._state = initial_state

    @property
    def state(self) -> str:
        return self._state

    def force_blocked(self, reason: str) -> TransitionResult:
        current = self._state
        self._state = "BLOCKED"
        return TransitionResult(current, "BLOCKED", False, reason)

    def force_failed(self, reason: str) -> TransitionResult:
        current = self._state
        self._state = "FAILED"
        return TransitionResult(current, "FAILED", False, reason)

    def evaluate(
        self,
        evidence: Mapping[str, bool],
        *,
        blocked: bool = False,
        failed: bool = False,
        failure_reason: str = "",
    ) -> TransitionResult:
        current = self._state
        if blocked:
            self._state = "BLOCKED"
            return TransitionResult(current, "BLOCKED", False, failure_reason or "blocked")
        if failed:
            self._state = "FAILED"
            return TransitionResult(current, "FAILED", False, failure_reason or "failed")
        if current in {"FAILED", "BLOCKED"}:
            return TransitionResult(current, current, False, "")

        if current in _REVALIDATION_PATH:
            required, nxt = _REVALIDATION_PATH[current]
            if not bool(evidence.get(required, False)):
                return TransitionResult(current, current, False, f"missing_evidence:{required}")
            self._state = nxt
            return TransitionResult(current, nxt, True, "")

        if current == "REVALIDATED":
            if bool(evidence.get("read_only_certified", False)):
                self._state = "READ_ONLY_CERTIFIED"
                return TransitionResult(current, "READ_ONLY_CERTIFIED", True, "")
            return TransitionResult(current, current, True, "")

        if current == "READ_ONLY_CERTIFIED":
            return TransitionResult(current, current, True, "")

        required = _ADVANCE_REQUIREMENTS.get(current)
        if required is None:
            return TransitionResult(current, current, False, "no_forward_transition")
        if not bool(evidence.get(required, False)):
            return TransitionResult(current, current, False, f"missing_evidence:{required}")

        idx = _FORWARD_PATH.index(current)
        nxt = _FORWARD_PATH[idx + 1]
        self._state = nxt
        return TransitionResult(current, nxt, True, "")

    def run_to_completion(
        self,
        evidence: Mapping[str, bool],
        *,
        blocked: bool = False,
        failed: bool = False,
        failure_reason: str = "",
        max_steps: int = 32,
    ) -> tuple[str, tuple[TransitionResult, ...]]:
        history: list[TransitionResult] = []
        for _ in range(max_steps):
            result = self.evaluate(
                evidence,
                blocked=blocked,
                failed=failed,
                failure_reason=failure_reason,
            )
            history.append(result)
            if result.to_state in {"FAILED", "BLOCKED", "READ_ONLY_CERTIFIED"}:
                break
            if result.to_state == "REVALIDATED" and not bool(
                evidence.get("read_only_certified", False)
            ):
                break
            if result.from_state == result.to_state:
                break
        return self._state, tuple(history)
