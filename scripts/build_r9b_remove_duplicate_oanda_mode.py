from pathlib import Path

INPUT_FILE = Path("scripts/css_live_dashboard_R9_STARTUP_FLOW.py")
OUTPUT_FILE = Path("scripts/css_live_dashboard_R9B_STARTUP_FLOW_CLEAN.py")

OLD_BLOCK = '''        print("=== OANDA MODE ===")
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
'''

NEW_BLOCK = '''        broker_mode = GLOBAL_BROKER_MODE

        if broker_mode == "live":
            if not role_profile.get("can_use_live_broker_mode", False):
                print(f"[RBAC] OANDA live mode denied for role {role}. Falling back to paper.")
                broker_mode = "paper"

            os.environ["OANDA_ENV"] = "live"
            os.environ["OANDA_BASE_URL"] = "https://api-fxtrade.oanda.com"

        else:
            if not role_profile.get("can_use_paper_broker_mode", False):
                print(f"[RBAC] OANDA practice mode denied for role {role}.")
                return False, "NONE", "paper"

            os.environ["OANDA_ENV"] = "practice"
            os.environ["OANDA_BASE_URL"] = "https://api-fxpractice.oanda.com"
'''

def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Missing input file: {INPUT_FILE}")

    text = INPUT_FILE.read_text(encoding="utf-8")

    if OLD_BLOCK not in text:
        raise RuntimeError("Duplicate OANDA mode block not found. Do not proceed manually.")

    text = text.replace(OLD_BLOCK, NEW_BLOCK, 1)

    OUTPUT_FILE.write_text(text, encoding="utf-8")

    print("[SUCCESS] R9B STARTUP FLOW CLEAN FILE CREATED")
    print(f"Output: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()