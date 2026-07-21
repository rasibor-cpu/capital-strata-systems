"""Fail-closed access policy for enterprise secret metadata and handles."""

from __future__ import annotations

from dataclasses import dataclass

from backend.security.identity.identity_models import EnterpriseIdentity, IdentityStatus, SecretMetadata, SecretStatus


@dataclass(frozen=True)
class SecretAccessRequest:
    identity: EnterpriseIdentity
    purpose: str
    component: str
    duration_seconds: int


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str


class IdentityPolicy:
    allowed_roles = frozenset({"SUPER_USER", "ADMIN"})

    def evaluate_identity_request(self, request: SecretAccessRequest) -> PolicyDecision:
        if request.identity.status is not IdentityStatus.ACTIVE:
            return PolicyDecision(False, "IDENTITY_NOT_ACTIVE")
        if request.identity.role.upper() not in self.allowed_roles:
            return PolicyDecision(False, "ROLE_NOT_AUTHORIZED")
        if not request.purpose.strip() or not request.component.strip():
            return PolicyDecision(False, "ACCESS_JUSTIFICATION_REQUIRED")
        if not 1 <= request.duration_seconds <= 900:
            return PolicyDecision(False, "ACCESS_DURATION_OUT_OF_POLICY")
        return PolicyDecision(True, "POLICY_APPROVED")

    def evaluate(self, request: SecretAccessRequest, metadata: SecretMetadata) -> PolicyDecision:
        identity_decision = self.evaluate_identity_request(request)
        if not identity_decision.allowed:
            return identity_decision
        if metadata.rotation_status in {
            SecretStatus.COMPROMISED,
            SecretStatus.REVOKED,
            SecretStatus.DISABLED,
            SecretStatus.ARCHIVED,
            SecretStatus.EXPIRED,
            SecretStatus.FAILED,
        }:
            return PolicyDecision(False, f"SECRET_{metadata.rotation_status.value}")
        return identity_decision


__all__ = ["IdentityPolicy", "PolicyDecision", "SecretAccessRequest"]
