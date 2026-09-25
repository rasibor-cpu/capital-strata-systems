from __future__ import annotations

import getpass
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.auth.css_sign_on import (
    MIN_PASSWORD_LENGTH,
    RECOVERY_QUESTIONS,
    PasswordValidationError,
    change_password,
    enroll_all_password_recovery,
    load_users,
    normalize_user_id,
    record_auth_audit_event,
    save_users,
)


def main() -> int:
    print("Capital Strata Systems — Local Account Recovery Enrollment")
    print("This local maintenance tool resets a user's password and recovery challenge.")
    print("No password or recovery answer is displayed or stored in plaintext.")

    user_id = normalize_user_id(input("User ID [00000]: ").strip() or "00000")
    if not user_id:
        print("Invalid CSS user ID.")
        return 2

    users = load_users()
    record = users.get(user_id)
    if not isinstance(record, dict):
        print("User ID not found.")
        return 2

    confirmation = input(f'Type RESET {user_id} to continue: ').strip()
    if confirmation != f"RESET {user_id}":
        print("Recovery enrollment cancelled.")
        return 1

    new_password = getpass.getpass(f"New password (minimum {MIN_PASSWORD_LENGTH} characters): ")
    confirm_password = getpass.getpass("Confirm new password: ")

    print("\nAll five recovery questions must be answered.")
    answers: dict[str, str] = {}
    for index, question in enumerate(RECOVERY_QUESTIONS, start=1):
        print(f"\n{index}. {question}")
        answer = getpass.getpass("Recovery answer: ")
        confirm_answer = getpass.getpass("Confirm recovery answer: ")
        if answer != confirm_answer:
            print("Recovery answers do not match.")
            return 2
        answers[question] = answer

    try:
        change_password(users, user_id, new_password, confirm_password)
        enroll_all_password_recovery(users, user_id, answers)
    except PasswordValidationError as exc:
        print(f"Password / recovery reset failed: {exc}")
        return 2

    save_users(users)

    record_auth_audit_event(
        "local_password_and_recovery_reset",
        user_id,
        "SUCCESS",
        auth_source="local_maintenance",
        details={"recovery_question_count": len(RECOVERY_QUESTIONS)},
    )
    print("\nPassword and all five recovery questions were reset successfully.")
    print("Failed sign-on lockout state has also been cleared.")
    print("You can now use the new password or the Forgot password flow.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
