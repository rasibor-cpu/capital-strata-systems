# === CSS R8 BUILDER: OANDA LIVE MODE ENABLEMENT (PCNRASS SAFE) ===

from pathlib import Path

INPUT_FILE = Path("scripts/css_live_dashboard_R7_UNIFIED_GATE.py")
OUTPUT_FILE = Path("scripts/css_live_dashboard_R8_OANDA_LIVE_MODE.py")


def apply_oanda_mode_selection(content: str) -> str:
    """
    Inject OANDA live/practice selection into broker config
    """

    old_block = '''if selected == "OANDA":
        if not role_profile.get("can_use_paper_broker_mode", False):
            print(f"[RBAC] OANDA practice mode denied for role {role}.")
            record_rbac_event(
                "broker_mode_denied",
                SESSION_USER_CTX,
                {
                    "selected_broker": "OANDA",
                    "selected_broker_mode": "paper",
                    "reason": "role_cannot_use_paper_broker_mode",
                },
            )
            return False, "NONE", "paper"

        record_rbac_event(
            "broker_selected",
            SESSION_USER_CTX,
            {
                "selected_broker": "OANDA",
                "selected_broker_mode": "paper",
            },
        )
        print("[BROKER EXECUTION ARMED] Selected broker: OANDA / FX practice only")
        return True, "OANDA", "paper"
'''

    new_block = '''if selected == "OANDA":
        print("=== OANDA MODE ===")
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

            # Set live environment
            os.environ["OANDA_ENV"] = "live"
            os.environ["OANDA_BASE_URL"] = "https://api-fxtrade.oanda.com"

        else:
            if not role_profile.get("can_use_paper_broker_mode", False):
                print(f"[RBAC] OANDA practice mode denied for role {role}.")
                return False, "NONE", "paper"

            os.environ["OANDA_ENV"] = "practice"
            os.environ["OANDA_BASE_URL"] = "https://api-fxpractice.oanda.com"

        record_rbac_event(
            "broker_selected",
            SESSION_USER_CTX,
            {
                "selected_broker": "OANDA",
                "selected_broker_mode": broker_mode,
            },
        )

        print(f"[BROKER EXECUTION ARMED] Selected broker: OANDA / mode={broker_mode}")
        return True, "OANDA", broker_mode
'''

    if old_block not in content:
        raise Exception("Could not locate OANDA block to replace")

    return content.replace(old_block, new_block)


def update_display_scope(content: str) -> str:
    """
    Update dashboard display from 'practice only' to dynamic mode
    """

    content = content.replace(
        "EXECUTION SCOPE: OANDA FX PRACTICE ONLY",
        "EXECUTION SCOPE: OANDA FX (DYNAMIC MODE)"
    )

    return content


def main():
    if not INPUT_FILE.exists():
        print(f"[ERROR] Input file not found: {INPUT_FILE}")
        return

    content = INPUT_FILE.read_text(encoding="utf-8")

    content = apply_oanda_mode_selection(content)
    content = update_display_scope(content)

    OUTPUT_FILE.write_text(content, encoding="utf-8")

    print("[SUCCESS] R8 OANDA LIVE MODE FILE CREATED")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()