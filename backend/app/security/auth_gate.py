"""
Authoritative authentication gate for REA Capital Trading Engine.

Rules:
- Authentication returns BOOLEAN ONLY
- Password length = exactly 6
- Initial password allowed = '123456'
"""

from getpass import getpass
from backend.app.security.user_registry import get_user, verify_password

MAX_PASSWORD_LENGTH = 6
INITIAL_PASSWORD = "123456"


def authenticate_user(user_id: int) -> bool:
    """
    Authenticate a user by numeric user_id.
    Returns:
        True  -> authentication successful
        False -> authentication failed
    """

    user = get_user(user_id)
    if not user:
        return False

    pw = getpass("REA LOGIN | password: ").strip()

    # Enforce exact length
    if len(pw) != MAX_PASSWORD_LENGTH:
        return False

    # Allow known initial password
    if pw == INITIAL_PASSWORD:
        return True

    # Normal verification path
    verified = verify_password(user, pw)

    if verified is True:
        return True

    return False


def await_login_ready_state() -> dict:
    """
    Blocking login gate. Returns user context on success.
    """

    print("REA LOGIN | user_id (numeric): ", end="")
    try:
        user_id = int(input().strip())
    except Exception:
        raise RuntimeError("INVALID_USER_ID")

    allowed = authenticate_user(user_id)

    if allowed is not True:
        raise RuntimeError("AUTH_FAILED")

    user = get_user(user_id)

    return {
        "user_id": user["user_id"],
        "display_name": user["display_name"],
        "role": user["role"],
        "unit_code": user["unit_code"],
        "home_branch": user["home_branch"],
    }
