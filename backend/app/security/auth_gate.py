# backend/app/security/auth_gate.py

from backend.app.security.user_registry import authenticate, change_password
from backend.app.observability.audit_context import set_audit_user


def await_login_ready_state() -> dict:
    print("REA LOGIN | user_id (numeric): ", end="")
    user_id = int(input().strip())

    print("REA LOGIN | password: ", end="")
    password = input().strip()

    user = authenticate(user_id, password)

    if user.must_change_password:
        print("FIRST_LOGIN_PASSWORD_CHANGE_REQUIRED")
        print("NEW PASSWORD (min 6 chars): ", end="")
        new_pw = input().strip()
        print("CONFIRM NEW PASSWORD: ", end="")
        confirm_pw = input().strip()

        if new_pw != confirm_pw:
            raise RuntimeError("PASSWORD_MISMATCH")

        change_password(user_id, new_pw)
        print("PASSWORD_CHANGED_SUCCESSFULLY")

        user = authenticate(user_id, new_pw)

    set_audit_user(
        user_id=user.user_id,
        display_name=user.display_name,
        role=user.role,
        unit_code=user.unit_code,
    )

    return {
        "user_id": user.user_id,
        "role": user.role,
        "unit_code": user.unit_code,
    }
