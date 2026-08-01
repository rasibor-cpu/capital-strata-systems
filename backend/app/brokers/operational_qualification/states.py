"""Phase 193 — qualification state machine (offline, no execution)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

QUALIFICATION_STATES: tuple[str, ...] = (
    "NOT_STARTED",
    "PRECHECK_READY",
    "CONFIG_READY",
    "AUTH_READY",
    "READ_ONLY_READY",
    "QUALIFIED",
    "BLOCKED",
)

# Forward path only — AUTH_READY means declared auth *config* present, not authenticated.
_FORWARD_PATH: tuple[str, ...] = (
    "NOT_STARTED",
    "PRECHECK_READY",
    "CONFIG_READY",
    "AUTH_READY",
    "READ_ONLY_READY",
    "QUALIFIED",
)

_ADVANCE_REQUIREMENTS: Mapping[str, str] = {
    "NOT_STARTED": "precheck_ready",
    "PRECHECK_READY": "config_ready",
    "CONFIG_READY": "auth_config_ready",
    "AUTH_READY": "read_only_framework_ready",
    "READ_ONLY_READY": "qualification_complete",
}

# Score / label keys are ignored — scores alone cannot advance state.
_IGNORED_EVIDENCE_KEYS: frozenset[str] = frozenset(
    {
        "readiness_score",
        "implementation_maturity_score",
        "operational_readiness_score",
        "aggregate_qualification_score",
        "readiness_label",
        "score",
        "aggregate",
    }
)


@dataclass(frozen=True)
class TransitionResult:
    from_state: str
    to_state: str
    success: bool
    failure_reason: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "from_state": self.from_state,
            "to_state": self.to_state,
            "success": self.success,
            "failure_reason": self.failure_reason,
        }


class QualificationStateMachine:
    """Deterministic qualification transitions. Never grants execution."""

    def __init__(self, initial_state: str = "NOT_STARTED") -> None:
        if initial_state not in QUALIFICATION_STATES:
            raise ValueError(f"unknown_state:{initial_state}")
        self._state = initial_state

    @property
    def state(self) -> str:
        return self._state

    def force_blocked(self, reason: str) -> TransitionResult:
        current = self._state
        self._state = "BLOCKED"
        return TransitionResult(current, "BLOCKED", False, reason or "blocked")

    def evaluate(self, evidence: Mapping[str, bool], *, blocked: bool = False, reason: str = "") -> TransitionResult:
        current = self._state
        # Scores/labels never participate in transitions.
        gated = {
            str(k): bool(v)
            for k, v in dict(evidence or {}).items()
            if str(k) not in _IGNORED_EVIDENCE_KEYS
        }
        if blocked:
            self._state = "BLOCKED"
            return TransitionResult(current, "BLOCKED", False, reason or "blocked")
        if current == "BLOCKED":
            return TransitionResult(current, current, False, "terminal_blocked")
        if current == "QUALIFIED":
            return TransitionResult(current, current, True, "")

        required = _ADVANCE_REQUIREMENTS.get(current)
        if required is None:
            return TransitionResult(current, current, False, "no_forward_transition")
        if not bool(gated.get(required, False)):
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
        reason: str = "",
        max_steps: int = 16,
    ) -> tuple[str, tuple[TransitionResult, ...]]:
        history: list[TransitionResult] = []
        for _ in range(max_steps):
            result = self.evaluate(evidence, blocked=blocked, reason=reason)
            history.append(result)
            if result.to_state in {"BLOCKED", "QUALIFIED"}:
                break
            if result.from_state == result.to_state:
                break
            # Only allow a single blocked injection on first step.
            blocked = False
        return self._state, tuple(history)

    def assert_transition_allowed(self, to_state: str) -> bool:
        """Reject non-adjacent / invalid transitions without mutating state."""
        if to_state not in QUALIFICATION_STATES:
            return False
        if to_state == "BLOCKED":
            return True
        if self._state == "BLOCKED":
            return False
        if self._state == "QUALIFIED":
            return to_state == "QUALIFIED"
        try:
            cur_i = _FORWARD_PATH.index(self._state)
            nxt_i = _FORWARD_PATH.index(to_state)
        except ValueError:
            return False
        return nxt_i == cur_i + 1
