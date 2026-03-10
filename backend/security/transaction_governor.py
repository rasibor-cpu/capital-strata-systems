from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from backend.security.permissions import PermissionEngine
from backend.security.maker_checker import MakerCheckerEngine


@dataclass
class GovernanceDecision:
    allowed: bool
    requires_approval: bool
    reason: str
    action_id: Optional[str] = None
    routing_head_role: Optional[str] = None
    escalation_role: Optional[str] = None


class TransactionGovernor:
    """
    CSS Institutional Transaction Governance Engine

    Responsibilities:
    - validates role/action permissions
    - determines when maker-checker approval is required
    - routes overrides first to the originating department head
    - supports escalation to other authorised departmental heads
    """

    def __init__(self) -> None:
        self.permissions = PermissionEngine()
        self.maker_checker = MakerCheckerEngine()

        self.department_heads = {
            "TELLER": "HEAD_TELLER",
            "HEAD_TELLER": "HEAD_CASH_AND_TELLERS",
            "CUSTOMER_SERVICE": "HEAD_CUSTOMER_SERVICE",
            "HEAD_CUSTOMER_SERVICE": "HEAD_CASH_AND_TELLERS",
            "HEAD_CASH_AND_TELLERS": "HEAD_CASH_AND_TELLERS",
            "OPERATIONS": "HEAD_OPERATIONS",
            "HEAD_OPERATIONS": "HEAD_OPERATIONS",
            "TREASURY": "HEAD_TREASURY",
            "HEAD_TREASURY": "HEAD_TREASURY",
            "FINCON": "HEAD_FINCON",
            "HEAD_FINCON": "HEAD_FINCON",
            "CREDIT": "HEAD_CREDIT",
            "HEAD_CREDIT": "HEAD_CREDIT",
            "RISK": "HEAD_RISK",
            "HEAD_RISK": "HEAD_RISK",
            "COMPLIANCE": "HEAD_COMPLIANCE",
            "HEAD_COMPLIANCE": "HEAD_COMPLIANCE",
            "AUDIT": "HEAD_AUDIT",
            "HEAD_AUDIT": "HEAD_AUDIT",
            "ADMIN": "HEAD_ADMIN",
            "HEAD_ADMIN": "HEAD_ADMIN",
            "TECH": "HEAD_TECH",
            "HEAD_TECH": "HEAD_TECH",
            "SUPER_USER": "SUPER_USER",
        }

        self.override_actions = {
            "system_override",
            "posting_override",
            "limit_override",
            "value_date_override",
            "back_valuation_override",
            "rate_override",
            "account_override",
        }

        self.csu_actions = {
            "create_customer",
            "update_customer",
            "capture_customer_kyc",
            "upload_customer_documents",
            "initiate_account_opening",
            "initiate_stop_order",
            "initiate_signature_mandate_change",
            "initiate_customer_profile_amendment",
            "authorize_account_opening",
            "authorize_stop_order",
            "authorize_signature_mandate_change",
            "authorize_customer_profile_amendment",
            "approve_customer_record_activation",
        }

        self.high_risk_actions = {
            "create_user",
            "large_transfer",
            "approve_trade",
            "system_override",
            "posting_override",
            "limit_override",
            "value_date_override",
            "back_valuation_override",
            "rate_override",
            "account_override",
            "create_gl_account",
            "close_period",
            "reopen_period",
            "post_high_value_transaction",
            "authorize_account_opening",
            "authorize_stop_order",
            "authorize_signature_mandate_change",
            "authorize_customer_profile_amendment",
            "approve_customer_record_activation",
        }

        self.action_thresholds = {
            "post_transaction": 2_000_000,
            "large_transfer": 2_000_000,
            "post_high_value_transaction": 2_000_000,
        }

    def process(
        self,
        user_id: str,
        role: str,
        action: str,
        payload: Dict[str, Any],
    ) -> GovernanceDecision:
        role_norm = self._normalize(role)
        action_norm = self._normalize(action)

        perm = self.permissions.check(role_norm, action_norm)
        if not perm.allowed:
            return GovernanceDecision(
                allowed=False,
                requires_approval=False,
                reason=perm.reason,
            )

        if action_norm in self.override_actions:
            return self._handle_override(user_id, role_norm, action_norm, payload)

        if self._requires_threshold_approval(action_norm, payload):
            action_id = self.maker_checker.submit_action(
                maker_user=user_id,
                action_type=action_norm,
                payload=payload,
            )
            return GovernanceDecision(
                allowed=True,
                requires_approval=True,
                reason="Transaction exceeds approval threshold and requires checker approval",
                action_id=action_id,
            )

        if action_norm in self.high_risk_actions:
            action_id = self.maker_checker.submit_action(
                maker_user=user_id,
                action_type=action_norm,
                payload=payload,
            )
            return GovernanceDecision(
                allowed=True,
                requires_approval=True,
                reason="Action requires checker approval",
                action_id=action_id,
            )

        return GovernanceDecision(
            allowed=True,
            requires_approval=False,
            reason="Action approved for immediate execution",
        )

    def _handle_override(
        self,
        user_id: str,
        role_norm: str,
        action_norm: str,
        payload: Dict[str, Any],
    ) -> GovernanceDecision:
        originating_head = self.department_heads.get(role_norm)
        escalation_head = self._get_escalation_head(role_norm, originating_head)

        if originating_head is None:
            return GovernanceDecision(
                allowed=False,
                requires_approval=False,
                reason=f"No departmental head configured for role {role_norm}",
            )

        action_payload = {
            **payload,
            "originating_role": role_norm,
            "originating_head_role": originating_head,
            "escalation_head_role": escalation_head,
            "requested_action": action_norm,
        }

        action_id = self.maker_checker.submit_action(
            maker_user=user_id,
            action_type=action_norm,
            payload=action_payload,
        )

        return GovernanceDecision(
            allowed=True,
            requires_approval=True,
            reason=(
                f"Override request routed first to {originating_head}. "
                f"If unavailable or declined, escalate to {escalation_head or 'next authorised head'}."
            ),
            action_id=action_id,
            routing_head_role=originating_head,
            escalation_role=escalation_head,
        )

    def _requires_threshold_approval(
        self,
        action_norm: str,
        payload: Dict[str, Any],
    ) -> bool:
        threshold = self.action_thresholds.get(action_norm)
        if threshold is None:
            return False

        amount = self._extract_amount(payload)
        if amount is None:
            return False

        return amount > threshold

    @staticmethod
    def _extract_amount(payload: Dict[str, Any]) -> Optional[float]:
        raw = payload.get("amount")
        if raw is None:
            return None

        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    def _get_escalation_head(
        self,
        role_norm: str,
        originating_head: Optional[str],
    ) -> Optional[str]:
        special_escalation = {
            "CUSTOMER_SERVICE": "HEAD_CASH_AND_TELLERS",
            "HEAD_CUSTOMER_SERVICE": "HEAD_CASH_AND_TELLERS",
            "TELLER": "HEAD_CASH_AND_TELLERS",
            "HEAD_TELLER": "HEAD_CASH_AND_TELLERS",
        }

        if role_norm in special_escalation:
            return special_escalation[role_norm]

        escalation_order = [
            "HEAD_OPERATIONS",
            "HEAD_TREASURY",
            "HEAD_FINCON",
            "HEAD_RISK",
            "HEAD_COMPLIANCE",
            "HEAD_AUDIT",
            "SUPER_USER",
        ]

        for head_role in escalation_order:
            if head_role != originating_head:
                return head_role

        return "SUPER_USER" if originating_head != "SUPER_USER" else None

    @staticmethod
    def _normalize(value: str) -> str:
        return value.strip().upper().replace(" ", "_").replace("-", "_")