from __future__ import annotations

import tempfile
from pathlib import Path

from dashboard.auth.css_sign_on import (
    AuthFailure,
    INITIAL_ADMIN_ID,
    INITIAL_ADMIN_PASSWORD,
    PasswordChangeRequired,
    PasswordValidationError,
    authenticate_credentials,
    change_password,
    load_users,
    save_users,
)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        users_file = Path(tmp) / "users.json"
        users = load_users(users_file)

        try:
            authenticate_credentials(users, INITIAL_ADMIN_ID, INITIAL_ADMIN_PASSWORD)
        except PasswordChangeRequired:
            pass
        else:
            raise AssertionError("Default password must force password change")

        try:
            change_password(users, INITIAL_ADMIN_ID, INITIAL_ADMIN_PASSWORD, INITIAL_ADMIN_PASSWORD)
        except PasswordValidationError:
            pass
        else:
            raise AssertionError("Default password must not be accepted as the new password")

        user_ctx = change_password(users, INITIAL_ADMIN_ID, "cssgood1", "cssgood1")
        assert user_ctx["user_id"] == INITIAL_ADMIN_ID
        save_users(users, users_file)

        user_ctx = authenticate_credentials(users, INITIAL_ADMIN_ID, "cssgood1")
        assert user_ctx["role"] == "SUPER_USER"

        try:
            change_password(users, INITIAL_ADMIN_ID, "cssgood1", "cssgood1")
        except PasswordValidationError:
            pass
        else:
            raise AssertionError("Current password must be blocked by history policy")

        for _attempt in range(2):
            try:
                authenticate_credentials(users, INITIAL_ADMIN_ID, "wrong-password")
            except AuthFailure as exc:
                assert exc.code == "AUTH_FAILED"
            else:
                raise AssertionError("Wrong password should fail")

        try:
            authenticate_credentials(users, INITIAL_ADMIN_ID, "wrong-password")
        except AuthFailure as exc:
            assert exc.code == "ACCOUNT_LOCKED"
        else:
            raise AssertionError("Third bad password should lock the account")

    print("CSS sign-on smoke test PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
