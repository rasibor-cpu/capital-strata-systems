# === CSS R9 BUILDER: STARTUP FLOW GOVERNANCE (PCNRASS SAFE) ===

from pathlib import Path

INPUT_FILE = Path("scripts/css_live_dashboard_R8_OANDA_LIVE_MODE.py")
OUTPUT_FILE = Path("scripts/css_live_dashboard_R9_STARTUP_FLOW.py")


def inject_global_broker_mode(content: str) -> str:
    """
    Add global broker mode selection BEFORE broker selection
    """

    anchor = "def select_broker_execution_config() -> tuple[bool, str, str]:"

    injection = '''
def select_global_broker_mode():
    print("=== GLOBAL BROKER MODE ===")
    print("1. PAPER / PRACTICE (default)")
    print("2. LIVE (real trading)")

    choice = input("Enter mode (1-2) [default=1]: ").strip() or "1"

    if choice == "2":
        confirm = input("Type LIVE to confirm GLOBAL LIVE trading: ").strip()
        if confirm == "LIVE":
            return "live"

    return "paper"


GLOBAL_BROKER_MODE = select_global_broker_mode()
'''

    if "GLOBAL_BROKER_MODE" not in content:
        content = content.replace(anchor, injection + "\n" + anchor)

    return content


def override_oanda_mode_logic(content: str) -> str:
    """
    Remove internal OANDA mode selection and use global mode instead
    """

    old_logic = 'print("=== OANDA MODE ===")'

    if old_logic in content:
        # Remove entire OANDA mode selection block
        content = content.replace(
            '''print("=== OANDA MODE ===")
        print("1. PRACTICE (default)")
        print("2. LIVE (real account)")

        mode_choice = input("Enter OANDA mode (1-2) [default=1]: ").strip() or "1"
        broker_mode = "live" if mode_choice == "2" else "paper"

        if broker_mode == "live":
            if not role_profile.get("can_use_live_broker_mode", False):
                print(f"[RBAC] OANDA live mode denied for role {role}. Falling back to practice.")
                broker_mode = "paper"

            confirm = input("Type LIVE to confirm OANDA LIVE trading: ").strip()
            if confirm != "LIVE":
                print("[OANDA LIVE CANCELLED] Falling back to practice mode")
                broker_mode = "paper"

            os.environ["OANDA_ENV"] = "live"
            os.environ["OANDA_BASE_URL"] = "https://api-fxtrade.oanda.com"

        else:
            if not role_profile.get("can_use_paper_broker_mode", False):
                print(f"[RBAC] OANDA practice mode denied for role {role}.")
                return False, "NONE", "paper"

            os.environ["OANDA_ENV"] = "practice"
            os.environ["OANDA_BASE_URL"] = "https://api-fxpractice.oanda.com"
''',
            '''
        broker_mode = GLOBAL_BROKER_MODE

        if broker_mode == "live":
            if not role_profile.get("can_use_live_broker_mode", False):
                print(f"[RBAC] OANDA live mode denied for role {role}. Falling back to paper.")
                broker_mode = "paper"

            os.environ["OANDA_ENV"] = "live"
            os.environ["OANDA_BASE_URL"] = "https://api-fxtrade.oanda.com"

        else:
            os.environ["OANDA_ENV"] = "practice"
            os.environ["OANDA_BASE_URL"] = "https://api-fxpractice.oanda.com"
'''
        )

    return content


def fix_execution_scope_display(content: str) -> str:
    """
    Fix dashboard display inconsistency
    """

    content = content.replace(
        "EXECUTION SCOPE: OANDA FX PRACTICE ONLY",
        'f"EXECUTION SCOPE: OANDA FX {SELECTED_BROKER_MODE.upper()}"'
    )

    return content


def main():
    if not INPUT_FILE.exists():
        print(f"[ERROR] Input file not found: {INPUT_FILE}")
        return

    content = INPUT_FILE.read_text(encoding="utf-8")

    content = inject_global_broker_mode(content)
    content = override_oanda_mode_logic(content)
    content = fix_execution_scope_display(content)

    OUTPUT_FILE.write_text(content, encoding="utf-8")

    print("[SUCCESS] R9 STARTUP FLOW FILE CREATED")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()