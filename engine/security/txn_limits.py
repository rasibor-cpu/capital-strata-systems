"""
Transaction Authorization Limits (v1)
-------------------------------------
Hard transaction amount limits enforced per user.

Key principles:
- No one-up approvals
- Users can only initiate/complete transactions within assigned bands
- Audit/Review users cannot transact
- Super Admin can modify others' limits but NEVER their own
- Every violation is audited and supervisor-flagged
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional

from engine.security.audit_log import AuditLogger, AuditEventType
from engine.security.supervisor_alerts import SupervisorAlert, SupervisorAlertService


# ─────────────────────────────────────────────
# Transaction Amount Bands
# ─────────────────────────────────────────────
class TxnBand(str, Enum):
    BAND_1 = "0-1_000_000"
    BAND_2 = "1_000_001-5_000_000"
    BAND_3 = "5_000_001-25_000_000"
    BAND_4 = "25_000_001-100_000_000"
    BAND_5 = "100_000_001+"


BAND_LIMITS = {
    TxnBand.BAND_1: Decimal("1000000"),
    TxnBand.BAND_2: Decimal("5000000"),
    TxnBand.BAND_3: Decimal("25000000"),
    TxnBand.BAND_4: Decimal("100000000"),
    TxnBand.BAND_5: Decimal("999999999999"),  # practical infinity
}


# ─────────────────────────────────────────────
# User Transaction Entitlement
# ─────────────────────────────────────────────
@dataclass(frozen=True)
class UserTxnProfile:
    user_id: str
    role: str
    txn_band: Optional[TxnBand]  # None means NO transaction rights
    is_audit_only: bool = False
    is_super_admin: bool = False


# ─────────────────────────────────────────────
# Authorization Engine
# ─────────────────────────────────────────────
class TransactionAuthorizer:
    def __init__(self, audit: AuditLogger, supervisor: SupervisorAlertService):
        self.audit = audit
        self.supervisor = supervisor

    def assert_can_transact(
        self,
        *,
        user: UserTxnProfile,
        amount: Decimal,
        session_id: Optional[str],
        screen: str,
        action: str,
        resource: str,
    ) -> None:
        """
        Enforces transaction limits.
        Raises PermissionError on violation.
        """

        # 1) Audit-only users are fully blocked
        if user.is_audit_only or user.txn_band is None:
            self._deny(
                user,
                session_id,
                screen,
                action,
                resource,
                "Audit/Review users cannot initiate or conclude transactions",
            )

        # 2) Check band limit
        limit = BAND_LIMITS[user.txn_band]
        if amount > limit:
            self._deny(
                user,
                session_id,
                screen,
                action,
                resource,
                f"Transaction amount {amount} exceeds authorized limit {limit}",
            )

        # 3) Success audit
        self.audit.log(
            event_type=AuditEventType.ACTION,
            user_id=user.user_id,
            role=user.role,
            session_id=session_id,
            screen=screen,
            action=action,
            resource=resource,
            success=True,
            meta={
                "amount": str(amount),
                "txn_band": user.txn_band.value,
            },
        )

    def assert_can_modify_limits(
        self,
        *,
        acting_user: UserTxnProfile,
        target_user_id: str,
    ) -> None:
        """
        Enforces that super admin cannot modify their own limits.
        """

        if not acting_user.is_super_admin:
            raise PermissionError("Only super admin can modify transaction limits")

        if acting_user.user_id == target_user_id:
            self._deny(
                acting_user,
                None,
                "ADMIN_USERS",
                "UPDATE_TXN_LIMIT",
                target_user_id,
                "Super admin cannot modify own transaction limits",
            )

    # ─────────────────────────────
    # Internal helpers
    # ─────────────────────────────
    def _deny(
        self,
        user: UserTxnProfile,
        session_id: Optional[str],
        screen: str,
        action: str,
        resource: str,
        reason: str,
    ) -> None:
        # Audit
        self.audit.log(
            event_type=AuditEventType.SECURITY,
            user_id=user.user_id,
            role=user.role,
            session_id=session_id,
            screen=screen,
            action=action,
            resource=resource,
            success=False,
            reason=reason,
        )

        # Supervisor alert
        self.supervisor.notify(
            SupervisorAlert(
                alert_type="UNAUTHORIZED_TRANSACTION",
                user_id=user.user_id,
                role=user.role,
                session_id=session_id,
                screen=screen,
                action=action,
                resource=resource,
                reason=reason,
                meta={"amount_violation": True},
            )
        )

        raise PermissionError(reason)