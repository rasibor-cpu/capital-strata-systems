"""Phase 187A / 187A-R1 — deterministic OANDA read-only certification state machine."""

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

# Forward progression path for initial certification.
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

# Revalidation path — never jumps directly to READ_ONLY_CERTIFIED from invalidation.
_REVALIDATION_PATH: Mapping[str, tuple[str, str]] = {
    # state -> (required_evidence_key, next_state)
    "REVALIDATION_PENDING": ("revalidation_start", "REVALIDATION_RUNNING"),
    "REVALIDATION_RUNNING": ("revalidation_complete", "REVALIDATED"),
}


@dataclass(frozen=True)
class TransitionResult:
    from_state: str
    to_state: str
    success: bool
    failure_reason: str = ""


class OandaReadOnlyStateMachine:
    """Offline-only deterministic state machine. Never performs network I/O."""

    def __init__(self, initial_state: str = "NOT_STARTED") -> None:
        if initial_state not in CERTIFICATION_STATES:
            raise ValueError(f"unknown state: {initial_state}")
        self._state = initial_state

    @property
    def state(self) -> str:
        return self._state

    def force_state(self, state: str, *, reason: str = "") -> TransitionResult:
        """Controlled transition used for invalidation / lineage ops only."""
        if state not in CERTIFICATION_STATES:
            raise ValueError(f"unknown state: {state}")
        current = self._state
        self._state = state
        return TransitionResult(current, state, True, reason)

    def invalidate_to_revalidation_pending(self, reason: str) -> TransitionResult:
        """Invalidation may only land on REVALIDATION_PENDING (never CERTIFIED)."""
        current = self._state
        if current not in {
            "READ_ONLY_CERTIFIED",
            "REVALIDATED",
            "REVALIDATION_PENDING",
            "REVALIDATION_RUNNING",
            "MARKETDATA_OK",
            "ACCOUNT_SCOPE_OK",
            "ACCOUNT_OK",
            "AUTH_OK",
            "TLS_OK",
            "DNS_OK",
            "CONFIG_VALIDATED",
            "CONFIG_PRESENT",
        }:
            # Still force pending — never certified.
            pass
        self._state = "REVALIDATION_PENDING"
        return TransitionResult(current, "REVALIDATION_PENDING", False, reason)

    def evaluate(
        self,
        evidence: Mapping[str, bool],
        *,
        blocked: bool = False,
        failed: bool = False,
        failure_reason: str = "",
    ) -> TransitionResult:
        """Advance at most one step based on explicit boolean evidence flags."""
        current = self._state
        if blocked:
            self._state = "BLOCKED"
            return TransitionResult(current, "BLOCKED", False, failure_reason or "blocked")
        if failed:
            self._state = "FAILED"
            return TransitionResult(current, "FAILED", False, failure_reason or "failed")
        if current in {"FAILED", "BLOCKED"}:
            return TransitionResult(current, current, False, "")

        # Revalidation branch — never silent reuse of older certified state.
        if current in _REVALIDATION_PATH:
            required, nxt = _REVALIDATION_PATH[current]
            if not bool(evidence.get(required, False)):
                return TransitionResult(current, current, False, f"missing_evidence:{required}")
            self._state = nxt
            return TransitionResult(current, nxt, True, "")

        if current == "REVALIDATED":
            # Controlled settle to certified only with explicit evidence flag.
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
            return TransitionResult(
                current,
                current,
                False,
                f"missing_evidence:{required}",
            )

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
        terminal = {"FAILED", "BLOCKED", "READ_ONLY_CERTIFIED", "REVALIDATED"}
        for _ in range(max_steps):
            result = self.evaluate(
                evidence,
                blocked=blocked,
                failed=failed,
                failure_reason=failure_reason,
            )
            history.append(result)
            if result.to_state in terminal and not (
                result.to_state == "REVALIDATED"
                and bool(evidence.get("read_only_certified", False))
                and result.from_state == "REVALIDATED"
            ):
                # Allow one settle step from REVALIDATED → READ_ONLY_CERTIFIED.
                if result.to_state == "REVALIDATED" and bool(evidence.get("read_only_certified", False)):
                    continue
                if result.to_state in {"FAILED", "BLOCKED", "READ_ONLY_CERTIFIED"}:
                    break
                if result.to_state == "REVALIDATED":
                    break
            if result.from_state == result.to_state:
                break
        return self._state, tuple(history)
