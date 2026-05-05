from pathlib import Path

INPUT_FILE = Path("scripts/css_live_dashboard_R9B_STARTUP_FLOW_CLEAN.py")
OUTPUT_FILE = Path("scripts/css_live_dashboard_R9C_LIVE_MODE_FIXED.py")


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Missing input file: {INPUT_FILE}")

    text = INPUT_FILE.read_text(encoding="utf-8")

    # 1) Accept LIVE confirmation case-insensitively.
    text = text.replace(
        'if confirm == "LIVE":\n            return "live"',
        'if confirm.strip().upper() == "LIVE":\n            return "live"'
    )

    # 2) Remove misleading OANDA practice-only broker description.
    text = text.replace(
        'print("2. OANDA - FX practice execution")',
        'print("2. OANDA - FX broker")'
    )

    # 3) Remove misleading execution scope label.
    text = text.replace(
        'print("EXECUTION SCOPE: OANDA FX PRACTICE ONLY")',
        'print(f"EXECUTION SCOPE: OANDA FX {str(SELECTED_BROKER_MODE).upper()}")'
    )

    text = text.replace(
        '"EXECUTION SCOPE: OANDA FX PRACTICE ONLY"',
        'f"EXECUTION SCOPE: OANDA FX {str(SELECTED_BROKER_MODE).upper()}"'
    )

    # 4) Improve displayed user identity: show user id and display name together.
    text = text.replace(
        'print(f"USER ID: {SESSION_USER_CTX.get(\'user_id\')}")',
        'print(f"USER ID: {SESSION_USER_CTX.get(\'user_id\')} | NAME: {SESSION_USER_CTX.get(\'display_name\')}")'
    )

    # 5) Fix OANDA mode inheritance print and prevent paper fallback after global live.
    text = text.replace(
        'print(f"[BROKER EXECUTION ARMED] Selected broker: OANDA / mode={broker_mode}")',
        'print(f"[BROKER EXECUTION ARMED] Selected broker: OANDA / mode={broker_mode} / url={os.environ.get(\'OANDA_BASE_URL\', \'UNKNOWN\')}")'
    )

    # 6) Strong live-capital warning: live mode must not pretend simulated capital is broker capital.
    old_capital_print = '''    print(
        f"[CAPITAL SOURCE ACTIVE] source={capital_governor.capital_source_label()} "
        f"mode={SELECTED_BROKER_MODE} available=${capital_governor.available_capital():,.2f}"
    )
'''

    new_capital_print = '''    if str(SELECTED_BROKER_MODE).lower() == "live":
        if float(capital_governor.real_balance or 0.0) <= 0.0:
            print(
                f"[LIVE CAPITAL WARNING] broker={SELECTED_BROKER} "
                f"mode=live url={os.environ.get('OANDA_BASE_URL', 'UNKNOWN')} "
                f"balance_fetch_failed_or_zero. Live trading must remain blocked until real balance is loaded."
            )

    print(
        f"[CAPITAL SOURCE ACTIVE] source={capital_governor.capital_source_label()} "
        f"mode={SELECTED_BROKER_MODE} available=${capital_governor.available_capital():,.2f}"
    )
'''

    if old_capital_print in text:
        text = text.replace(old_capital_print, new_capital_print, 1)

    # 7) Ensure live mode does not silently use simulated pool as the label.
    text = text.replace(
        'return "SIMULATED"\n        return self.balance_source or "REAL_BROKER"',
        'return "SIMULATED"\n        return self.balance_source or f"REAL_BROKER_{SELECTED_BROKER}"'
    )

    OUTPUT_FILE.write_text(text, encoding="utf-8")

    print("[SUCCESS] R9C LIVE MODE DISPLAY/CAPITAL FIX FILE CREATED")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()