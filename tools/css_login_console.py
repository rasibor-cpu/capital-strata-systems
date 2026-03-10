from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from backend.security.session_manager import SessionManager
from backend.security.user_auth import UserAuth, RECOVERY_QUESTIONS


def masked_password_input(prompt: str) -> str:
    """
    Reads password input while showing * for each typed character.
    Supports Backspace and blocks empty input.
    Works on Windows console.
    """
    import msvcrt

    while True:
        print(prompt, end="", flush=True)
        chars: list[str] = []

        while True:
            ch = msvcrt.getwch()

            if ch in ("\r", "\n"):
                print()
                password = "".join(chars)
                if password.strip() == "":
                    print("Password cannot be blank.")
                    break
                return password

            if ch == "\003":
                raise KeyboardInterrupt

            if ch == "\b":
                if chars:
                    chars.pop()
                    print("\b \b", end="", flush=True)
                continue

            if ch in ("\x00", "\xe0"):
                # swallow special keys
                _ = msvcrt.getwch()
                continue

            chars.append(ch)
            print("*", end="", flush=True)


def first_login_setup(auth, user_id):

    print()
    print("FIRST LOGIN SETUP REQUIRED")
    print("--------------------------")
    print("You must change your password and configure recovery options.")
    print()

    while True:
        print("New Password (min 6 chars): ******")
        new_password = masked_password_input("New Password: ")

        print("Confirm Password: ******")
        confirm_password = masked_password_input("Confirm Password: ")

        if new_password != confirm_password:
            print("Passwords do not match.\n")
            continue

        if len(new_password) < 6:
            print("Password must contain at least 6 characters.\n")
            continue

        break

    print()
    print("Select a password recovery question:\n")

    for i, q in enumerate(RECOVERY_QUESTIONS, start=1):
        print(f"{i}. {q}")

    while True:
        choice = input("\nSelect question number: ").strip()

        if not choice.isdigit():
            print("Enter a valid number.")
            continue

        choice_num = int(choice)

        if 1 <= choice_num <= len(RECOVERY_QUESTIONS):
            question = RECOVERY_QUESTIONS[choice_num - 1]
            break

        print("Invalid selection.")

    while True:
        answer = input("Recovery answer: ").strip()
        if answer == "":
            print("Recovery answer cannot be blank.")
            continue
        break

    users = auth._load_users()
    user = users[user_id]

    user["password"] = auth._hash_password(new_password)
    user["recovery_question"] = question
    user["recovery_answer_hash"] = auth._hash_answer(answer)
    user["must_change_password"] = False
    user["failed_attempts"] = 0
    user["locked"] = False

    users[user_id] = user
    auth._save_users(users)

    print("\nSetup complete.\n")


def reset_password_flow(auth):

    print()
    print("PASSWORD RESET")
    print("----------------")

    user_id = input("User ID (5 digits): ").strip()

    ok, question = auth.get_recovery_question(user_id)

    if not ok:
        print(question)
        return

    print()
    print("Security Question:")
    print(question)

    answer = input("Answer: ").strip()

    while True:
        print("New Password: ******")
        new_password = masked_password_input("New Password: ")

        print("Confirm New Password: ******")
        confirm_password = masked_password_input("Confirm New Password: ")

        if new_password != confirm_password:
            print("Passwords do not match.\n")
            continue

        ok, message = auth.reset_password(user_id, answer, new_password)
        print(message)
        break


def change_password_flow(auth):

    print()
    print("CHANGE PASSWORD")
    print("----------------")

    user_id = input("User ID (5 digits): ").strip()

    print("Current Password: ******")
    old_password = masked_password_input("Current Password: ")

    while True:
        print("New Password: ******")
        new_password = masked_password_input("New Password: ")

        print("Confirm New Password: ******")
        confirm_password = masked_password_input("Confirm New Password: ")

        if new_password != confirm_password:
            print("Passwords do not match.\n")
            continue

        ok, message = auth.change_password(user_id, old_password, new_password)
        print(message)
        break


def main():

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
            change_password_flow(auth)
            continue

        if choice != "1":
            print("Invalid option.")
            continue

        user_id = input("User ID (5 digits): ").strip()

        print("Password: ******")
        password = masked_password_input("Password: ")

        success, message, role, must_change = auth.authenticate(user_id, password)

        print()
        print(message)

        if not success:
            continue

        if must_change:
            first_login_setup(auth, user_id)

        session = sm.create_session(user_id, role)

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