from pathlib import Path

INPUT_FILE = Path("scripts/css_live_dashboard_R9C_LIVE_MODE_FIXED.py")
OUTPUT_FILE = Path("scripts/css_live_dashboard_R10_AUTH_FIRST.py")


def reorder_auth_first(content: str) -> str:
    """
    Move authentication BEFORE any mode selection
    """

    # Find where global broker mode is triggered
    old_sequence = '''
GLOBAL_BROKER_MODE = select_global_broker_mode()

SESSION_USER_CTX = authenticate_startup_user()
'''

    new_sequence = '''
SESSION_USER_CTX = authenticate_startup_user()

GLOBAL_BROKER_MODE = select_global_broker_mode()
'''

    if old_sequence not in content:
        raise Exception("Expected startup sequence not found. Aborting to prevent regression.")

    content = content.replace(old_sequence, new_sequence, 1)

    return content


def block_pre_auth_execution(content: str) -> str:
    """
    Add hard guard to ensure nothing runs before auth
    """

    guard = '''
# === R10 AUTH-FIRST HARD GUARD ===
if "SESSION_USER_CTX" not in globals():
    raise Exception("AUTHENTICATION_REQUIRED_BEFORE_SYSTEM_START")
'''

    insert_point = 'SESSION_USER_CTX = authenticate_startup_user()'

    content = content.replace(
        insert_point,
        insert_point + "\n" + guard
    )

    return content


def main():
    if not INPUT_FILE.exists():
        print(f"[ERROR] Input file not found: {INPUT_FILE}")
        return

    content = INPUT_FILE.read_text(encoding="utf-8")

    content = reorder_auth_first(content)
    content = block_pre_auth_execution(content)

    OUTPUT_FILE.write_text(content, encoding="utf-8")

    print("[SUCCESS] R10 AUTH-FIRST FLOW FILE CREATED")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()