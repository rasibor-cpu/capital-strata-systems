from __future__ import annotations

import getpass
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from backend.security.session_manager import SessionManager
from backend.security.user_auth import UserAuth


def reset_password_flow(auth: UserAuth) -> None:
    print()
    print("PASSWORD RESET")
    print("----------------")

    user_id = input("User ID (5 digits): ").strip()

    ok, question_or_message = auth.get_recovery_question(user_id)
    if not ok:
        print(question_or_message)
        return

    print()
    print("Security Question:")
    print(question_or_message)

    answer = input("Answer: ").strip()
    print("New Password: ********")
    new_password = getpass.getpass("New Password: ")

    ok, message = auth.reset_password(user_id, answer, new_password)
    print()
    print(message)


def change_password_anytime_flow(auth: UserAuth) -> None:
    print()
    print("CHANGE PASSWORD")
    print("----------------")

    user_id = input("User ID (5 digits): ").strip()
    print("Current Password: ********")
    old_password = getpass.getpass("Current Password: ")
    print("New Password: ********")
    new_password = getpass.getpass("New Password: ")

    ok, message = auth.admin_change_password(user_id, old_password, new_password)
    print()
    print(message)


def main() -> None:
    auth = UserAuth()
    sm = SessionManager()

    while True:
        print()
        print("====================================")
        print("   CAPITAL STRATA SYSTEMS TERMINAL")
        print("====================================")
        print()
        print("1  Login")
        print("2  Reset Password")
        print("3  Change Password")
        print("4  Exit")

        choice = input("Select option: ").strip()

        if choice == "4":
            break

        if choice == "2":
            reset_password_flow(auth)
            continue

        if choice == "3":
            change_password_anytime_flow(auth)
            continue

        if choice != "1":
            print("Invalid option.")
            continue

        user_id = input("User ID (5 digits): ").strip()
        print("Password: ********")
        password = getpass.getpass("Password: ")

        success, message, role = auth.authenticate(user_id, password)

        print()
        print(message)

        if not success:
            print("Forgot password? Use option 2.")
            continue

        session = sm.create_session(user_id, role or "VIEWER")

        print()
        print("Login successful")
        print("User ID:", user_id)
        print("Role:", role)
        print("Session ID:", session.session_id[:12])
        print()
        print("CSS Terminal Ready")
        break


if __name__ == "__main__":
    main()