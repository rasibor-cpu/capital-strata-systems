from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

ALLOWED_APPROVER_ROLES = {"ADMIN", "SUPER_USER"}


def _require_utc(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None or value.utcoffset().total_seconds() != 0:
        raise ValueError("timestamp must be timezone-aware UTC")


@dataclass(frozen=True)
class OperatorApproval:
    approval_id: str
    approver_id: str
    approver_role: str
    approved_at_utc: datetime
    expires_at_utc: datetime
    scope: str
    approved: bool = True

    def __post_init__(self) -> None:
        if not self.approval_id.strip() or not self.approver_id.strip() or not self.scope.strip():
            raise ValueError("approval id, approver id, and scope are required")
        _require_utc(self.approved_at_utc)
        _require_utc(self.expires_at_utc)
        if self.expires_at_utc <= self.approved_at_utc:
            raise ValueError("approval expiry must be after approval time")

    def as_audit_dict(self) -> dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "approver_id": self.approver_id,
            "approver_role": self.approver_role.upper(),
            "approved_at_utc": self.approved_at_utc.isoformat(),
            "expires_at_utc": self.expires_at_utc.isoformat(),
            "scope": self.scope,
            "approved": self.approved,
        }


def validate_operator_approval(
    approval: OperatorApproval | None,
    *,
    required_scope: str,
    now_utc: datetime,
) -> tuple[bool, str]:
    _require_utc(now_utc)
    if approval is None:
        return False, "OPERATOR_APPROVAL_MISSING"
    if not approval.approved:
        return False, "OPERATOR_APPROVAL_DENIED"
    if approval.approver_role.upper() not in ALLOWED_APPROVER_ROLES:
        return False, "OPERATOR_ROLE_NOT_AUTHORIZED"
    if approval.scope != required_scope:
        return False, "OPERATOR_APPROVAL_SCOPE_MISMATCH"
    if now_utc >= approval.expires_at_utc:
        return False, "OPERATOR_APPROVAL_EXPIRED"
    return True, "OPERATOR_APPROVAL_VALID"
