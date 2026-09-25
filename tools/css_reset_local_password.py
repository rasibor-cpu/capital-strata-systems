from __future__ import annotations

import getpass
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dashboard.auth import css_sign_on as auth


def reset_local_password(user_id: str, temporary_password: str) -> None:
    normalized = auth.normalize_user_id(user_id)
    if not normalized:
        raise SystemExit("Invalid user ID.")

    users = auth.load_users()
    record = users.get(normalized)
    if not isinstance(record, dict):
        raise SystemExit(f"User {normalized} not found.")

    auth.validate_initial_password(temporary_password)

    current_hash = str(record.get("password_hash", "") or "").strip()
    history = record.get("password_history")
    if not isinstance(history, list):
        history = []
    if current_hash:
        history.append(current_hash)

    record["password_history"] = history[-auth.PASSWORD_HISTORY_LIMIT :]
    record["password_hash"] = auth.hash_password(temporary_password)
    record["must_change_password"] = True
    record["last_password_change"] = None
    auth.clear_lockout_state(record, preserve_failed_attempts=False)

    # Deliberately preserve recovery_answers, recovery_required,
    # broker/application preferences, role, and profile metadata.
    auth.save_users(users)

    session_file = Path(auth.SESSION_AUTH_FILE)
    try:
        if session_file.exists():
            session_file.unlink()
    except OSError as exc:
        raise SystemExit(f"Password reset completed, but session invalidation failed: {exc}")

    print(
        f"CSS temporary password reset completed for {normalized}. "
        "The next successful sign-in must change the password."
    )


def main() -> int:
    user_id = input("CSS user ID [00000]: ").strip() or "00000"
    first = getpass.getpass("Temporary password: ")
    second = getpass.getpass("Confirm temporary password: ")
    if first != second:
        raise SystemExit("Temporary passwords do not match.")
    reset_local_password(user_id, first)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
