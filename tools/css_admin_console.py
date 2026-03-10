from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from backend.security.user_auth import UserAuth, RECOVERY_QUESTIONS
from backend.security.session_manager import SessionManager


PHASE1_ADMIN_ID = "00000"

DEPARTMENTS = {
    "0": "CONTROL / ADMIN / SUPER USER / AUDIT / TECH / FINCON",
    "1": "CASH AND TELLERS",
    "2": "TREASURY AND TREASURY OPERATIONS",
    "3": "TRADE AND TRADE OPERATIONS",
    "4": "FUNDS TRANSFER AND SUNDRY OPERATIONS",
    "5": "RETAIL BANKING",
    "6": "COMMERCIAL BANKING",
    "7": "CORPORATE AND INSTITUTIONAL BANKING",
    "8": "LEGAL AND CORPORATE SERVICES",
    "9": "CREDIT ADMINISTRATION",
}

DEPARTMENT_DEFAULT_ROLES = {
    "0": ["ADMIN", "SUPER_USER", "AUDIT", "TECH", "FINCON"],
    "1": ["TELLER", "CASH_OFFICER", "BRANCH_SUPERVISOR"],
    "2": ["TRADER", "TREASURY_OPERATIONS", "TREASURY_MANAGER"],
    "3": ["TRADE_OFFICER", "TRADE_OPERATIONS", "TRADE_MANAGER"],
    "4": ["FUNDS_TRANSFER_OFFICER", "SETTLEMENT_OFFICER", "OPERATIONS_SUPERVISOR"],
    "5": ["RETAIL_OFFICER", "CUSTOMER_SERVICE", "RETAIL_MANAGER"],
    "6": ["COMMERCIAL_OFFICER", "COMMERCIAL_MANAGER"],
    "7": ["CORPORATE_OFFICER", "INSTITUTIONAL_BANKING_OFFICER", "CORPORATE_MANAGER"],
    "8": ["LEGAL_OFFICER", "CORPORATE_SERVICES_OFFICER", "COMPLIANCE_OFFICER"],
    "9": ["CREDIT_ADMIN_OFFICER", "CREDIT_CONTROL", "CREDIT_MANAGER"],
}


def masked_password_input(prompt: str) -> str:
    import msvcrt

    while True:
        print(prompt, end="", flush=True)
        chars = []

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
                _ = msvcrt.getwch()
                continue

            chars.append(ch)
            print("*", end="", flush=True)


def admin_login(auth, sm):
    print()
    print("====================================")
    print(" CSS ADMIN AUTHENTICATION REQUIRED ")
    print("====================================")
    print()
    print("Phase 1 rule: only ADMIN user ID 00000 may create users.")
    print()

    user_id = input("Admin User ID (5 digits): ").strip()
    password = masked_password_input("Admin Password: ")

    success, message, role, must_change = auth.authenticate(user_id, password)

    print()
    print(message)

    if not success:
        return None

    if user_id != PHASE1_ADMIN_ID:
        print("Access denied. Phase 1 user creation is restricted to ADMIN ID 00000 only.")
        return None

    if role != "ADMIN":
        print("Access denied. Only ADMIN role may access this console.")
        return None

    if must_change:
        print("Access denied. Complete first-login password change in the main CSS terminal first.")
        return None

    session = sm.create_session(user_id, role)
    print("Admin authentication successful.")
    print("Session ID:", session.session_id[:12])
    return session


def get_next_user_id(auth, dept_prefix: str) -> str:
    users = auth._load_users()
    matching_ids = sorted(uid for uid in users.keys() if uid.startswith(dept_prefix) and uid.isdigit() and len(uid) == 5)

    if dept_prefix == "0":
        if not matching_ids:
            return "00000"
        max_num = max(int(uid) for uid in matching_ids)
        return f"{max_num + 1:05d}"

    if not matching_ids:
        return f"{dept_prefix}0001"

    max_num = max(int(uid) for uid in matching_ids)
    next_num = max_num + 1

    if str(next_num)[0] != dept_prefix:
        raise ValueError(f"No more available IDs for department prefix {dept_prefix}.")

    return f"{next_num:05d}"


def choose_department() -> str:
    print()
    print("SELECT DEPARTMENT")
    print("-----------------")
    for code, name in DEPARTMENTS.items():
        print(f"{code}  {name}")

    while True:
        dept_code = input("Enter department code: ").strip()
        if dept_code in DEPARTMENTS:
            return dept_code
        print("Invalid department code.")


