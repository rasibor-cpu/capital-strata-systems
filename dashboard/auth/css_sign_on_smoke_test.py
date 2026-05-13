from __future__ import annotations

import tempfile
import os
from datetime import datetime, timedelta
from pathlib import Path

import dashboard.auth.css_sign_on as css_auth
from dashboard.auth.css_sign_on import (
    AuthFailure,
    INITIAL_ADMIN_ID,
    INITIAL_ADMIN_PASSWORD,
    PasswordChangeRequired,
    PasswordValidationError,
    authenticate_credentials,
    change_password,
    create_user,
    load_users,
    lockout_seconds_for_attempt,
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

        created = create_user(
            users,
            user_ctx,
            user_id="17",
            display_name="CSS Test Trader",
            role="TRADER",
            initial_password="trader1",
            unit_code="TRD",
            home_branch="HQ",
        )
        assert created["user_id"] == "00017"
        assert created["role"] == "TRADER"

        try:
            authenticate_credentials(users, "00017", "trader1")
        except PasswordChangeRequired:
            pass
        else:
            raise AssertionError("Created users must change initial passwords")

        trader_ctx = change_password(users, "00017", "trader2", "trader2")
        assert trader_ctx["role"] == "TRADER"

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
            assert exc.code == "AUTH_LOCKOUT"
            assert users[INITIAL_ADMIN_ID]["failed_attempts"] == 3
            assert users[INITIAL_ADMIN_ID]["locked"] is True
            assert users[INITIAL_ADMIN_ID]["lockout_seconds"] == lockout_seconds_for_attempt(3)
        else:
            raise AssertionError("Third bad password should start timed lockout")

        try:
            authenticate_credentials(users, INITIAL_ADMIN_ID, "cssgood1")
        except AuthFailure as exc:
            assert exc.code == "AUTH_LOCKOUT"
        else:
            raise AssertionError("Correct password should be blocked during timed lockout")

        users[INITIAL_ADMIN_ID]["lockout_until"] = (
            datetime.now() - timedelta(seconds=1)
        ).isoformat(timespec="seconds")

        try:
            authenticate_credentials(users, INITIAL_ADMIN_ID, "wrong-password")
        except AuthFailure as exc:
            assert exc.code == "AUTH_LOCKOUT"
            assert users[INITIAL_ADMIN_ID]["failed_attempts"] == 4
            assert users[INITIAL_ADMIN_ID]["lockout_seconds"] == lockout_seconds_for_attempt(4)
        else:
            raise AssertionError("Fourth sequential bad password should increase timed lockout")

        users[INITIAL_ADMIN_ID]["lockout_until"] = (
            datetime.now() - timedelta(seconds=1)
        ).isoformat(timespec="seconds")
        user_ctx = authenticate_credentials(users, INITIAL_ADMIN_ID, "cssgood1")
        assert user_ctx["role"] == "SUPER_USER"
        assert users[INITIAL_ADMIN_ID]["failed_attempts"] == 0
        assert users[INITIAL_ADMIN_ID]["locked"] is False

        previous_store = os.environ.get("CSS_AUTH_STORE")
        previous_db = css_auth.USER_DB_FILE
        try:
            os.environ["CSS_AUTH_STORE"] = "db"
            css_auth.USER_DB_FILE = Path(tmp) / "css_users.sqlite3"
            db_users = css_auth.load_users()
            db_ctx = css_auth.change_password(db_users, INITIAL_ADMIN_ID, "dbgood1", "dbgood1")
            css_auth.save_users(db_users)
            reloaded = css_auth.load_users()
            assert css_auth.authenticate_credentials(reloaded, INITIAL_ADMIN_ID, "dbgood1")["role"] == db_ctx["role"]
        finally:
            css_auth.USER_DB_FILE = previous_db
            if previous_store is None:
                os.environ.pop("CSS_AUTH_STORE", None)
            else:
                os.environ["CSS_AUTH_STORE"] = previous_store

    print("CSS sign-on smoke test PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
