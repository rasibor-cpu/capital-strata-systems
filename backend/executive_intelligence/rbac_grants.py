"""Executive Brief RBAC grants — print designation only; email is role-gated.

Email send/receive: SUPER_USER and ADMIN only (non-delegable).
Print: SUPER_USER/ADMIN, or staff with executive_brief_print grant.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from backend.executive_intelligence.recipients import is_email_eligible_role, normalize_role
from backend.executive_intelligence.utils import utc_now_iso
from backend.security.permissions import PermissionEngine

ACTION_PRINT = "executive_brief_print"
ACTION_EMAIL = "executive_brief_email"
ACTION_MANAGE_GRANTS = "manage_executive_brief_grants"

DEFAULT_GRANT_RELATIVE = Path("artifacts/runtime_reports/executive_intelligence_archive/rbac/staff_grants.json")


class ExecutiveBriefAccessControl:
    def __init__(self, grant_path: Path | str | None = None, *, engine: PermissionEngine | None = None) -> None:
        self.grant_path = Path(grant_path) if grant_path else Path.cwd() / DEFAULT_GRANT_RELATIVE
        self.engine = engine or PermissionEngine()
        self._ensure_actions_registered()

    def _ensure_actions_registered(self) -> None:
        perms = self.engine.permissions
        admin_actions = {ACTION_PRINT, ACTION_EMAIL, ACTION_MANAGE_GRANTS, "view_reports"}
        for role in ("ADMIN", "SUPER_USER"):
            if role in perms:
                perms[role] = set(perms[role]) | admin_actions

    def _load_grants(self) -> dict[str, Any]:
        if not self.grant_path.is_file():
            return {"schema_version": "css.executive_brief_grants.v1", "grants": {}, "audit": []}
        try:
            data = json.loads(self.grant_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("grants", {})
                data.setdefault("audit", [])
                return data
        except Exception:
            pass
        return {"schema_version": "css.executive_brief_grants.v1", "grants": {}, "audit": []}

    def _save_grants(self, payload: Mapping[str, Any]) -> None:
        self.grant_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix="grants.", suffix=".tmp", dir=str(self.grant_path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(dict(payload), handle, indent=2, sort_keys=True)
                handle.write("\n")
            os.replace(tmp, str(self.grant_path))
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass

    def authorize(self, *, role: str, user_id: str, action: str) -> dict[str, Any]:
        role_u = normalize_role(role)
        if role_u == "SUPERUSER":
            role_u = "SUPER_USER"
        user = str(user_id or "").strip()
        action_n = self.engine.normalize(action)

        # Email is intrinsically role-gated — never delegable via staff grants
        if action_n == ACTION_EMAIL:
            if is_email_eligible_role(role_u):
                return {
                    "allowed": True,
                    "role": role_u,
                    "user_id": user,
                    "action": action_n,
                    "permission_used": f"role:{role_u}:{action_n}",
                    "reason": "Email authorized for ADMIN/SUPER_USER only.",
                }
            return {
                "allowed": False,
                "role": role_u,
                "user_id": user,
                "action": action_n,
                "permission_used": None,
                "reason": "EMAIL_SENDER_ROLE_NOT_AUTHORIZED",
            }

        # ADMIN / SUPER_USER via PermissionEngine for print / grant management
        result = self.engine.check(role_u, action_n)
        if result.allowed:
            return {
                "allowed": True,
                "role": role_u,
                "user_id": user,
                "action": action_n,
                "permission_used": f"role:{role_u}:{action_n}",
                "reason": result.reason,
            }

        # Staff designation grants — PRINT only
        if action_n == ACTION_PRINT:
            grants = self._load_grants().get("grants") or {}
            user_grants = grants.get(user) if isinstance(grants, dict) else None
            if isinstance(user_grants, Mapping):
                actions = {self.engine.normalize(a) for a in (user_grants.get("actions") or [])}
                # Ignore any legacy executive_brief_email entries in grant files
                if ACTION_PRINT in actions and user_grants.get("revoked") is not True:
                    return {
                        "allowed": True,
                        "role": role_u,
                        "user_id": user,
                        "action": action_n,
                        "permission_used": f"grant:{user}:{ACTION_PRINT}",
                        "reason": "Staff print designation grant active.",
                    }

        return {
            "allowed": False,
            "role": role_u,
            "user_id": user,
            "action": action_n,
            "permission_used": None,
            "reason": result.reason if not result.allowed else "Grant not found",
        }

    def designate_staff(
        self,
        *,
        admin_role: str,
        admin_user_id: str,
        staff_user_id: str,
        actions: list[str],
    ) -> dict[str, Any]:
        auth = self.authorize(role=admin_role, user_id=admin_user_id, action=ACTION_MANAGE_GRANTS)
        if not auth["allowed"]:
            return {"status": "DENIED", "reason": auth["reason"], **auth}
        staff = str(staff_user_id).strip()
        if not staff:
            return {"status": "DENIED", "reason": "staff_user_id_required"}

        requested = [self.engine.normalize(a) for a in actions]
        if ACTION_EMAIL in requested:
            return {
                "status": "DENIED",
                "reason": "EMAIL_GRANT_NOT_DELEGABLE",
                "detail": "executive_brief_email cannot be granted to STAFF",
            }

        normalized = sorted({a for a in requested if a == ACTION_PRINT})
        if not normalized:
            return {"status": "DENIED", "reason": "no_valid_print_actions"}

        data = self._load_grants()
        grants = dict(data.get("grants") or {})
        # Strip any legacy email actions if present when re-designating
        grants[staff] = {
            "actions": normalized,
            "designated_by": admin_user_id,
            "designated_at_utc": utc_now_iso(),
            "revoked": False,
        }
        data["grants"] = grants
        audit = list(data.get("audit") or [])
        audit.append(
            {
                "event": "DESIGNATE_PRINT",
                "admin_user_id": admin_user_id,
                "admin_role": normalize_role(admin_role),
                "staff_user_id": staff,
                "actions": normalized,
                "at_utc": utc_now_iso(),
            }
        )
        data["audit"] = audit[-500:]
        self._save_grants(data)
        return {"status": "OK", "staff_user_id": staff, "actions": normalized}

    def revoke_staff(
        self,
        *,
        admin_role: str,
        admin_user_id: str,
        staff_user_id: str,
    ) -> dict[str, Any]:
        auth = self.authorize(role=admin_role, user_id=admin_user_id, action=ACTION_MANAGE_GRANTS)
        if not auth["allowed"]:
            return {"status": "DENIED", "reason": auth["reason"], **auth}
        staff = str(staff_user_id).strip()
        data = self._load_grants()
        grants = dict(data.get("grants") or {})
        if staff not in grants:
            return {"status": "NOT_FOUND", "staff_user_id": staff}
        grants[staff] = {
            **dict(grants[staff]),
            "revoked": True,
            "revoked_by": admin_user_id,
            "revoked_at_utc": utc_now_iso(),
            "actions": [],
        }
        data["grants"] = grants
        audit = list(data.get("audit") or [])
        audit.append(
            {
                "event": "REVOKE_PRINT",
                "admin_user_id": admin_user_id,
                "admin_role": normalize_role(admin_role),
                "staff_user_id": staff,
                "at_utc": utc_now_iso(),
            }
        )
        data["audit"] = audit[-500:]
        self._save_grants(data)
        return {"status": "OK", "staff_user_id": staff, "revoked": True}
