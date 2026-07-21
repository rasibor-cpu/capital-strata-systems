"""Broker-independent onboarding state machine with execution blocked."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from enum import Enum


class OnboardingState(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    METADATA_REGISTERED = "METADATA_REGISTERED"
    AUTHORIZATION_REQUIRED = "AUTHORIZATION_REQUIRED"
    CALLBACK_PENDING = "CALLBACK_PENDING"
    CREDENTIAL_VALIDATION_REQUIRED = "CREDENTIAL_VALIDATION_REQUIRED"
    READ_ONLY_CERTIFICATION_REQUIRED = "READ_ONLY_CERTIFICATION_REQUIRED"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


_TRANSITIONS = {
    OnboardingState.NOT_STARTED: {OnboardingState.METADATA_REGISTERED},
    OnboardingState.METADATA_REGISTERED: {OnboardingState.AUTHORIZATION_REQUIRED},
    OnboardingState.AUTHORIZATION_REQUIRED: {OnboardingState.CALLBACK_PENDING},
    OnboardingState.CALLBACK_PENDING: {OnboardingState.CREDENTIAL_VALIDATION_REQUIRED},
    OnboardingState.CREDENTIAL_VALIDATION_REQUIRED: {OnboardingState.READ_ONLY_CERTIFICATION_REQUIRED},
    OnboardingState.READ_ONLY_CERTIFICATION_REQUIRED: {OnboardingState.COMPLETE},
}


@dataclass(frozen=True)
class BrokerOnboarding:
    broker: str
    state: OnboardingState = OnboardingState.NOT_STARTED
    vcid: str | None = None
    failure_code: str | None = None
    oauth_performed: bool = False
    execution_allowed: bool = False

    def transition(self, target: OnboardingState) -> "BrokerOnboarding":
        if target is OnboardingState.FAILED:
            return replace(self, state=target)
        if target not in _TRANSITIONS.get(self.state, set()):
            raise ValueError(f"ONBOARDING_TRANSITION_BLOCKED:{self.state.value}->{target.value}")
        return replace(self, state=target)

    def as_dict(self) -> dict:
        payload = asdict(self)
        payload["state"] = self.state.value
        return payload


__all__ = ["BrokerOnboarding", "OnboardingState"]
