from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PermissionResult:
    allowed: bool
    role: str
    action: str
    reason: str


class PermissionEngine:
    def __init__(self) -> None:
        self.permissions = {
            # =========================
            # SYSTEM / GOVERNANCE ROLES
            # =========================
            "ADMIN": {
                "create_user",
                "unlock_user",
                "list_users",
                "view_users",
                "reset_user_password",
                "change_own_password",
                "access_admin_console",
                "view_reports",
                "view_audit_logs",
            },
            "SUPER_USER": {
                "manage_system",
                "system_override",
                "posting_override",
                "limit_override",
                "value_date_override",
                "back_valuation_override",
                "rate_override",
                "account_override",
                "approve_transaction",
                "approve_postings",
                "approve_trade",
                "create_gl_account",
                "close_period",
                "reopen_period",
                "view_reports",
                "view_audit_logs",
                "view_positions",
                "view_market_scanner",
            },
            "AUDIT": {
                "view_audit_logs",
                "list_users",
                "view_users",
                "view_reports",
            },
            "HEAD_AUDIT": {
                "view_audit_logs",
                "list_users",
                "view_users",
                "view_reports",
                "approve_transaction",
                "approve_postings",
            },
            "TECH": {
                "system_maintenance",
                "view_system_logs",
                "support_access",
            },
            "HEAD_TECH": {
                "system_maintenance",
                "view_system_logs",
                "support_access",
                "system_override",
                "view_reports",
            },
            "COMPLIANCE": {
                "view_compliance_records",
                "view_reports",
            },
            "HEAD_COMPLIANCE": {
                "view_compliance_records",
                "view_reports",
                "approve_transaction",
                "approve_postings",
                "posting_override",
                "limit_override",
            },
            "RISK": {
                "view_risk_records",
                "view_reports",
            },
            "HEAD_RISK": {
                "view_risk_records",
                "view_reports",
                "approve_transaction",
                "approve_postings",
                "limit_override",
            },

            # =========================
            # CASH / TELLERS / CUSTOMER SERVICE
            # =========================
            "TELLER": {
                "post_transaction",
                "cash_deposit",
                "cash_withdrawal",
                "transfer_between_accounts",
                "change_own_password",
                "view_customer_profile",
            },
            "HEAD_TELLER": {
                "post_transaction",
                "cash_deposit",
                "cash_withdrawal",
                "transfer_between_accounts",
                "approve_transaction",
                "approve_postings",
                "posting_override",
                "value_date_override",
                "back_valuation_override",
                "view_reports",
            },
            "CUSTOMER_SERVICE": {
                "view_customer_profile",
                "create_customer",
                "update_customer",
                "capture_customer_kyc",
                "upload_customer_documents",
                "initiate_account_opening",
                "initiate_stop_order",
                "initiate_signature_mandate_change",
                "initiate_customer_profile_amendment",
            },
            "HEAD_CUSTOMER_SERVICE": {
                "view_customer_profile",
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
                "approve_transaction",
                "approve_postings",
                "posting_override",
                "account_override",
                "view_reports",
            },
            "HEAD_CASH_AND_TELLERS": {
                "post_transaction",
                "cash_deposit",
                "cash_withdrawal",
                "transfer_between_accounts",
                "view_customer_profile",
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
                "approve_transaction",
                "approve_postings",
                "posting_override",
                "value_date_override",
                "back_valuation_override",
                "account_override",
                "view_reports",
            },

            # =========================
            # OPERATIONS
            # =========================
            "OPERATIONS": {
                "post_transaction",
                "process_transfer",
                "settle_trade",
                "reverse_transaction_request",
                "view_reports",
            },
            "HEAD_OPERATIONS": {
                "post_transaction",
                "process_transfer",
                "settle_trade",
                "reverse_transaction_request",
                "approve_transaction",
                "approve_postings",
                "approve_operations",
                "posting_override",
                "value_date_override",
                "back_valuation_override",
                "account_override",
                "view_reports",
            },

            # =========================
            # FINANCIAL CONTROL
            # =========================
            "FINCON": {
                "view_financial_reports",
                "approve_postings",
                "view_reports",
                "post_transaction",
                "create_gl_entry",
            },
            "HEAD_FINCON": {
                "view_financial_reports",
                "approve_postings",
                "approve_transaction",
                "view_reports",
                "post_transaction",
                "create_gl_entry",
                "create_gl_account",
                "close_period",
                "reopen_period",
                "posting_override",
                "value_date_override",
                "back_valuation_override",
                "account_override",
            },

            # =========================
            # TREASURY
            # =========================
            "TREASURY": {
                "post_transaction",
                "manage_liquidity",
                "view_positions",
                "settle_trade",
                "place_trade",
                "submit_trade",
                "view_market_scanner",
            },
            "HEAD_TREASURY": {
                "post_transaction",
                "manage_liquidity",
                "view_positions",
                "settle_trade",
                "place_trade",
                "submit_trade",
                "approve_trade",
                "approve_transaction",
                "approve_postings",
                "override_limits",
                "limit_override",
                "rate_override",
                "view_reports",
                "view_market_scanner",
            },

            # =========================
            # LEGACY / SPECIALIST ROLES
            # =========================
            "TRADER": {
                "place_trade",
                "submit_trade",
                "view_positions",
                "view_market_scanner",
            },
            "TREASURY_OPERATIONS": {
                "settle_trade",
                "manage_liquidity",
                "view_positions",
            },
            "TREASURY_MANAGER": {
                "approve_trade",
                "override_limits",
                "view_positions",
                "view_reports",
                "view_market_scanner",
            },
            "TRADE_OFFICER": {
                "process_trade_docs",
            },
            "TRADE_OPERATIONS": {
                "process_trade_docs",
                "settle_trade",
            },
            "TRADE_MANAGER": {
                "process_trade_docs",
                "settle_trade",
                "approve_trade_operations",
                "view_reports",
            },
            "FUNDS_TRANSFER_OFFICER": {
                "process_transfer",
            },
            "SETTLEMENT_OFFICER": {
                "process_transfer",
                "settle_trade",
            },
            "OPERATIONS_SUPERVISOR": {
                "process_transfer",
                "approve_operations",
                "view_reports",
            },
            "RETAIL_OFFICER": {
                "view_customer_profile",
                "service_retail_customer",
            },
            "RETAIL_MANAGER": {
                "view_customer_profile",
                "service_retail_customer",
                "approve_retail_actions",
                "view_reports",
            },
            "COMMERCIAL_OFFICER": {
                "view_commercial_clients",
                "service_commercial_customer",
            },
            "COMMERCIAL_MANAGER": {
                "view_commercial_clients",
                "service_commercial_customer",
                "approve_commercial_actions",
                "view_reports",
            },
            "CORPORATE_OFFICER": {
                "view_corporate_clients",
                "service_corporate_customer",
            },
            "INSTITUTIONAL_BANKING_OFFICER": {
                "view_corporate_clients",
                "service_corporate_customer",
            },
            "CORPORATE_MANAGER": {
                "view_corporate_clients",
                "service_corporate_customer",
                "approve_corporate_actions",
                "view_reports",
            },
            "LEGAL_OFFICER": {
                "view_legal_records",
            },
            "CORPORATE_SERVICES_OFFICER": {
                "view_corporate_records",
            },
            "COMPLIANCE_OFFICER": {
                "view_compliance_records",
                "view_reports",
            },
            "CREDIT_ADMIN_OFFICER": {
                "view_credit_files",
                "update_credit_control",
            },
            "CREDIT_CONTROL": {
                "view_credit_files",
                "update_credit_control",
            },
            "CREDIT_MANAGER": {
                "view_credit_files",
                "update_credit_control",
                "approve_credit_actions",
                "view_reports",
            },
            "VIEWER": {
                "view_reports",
            },
        }

    def normalize(self, text: str) -> str:
        text = str(text).strip().lower()
        return text.replace(" ", "_").replace("-", "_")

    def check(self, role: str, action: str) -> PermissionResult:
        role = str(role).strip().upper().replace(" ", "_").replace("-", "_")
        action_normalized = self.normalize(action)

        if role not in self.permissions:
            return PermissionResult(
                allowed=False,
                role=role,
                action=action_normalized,
                reason=f"Role {role} not recognised",
            )

        if action_normalized in self.permissions[role]:
            return PermissionResult(
                allowed=True,
                role=role,
                action=action_normalized,
                reason="Permission granted.",
            )

        return PermissionResult(
            allowed=False,
            role=role,
            action=action_normalized,
            reason=f"Role {role} is not permitted to perform action: {action_normalized}",
        )