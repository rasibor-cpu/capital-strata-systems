"""Provision DEVELOPMENT/UAT operator identities in the css_sign_on user store.

Creates FINCON, HEAD_FINCON, AUDIT and HEAD_COMPLIANCE operator accounts with
freshly generated random passwords, each flagged to require a password change
on first sign-in. Intended for local development and UAT environments only --
never point this at a production user store.

Generated passwords are written once to a local, gitignored file
(artifacts/dev_uat_operator_credentials.json) and are never printed or
committed. Re-running this script skips any account that already exists.

Usage:
    python scripts/provision_dev_uat_operators.py
"""
from __future__ import annotations

import json
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboard.auth.css_sign_on import (  # noqa: E402
    ARTIFACTS_DIR,
    PasswordValidationError,
    create_user,
    load_users,
    save_users,
)

SUPER_USER_CTX = {"user_id": "00000", "role": "SUPER_USER"}

# (user_id, display_name, role)
OPERATORS = (
    ("10001", "Dev FinCon Operator", "FINCON"),
    ("10002", "Dev Head FinCon Operator", "HEAD_FINCON"),
    ("10003", "Dev Audit Operator", "AUDIT"),
    ("10004", "Dev Head Compliance Operator", "HEAD_COMPLIANCE"),
)

CREDENTIALS_FILE = ARTIFACTS_DIR / "dev_uat_operator_credentials.json"


def _generate_password() -> str:
    return secrets.token_urlsafe(18)


def main() -> int:
    users = load_users()
    created: dict[str, dict[str, str]] = {}

    for user_id, display_name, role in OPERATORS:
        if user_id in users:
            print(f"[skip] {user_id} ({role}) already exists")
            continue

        password = _generate_password()
        try:
            create_user(
                users,
                SUPER_USER_CTX,
                user_id,
                display_name,
                role,
                password,
                unit_code="COMMERCIAL",
                home_branch="HQ",
                must_change_password=True,
            )
        except PasswordValidationError as exc:
            print(f"[error] could not create {user_id} ({role}): {exc}")
            continue

        created[user_id] = {"display_name": display_name, "role": role, "password": password}
        print(f"[created] {user_id} ({role}) - {display_name}")

    if not created:
        print("No new operator accounts were created.")
        return 0

    save_users(users)
    CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    CREDENTIALS_FILE.write_text(json.dumps(created, indent=2), encoding="utf-8")
    print(f"\nDEV/UAT credentials written to {CREDENTIALS_FILE} (gitignored; local only).")
    print("Each account requires a password change on first sign-in.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
