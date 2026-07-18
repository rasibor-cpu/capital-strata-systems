"""Executive Brief recipient resolution — ADMIN/SUPER_USER only (Phase 175 correction).

Recipients must resolve to active CSS users with role ADMIN or SUPER_USER.
Arbitrary external addresses are rejected. Fail-closed.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any

EMAIL_ELIGIBLE_ROLES = frozenset({"ADMIN", "SUPER_USER", "SUPERUSER"})
RECIPIENT_ROLE_NOT_AUTHORIZED = "RECIPIENT_ROLE_NOT_AUTHORIZED"
_EMAIL_LIKE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_role(role: Any) -> str:
    return str(role or "").strip().upper().replace(" ", "_").replace("-", "_")


def is_email_eligible_role(role: Any) -> bool:
    r = normalize_role(role)
    if r == "SUPERUSER":
        r = "SUPER_USER"
    return r in {"ADMIN", "SUPER_USER"}


def is_user_active(record: Mapping[str, Any] | None) -> bool:
    if not isinstance(record, Mapping):
        return False
    if record.get("active") is False:
        return False
    if record.get("disabled") is True:
        return False
    status = str(record.get("status") or "").strip().upper()
    if status in {"INACTIVE", "DISABLED", "LOCKED", "SUSPENDED", "DELETED"}:
        return False
    return True


def default_load_user_directory() -> dict[str, dict[str, Any]]:
    """Load canonical CSS users from user_registry when available."""
    try:
        from backend.app.security.user_registry import load_users

        raw = load_users() or {}
        out: dict[str, dict[str, Any]] = {}
        if isinstance(raw, Mapping):
            for key, value in raw.items():
                if isinstance(value, Mapping):
                    out[str(key)] = dict(value)
                    # also index by display_name when unique-ish (optional lookup)
                    display = str(value.get("display_name") or "").strip()
                    if display and display not in out:
                        out[display] = dict(value)
        return out
    except Exception:
        return {}


class RecipientDirectory:
    """Resolves recipient identifiers to CSS user records."""

    def __init__(self, loader: Callable[[], dict[str, dict[str, Any]]] | None = None) -> None:
        self._loader = loader or default_load_user_directory

    def resolve(self, recipient_id: str) -> dict[str, Any]:
        rid = str(recipient_id or "").strip()
        if not rid:
            return {
                "eligible": False,
                "reason": RECIPIENT_ROLE_NOT_AUTHORIZED,
                "detail": "empty_recipient",
                "user_id": None,
                "role": None,
            }

        # Reject raw external email addresses — must be CSS user identifiers
        if _EMAIL_LIKE.match(rid):
            return {
                "eligible": False,
                "reason": RECIPIENT_ROLE_NOT_AUTHORIZED,
                "detail": "external_address_not_allowed",
                "user_id": None,
                "role": None,
            }

        try:
            directory = self._loader() or {}
        except Exception:
            return {
                "eligible": False,
                "reason": RECIPIENT_ROLE_NOT_AUTHORIZED,
                "detail": "role_evidence_unavailable",
                "user_id": None,
                "role": None,
            }

        if not isinstance(directory, Mapping) or not directory:
            return {
                "eligible": False,
                "reason": RECIPIENT_ROLE_NOT_AUTHORIZED,
                "detail": "role_evidence_unavailable",
                "user_id": None,
                "role": None,
            }

        record = directory.get(rid)
        if record is None:
            # try numeric normalization
            record = directory.get(str(rid).lstrip("0") if rid.isdigit() else rid)
        if not isinstance(record, Mapping):
            return {
                "eligible": False,
                "reason": RECIPIENT_ROLE_NOT_AUTHORIZED,
                "detail": "user_unresolved",
                "user_id": rid,
                "role": None,
            }

        if not is_user_active(record):
            return {
                "eligible": False,
                "reason": RECIPIENT_ROLE_NOT_AUTHORIZED,
                "detail": "user_inactive",
                "user_id": str(record.get("user_id") or rid),
                "role": normalize_role(record.get("role")),
            }

        role = normalize_role(record.get("role"))
        if role == "SUPERUSER":
            role = "SUPER_USER"
        if not is_email_eligible_role(role):
            return {
                "eligible": False,
                "reason": RECIPIENT_ROLE_NOT_AUTHORIZED,
                "detail": "role_not_admin_or_super_user",
                "user_id": str(record.get("user_id") or rid),
                "role": role,
            }

        return {
            "eligible": True,
            "reason": "OK",
            "detail": "eligible_admin_or_super_user",
            "user_id": str(record.get("user_id") or rid),
            "role": role,
        }

    def validate_recipients(self, recipient_ids: list[str]) -> dict[str, Any]:
        eligible: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        for rid in recipient_ids:
            result = self.resolve(str(rid))
            entry = {
                "recipient_ref": str(rid),
                "user_id": result.get("user_id"),
                "role": result.get("role"),
                "detail": result.get("detail"),
            }
            # privacy: never include email-like addresses in audit payloads beyond opaque ref hash-ish
            if result.get("eligible"):
                eligible.append(entry)
            else:
                rejected.append({**entry, "reason": result.get("reason")})

        ok = bool(eligible) and not rejected
        return {
            "ok": ok,
            "eligible_count": len(eligible),
            "rejected_count": len(rejected),
            "eligible": eligible,
            "rejected": rejected,
            "reason": "OK" if ok else RECIPIENT_ROLE_NOT_AUTHORIZED,
            # delivery uses opaque CSS user ids only
            "delivery_recipient_ids": [e["user_id"] for e in eligible if e.get("user_id")],
        }
