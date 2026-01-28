"""
Security Context (v1)
--------------------
Unified entry point for:
- session validation
- RBAC authorization
- transaction authorization

Every protected operation MUST pass through this context.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from engine.security.session_manager import SessionManager
from engine.security.user_directory import UserDirectory
from engine.security.access_control import AccessController


@dataclass
class SecurityContext:
    session_manager: SessionManager
    user_directory: UserDirectory
    access_controller: AccessController

    def require_access(
        self,
        *,
        session_id: str,
        screen: str,
        action: str,
        resource: str,
        amount: Optional[Decimal] = None,
    ) -> None:
        """
        Enforces:
        1) active session
        2) RBAC access
        3) transaction limits (if amount provided)
        """

        # 1) Validate session
        session = self.session_manager.require_active(session_id)

        # 2) RBAC authorization
        ent = self.user_directory.require(session.user_id)
        self.access_controller.check(
            user_id=ent.user_id,
            role=ent.access_level.value,
            session_id=session_id,
            screen=screen,
            action=action,
            resource=resource,
        )

        # 3) Transaction authorization (optional)
        if amount is not None:
            txn_profile = self.user_directory.txn_profile(ent.user_id)
            self.user_directory.authorizer.assert_can_transact(
                user=txn_profile,
                amount=amount,
                session_id=session_id,
                screen=screen,
                action=action,
                resource=resource,
            )