def choose_role_for_department(dept_code: str) -> str:
    allowed_roles = DEPARTMENT_DEFAULT_ROLES[dept_code]

    print()
    print("SELECT ROLE")
    print("-----------")
    for idx, role in enumerate(allowed_roles, start=1):
        print(f"{idx}  {role}")

    while True:
        choice = input("Select role number: ").strip()
        if not choice.isdigit():
            print("Enter a valid number.")
            continue

        idx = int(choice)
        if 1 <= idx <= len(allowed_roles):
            return allowed_roles[idx - 1]

        print("Invalid selection.")


def create_user(auth):
    print()
    print("CREATE NEW USER")
    print("----------------")

    dept_code = choose_department()
    generated_user_id = get_next_user_id(auth, dept_code)
    role = choose_role_for_department(dept_code)

    print()
    print("Generated User ID:", generated_user_id)
    print("Department:", DEPARTMENTS[dept_code])
    print("Assigned Role:", role)
    print()

    while True:
        print("Initial Password (min 6 chars): ******")
        password = masked_password_input("Initial Password: ")

        print("Confirm Password: ******")
        confirm = masked_password_input("Confirm Password: ")

        if len(password) < 6:
            print("Password too short.")
            continue

        if password != confirm:
            print("Passwords do not match.")
            continue

        break

    print()
    print("Select recovery question:")
    print()

    for i, q in enumerate(RECOVERY_QUESTIONS, start=1):
        print(f"{i}. {q}")

    while True:
        choice = input("Select question number: ").strip()

        if not choice.isdigit():
            print("Enter a valid number.")
            continue

        num = int(choice)
        if 1 <= num <= len(RECOVERY_QUESTIONS):
            question = RECOVERY_QUESTIONS[num - 1]
            break

        print("Invalid selection.")

    while True:
        answer = input("Recovery answer: ").strip()
        if answer == "":
            print("Recovery answer cannot be blank.")
            continue
        break

    confirm_create = input("Create user now? (Y/N): ").strip().upper()
    if confirm_create != "Y":
        print("User creation cancelled.")
        return

    try:
        auth.create_user(
            user_id=generated_user_id,
            password=password,
            role=role,
            recovery_question=question,
            recovery_answer=answer,
            must_change_password=True,
        )
        print()
        print("User created successfully.")
        print("User ID:", generated_user_id)
        print("Department:", DEPARTMENTS[dept_code])
        print("Role:", role)
        print("First login password change: REQUIRED")

    except Exception as e:
        print()
        print("Error:", e)


def list_users(auth):
    print()
    print("SYSTEM USERS")
    print("------------")

    users = auth._load_users()

    if not users:
        print("No users found.")
        return

    for uid, data in sorted(users.items()):
        prefix = uid[0]
        dept_name = DEPARTMENTS.get(prefix, "UNKNOWN")
        status = "LOCKED" if data.get("locked", False) else "ACTIVE"
        must_change = "YES" if data.get("must_change_password", False) else "NO"

        print(
            f"User ID: {uid} | Dept: {dept_name} | Role: {data.get('role', '')} | "
            f"Status: {status} | Must Change Password: {must_change}"
        )


def unlock_user(auth):
    print()
    print("UNLOCK USER")
    print("-----------")

    user_id = input("User ID: ").strip()
    users = auth._load_users()

    if user_id not in users:
        print("User not found.")
        return

    users[user_id]["locked"] = False
    users[user_id]["failed_attempts"] = 0
    auth._save_users(users)

    print("User unlocked.")


def main():
    auth = UserAuth()
    sm = SessionManager()

    session = admin_login(auth, sm)

    if session is None:
        return

    while True:
        print()
        print("====================================")
        print(" CSS ADMIN USER MANAGEMENT CONSOLE ")
        print("====================================")
        print()
        print("Authenticated Admin:", PHASE1_ADMIN_ID)
        print()
        print("1 Create User")
        print("2 List Users")
        print("3 Unlock User")
        print("4 Exit")

        choice = input("Select option: ").strip()

        if choice == "4":
            break
        if choice == "1":
            create_user(auth)
        elif choice == "2":
            list_users(auth)
        elif choice == "3":
            unlock_user(auth)
        else:
            print("Invalid option.")


if __name__ == "__main__":
    main()