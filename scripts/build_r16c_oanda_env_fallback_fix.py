from pathlib import Path

INPUT_FILE = Path("scripts/css_live_dashboard.py")
OUTPUT_FILE = Path("scripts/css_live_dashboard_R16C_OANDA_ENV_FIX.py")

old = '''        if broker_mode == "live":
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

new = '''        if broker_mode == "live":
            if not role_profile.get("can_use_live_broker_mode", False):
                print(f"[RBAC] OANDA live mode denied for role {role}. Falling back to paper.")
                broker_mode = "paper"

        if broker_mode == "live":
            os.environ["OANDA_ENV"] = "live"
            os.environ["OANDA_BASE_URL"] = "https://api-fxtrade.oanda.com"
        else:
            if not role_profile.get("can_use_paper_broker_mode", False):
                print(f"[RBAC] OANDA practice mode denied for role {role}.")
                return False, "NONE", "paper"

            os.environ["OANDA_ENV"] = "practice"
            os.environ["OANDA_BASE_URL"] = "https://api-fxpractice.oanda.com"
'''

text = INPUT_FILE.read_text(encoding="utf-8")

if old not in text:
    raise RuntimeError("OANDA environment block not found. No output written.")

text = text.replace(old, new, 1)

OUTPUT_FILE.write_text(text, encoding="utf-8")

print("[SUCCESS] R16C OANDA ENV FALLBACK FIX CREATED")
print(f"Output: {OUTPUT_FILE}")