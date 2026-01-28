"""
RBAC v1: Access Levels → Modules → Users
---------------------------------------
This is the authorization backbone.

Model:
- Users have an access level (role)
- Access levels grant modules
- Modules map to screens/actions/resources
- AccessController enforces decisions and audits denials
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Set, Optional

from engine.security.access_control import AccessPolicy


class AccessLevel(str, Enum):
    LEVEL_0_VIEWER = "LEVEL_0_VIEWER"
    LEVEL_1_ANALYST = "LEVEL_1_ANALYST"
    LEVEL_2_TRADER = "LEVEL_2_TRADER"
    LEVEL_3_SUPERVISOR = "LEVEL_3_SUPERVISOR"
    LEVEL_4_ADMIN = "LEVEL_4_ADMIN"


class ModuleID(str, Enum):
    MODULE_AUDIT = "MODULE_AUDIT"
    MODULE_FX = "MODULE_FX"
    MODULE_LEDGER = "MODULE_LEDGER"
    MODULE_EXECUTION = "MODULE_EXECUTION"
    MODULE_ARBITRAGE = "MODULE_ARBITRAGE"
    MODULE_ADMIN = "MODULE_ADMIN"


@dataclass(frozen=True)
class UserProfile:
    user_id: str
    access_level: AccessLevel


# ─────────────────────────────────────────────
# Access Level → Modules
# ─────────────────────────────────────────────
ACCESS_LEVEL_MODULES: Dict[AccessLevel, Set[ModuleID]] = {
    AccessLevel.LEVEL_0_VIEWER: {ModuleID.MODULE_AUDIT},
    AccessLevel.LEVEL_1_ANALYST: {ModuleID.MODULE_AUDIT, ModuleID.MODULE_FX, ModuleID.MODULE_LEDGER},
    AccessLevel.LEVEL_2_TRADER: {
        ModuleID.MODULE_AUDIT, ModuleID.MODULE_FX, ModuleID.MODULE_LEDGER, ModuleID.MODULE_EXECUTION
    },
    AccessLevel.LEVEL_3_SUPERVISOR: {
        ModuleID.MODULE_AUDIT, ModuleID.MODULE_FX, ModuleID.MODULE_LEDGER, ModuleID.MODULE_EXECUTION, ModuleID.MODULE_ARBITRAGE
    },
    AccessLevel.LEVEL_4_ADMIN: {
        ModuleID.MODULE_AUDIT, ModuleID.MODULE_FX, ModuleID.MODULE_LEDGER, ModuleID.MODULE_EXECUTION,
        ModuleID.MODULE_ARBITRAGE, ModuleID.MODULE_ADMIN
    },
}


# ─────────────────────────────────────────────
# Module → Screens/Actions/Resources
# (v1 minimal set; expand per UI)
# ─────────────────────────────────────────────
MODULE_SCREENS: Dict[ModuleID, Set[str]] = {
    ModuleID.MODULE_AUDIT: {"AUDIT_HOME", "AUDIT_EOD_REPORTS", "AUDIT_TICKETS"},
    ModuleID.MODULE_FX: {"FX_HOME", "FX_RATES", "FX_TRANSLATION"},
    ModuleID.MODULE_LEDGER: {"LEDGER_HOME", "LEDGER_POSTINGS", "LEDGER_PNL", "LEDGER_BALANCE_SHEET"},
    ModuleID.MODULE_EXECUTION: {"EXEC_HOME", "EXEC_PAPER", "EXEC_LIVE"},
    ModuleID.MODULE_ARBITRAGE: {"ARB_HOME", "ARB_MONITOR"},
    ModuleID.MODULE_ADMIN: {"ADMIN_HOME", "ADMIN_USERS", "ADMIN_POLICIES"},
}

MODULE_ACTIONS: Dict[ModuleID, Set[str]] = {
    ModuleID.MODULE_AUDIT: {"VIEW", "PRINT", "EXPORT"},
    ModuleID.MODULE_FX: {"VIEW", "CREATE_RATE", "UPDATE_RATE", "TRANSLATE"},
    ModuleID.MODULE_LEDGER: {"VIEW", "POST", "SNAPSHOT", "EXPORT"},
    ModuleID.MODULE_EXECUTION: {"VIEW", "SUBMIT_ORDER", "CANCEL_ORDER", "SWITCH_MODE"},
    ModuleID.MODULE_ARBITRAGE: {"VIEW", "ARM", "DISARM"},
    ModuleID.MODULE_ADMIN: {"VIEW", "CREATE_USER", "UPDATE_USER", "ASSIGN_ROLE", "UPDATE_POLICY"},
}

MODULE_RESOURCES: Dict[ModuleID, Set[str]] = {
    ModuleID.MODULE_AUDIT: {"AUDIT_LOG", "TICKETS", "EOD_PACKS"},
    ModuleID.MODULE_FX: {"FX_RATE", "FX_SOURCE", "FX_PAIR"},
    ModuleID.MODULE_LEDGER: {"LEDGER_ENTRY", "LEDGER_TXN", "PNL_SNAPSHOT", "BALANCE_SHEET"},
    ModuleID.MODULE_EXECUTION: {"ORDER_INTENT", "EXECUTION_REPORT"},
    ModuleID.MODULE_ARBITRAGE: {"ARB_SPREAD", "ARB_LEG"},
    ModuleID.MODULE_ADMIN: {"USER_PROFILE", "ACCESS_POLICY"},
}


def build_policy_for_access_level(level: AccessLevel) -> AccessPolicy:
    """
    Builds an AccessPolicy by aggregating all allowed module permissions.
    """
    allowed_modules = ACCESS_LEVEL_MODULES.get(level, set())

    screens: Set[str] = set()
    actions: Set[str] = set()
    resources: Set[str] = set()

    for m in allowed_modules:
        screens |= MODULE_SCREENS.get(m, set())
        actions |= MODULE_ACTIONS.get(m, set())
        resources |= MODULE_RESOURCES.get(m, set())

    return AccessPolicy(
        allowed_screens=screens,
        allowed_actions=actions,
        allowed_resources=resources,
    )


def build_policies_by_role() -> Dict[str, AccessPolicy]:
    """
    Returns dict[str role] -> AccessPolicy for AccessController.
    """
    return {lvl.value: build_policy_for_access_level(lvl) for lvl in AccessLevel}