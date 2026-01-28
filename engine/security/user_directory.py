"""
User Directory (v1)
-------------------
Central registry mapping user_id -> entitlements.

Entitlements include:
- RBAC access level (modules/screens/actions/resources)
- transaction authorization band
- audit-only restriction
- super-admin restriction rules

Design notes:
- v1 is in-memory (dict). Swap to DB later without changing callers.
- user_id is immutable and is the primary key for audit trail queries.
"""

from dataclasses import dataclass
from typing import Dict, Optional

from engine.security.rbac import AccessLevel
from engine.security.txn_limits import TxnBand, UserTxnProfile, TransactionAuthorizer
from engine.security.audit_log import AuditLogger, AuditEventType
from engine.security.supervisor_alerts import SupervisorAlertService


@dataclass
class UserEntitlements:
    user_id: str
    access_level: AccessLevel

    # Transaction processing
    txn_band: Optional[TxnBand] = None
    audit_only: bool = False
    super_admin: bool = False


class UserDirectory:
    """
    In-memory user directory (v1).
    """

    def __init__(self, audit: AuditLogger, supervisor: SupervisorAlertService):
        self.audit = audit
        self.supervisor = supervisor
        self.authorizer = TransactionAuthorizer(audit, supervisor)
        self._users: Dict[str, UserEntitlements] = {}

    # ─────────────────────────────
    # User lifecycle
    # ─────────────────────────────
    def add_user(self, ent: UserEntitlements) -> None:
        self._users[ent.user_id] = ent
        self.audit.log(
            event_type=AuditEventType.ACTION,
            user_id=ent.user_id,
            role=ent.access_level.value,
            session_id=None,
            screen="ADMIN_USERS",
            action="CREATE_USER",
            resource=ent.user_id,
            success=True,
            meta={
                "txn_band": ent.txn_band.value if ent.txn_band else None,
                "audit_only": ent.audit_only,
                "super_admin": ent.super_admin,
            },
        )

    def get(self, user_id: str) -> Optional[UserEntitlements]:
        return self._users.get(user_id)

    def require(self, user_id: str) -> UserEntitlements:
        ent = self.get(user_id)
        if not ent:
            raise ValueError(f"Unknown user_id: {user_id}")
        return ent

    # ─────────────────────────────
    # Derived profiles
    # ─────────────────────────────
    def txn_profile(self, user_id: str) -> UserTxnProfile:
        ent = self.require(user_id)
        return UserTxnProfile(
            user_id=ent.user_id,
            role=ent.access_level.value,
            txn_band=ent.txn_band,
            is_audit_only=ent.audit_only,
            is_super_admin=ent.super_admin,
        )

    # ─────────────────────────────
    # Admin: modify transaction limits (no self-change)
    # ─────────────────────────────
    def set_user_txn_band(
        self,
        *,
        acting_user_id: str,
        target_user_id: str,
        new_band: Optional[TxnBand],
        session_id: Optional[str] = None,
    ) -> None:
        acting = self.txn_profile(acting_user_id)

        # Enforce: super admin only + cannot modify own limits
        self.authorizer.assert_can_modify_limits(
            acting_user=acting,
            target_user_id=target_user_id,
        )

        target = self.require(target_user_id)

        old = target.txn_band.value if target.txn_band else None
        target.txn_band = new_band

        self.audit.log(
            event_type=AuditEventType.ACTION,
            user_id=acting_user_id,
            role=acting.role,
            session_id=session_id,
            screen="ADMIN_USERS",
            action="UPDATE_TXN_LIMIT",
            resource=target_user_id,
            success=True,
            meta={
                "old_band": old,
                "new_band": new_band.value if new_band else None,
            },
        )

    def set_user_access_level(
        self,
        *,
        acting_user_id: str,
        target_user_id: str,
        new_level: AccessLevel,
        session_id: Optional[str] = None,
    ) -> None:
        acting = self.require(acting_user_id)
        if not acting.super_admin:
            raise PermissionError("Only super admin can modify access levels")

        if acting_user_id == target_user_id:
            raise PermissionError("Super admin cannot modify own access level")

        target = self.require(target_user_id)
        old = target.access_level.value
        target.access_level = new_level

        self.audit.log(
            event_type=AuditEventType.ACTION,
            user_id=acting_user_id,
            role=acting.access_level.value,
            session_id=session_id,
            screen="ADMIN_USERS",
            action="ASSIGN_ROLE",
            resource=target_user_id,
            success=True,
            meta={"old_level": old, "new_level": new_level.value},
        )