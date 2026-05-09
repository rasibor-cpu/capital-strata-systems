from __future__ import annotations

import dashboard.mobile.mobile_app as mobile_app
from backend.security.permissions import PermissionEngine
from dashboard.auth.css_sign_on import available_roles, can_manage_users


def _ctx(role: str) -> dict[str, str]:
    return {
        "user_id": "00017",
        "display_name": f"CSS {role}",
        "role": role,
    }


def test_permission_engine_core_trading_matrix() -> None:
    engine = PermissionEngine()

    assert engine.check("TRADER", "submit_trade").allowed is True
    assert engine.check("TREASURY", "place_trade").allowed is True
    assert engine.check("HEAD_TREASURY", "approve_trade").allowed is True
    assert engine.check("VIEWER", "submit_trade").allowed is False
    assert engine.check("AUDIT", "submit_trade").allowed is False


def test_mobile_trade_authority_matrix() -> None:
    allowed_roles = {"SUPER_USER", "TRADER", "TREASURY", "HEAD_TREASURY"}
    blocked_roles = {"VIEWER", "AUDIT", "RISK", "TECH", "COMPLIANCE"}

    for role in allowed_roles:
        assert mobile_app._can_submit_trade(_ctx(role)) is True

    for role in blocked_roles:
        assert mobile_app._can_submit_trade(_ctx(role)) is False


def test_mobile_control_and_user_admin_authority_matrix() -> None:
    assert mobile_app._can_manage_mobile_controls(_ctx("SUPER_USER")) is True
    assert can_manage_users(_ctx("SUPER_USER")) is True

    for role in ("ADMIN", "TRADER", "TREASURY", "HEAD_TREASURY", "VIEWER"):
        assert mobile_app._can_manage_mobile_controls(_ctx(role)) is False
        assert can_manage_users(_ctx(role)) is False


def test_available_roles_are_backed_by_permission_engine() -> None:
    engine_roles = set(PermissionEngine().permissions)
    auth_roles = set(available_roles())

    assert engine_roles <= auth_roles
    assert {"SUPER_USER", "TRADER", "TREASURY", "VIEWER"} <= auth_roles
