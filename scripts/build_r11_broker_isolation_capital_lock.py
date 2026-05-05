from pathlib import Path

INPUT_FILE = Path("scripts/css_live_dashboard.py")
OUTPUT_FILE = Path("scripts/css_live_dashboard_R11_BROKER_LOCK.py")


def isolate_broker_urls(content: str) -> str:
    """
    Ensure broker URLs are strictly tied to selected broker
    """

    # Remove any global/shared OANDA URL usage
    content = content.replace(
        'os.environ.get("OANDA_BASE_URL", "UNKNOWN")',
        'get_active_broker_url()'
    )

    # Inject broker-specific URL resolver
    if "def get_active_broker_url()" not in content:
        injection = '''
# === R11 BROKER URL ISOLATION ===
def get_active_broker_url():
    if SELECTED_BROKER == "OANDA":
        return os.environ.get("OANDA_BASE_URL", "OANDA_NOT_SET")
    elif SELECTED_BROKER == "COINBASE":
        return "https://api.coinbase.com"
    return "NO_BROKER_SELECTED"
'''
        content = injection + "\n" + content

    return content


def enforce_capital_hard_lock(content: str) -> str:
    """
    Prevent ANY simulated capital usage in live mode
    """

    old_block = '''print(
        f"[CAPITAL SOURCE ACTIVE] source={capital_governor.capital_source_label()} "
        f"mode={SELECTED_BROKER_MODE} available=${capital_governor.available_capital():,.2f}"
    )'''

    new_block = '''# === R11 CAPITAL HARD LOCK ===
if str(SELECTED_BROKER_MODE).lower() == "live":
    real_balance = float(getattr(capital_governor, "real_balance", 0.0) or 0.0)

    if real_balance <= 0.0:
        print(
            f"[LIVE CAPITAL BLOCKED] broker={SELECTED_BROKER} "
            f"url={get_active_broker_url()} "
            f"reason=NO_REAL_BALANCE"
        )

        print("[SYSTEM HALT] Live trading disabled until real broker balance is loaded.")
        
        # HARD STOP — prevent fake execution
        import sys
        sys.exit(1)

print(
    f"[CAPITAL SOURCE ACTIVE] source={capital_governor.capital_source_label()} "
    f"mode={SELECTED_BROKER_MODE} available=${capital_governor.available_capital():,.2f}"
)'''

    if old_block not in content:
        raise Exception("Capital print block not found — aborting to prevent regression.")

    content = content.replace(old_block, new_block, 1)

    return content


def main():
    if not INPUT_FILE.exists():
        print(f"[ERROR] Input file not found: {INPUT_FILE}")
        return

    content = INPUT_FILE.read_text(encoding="utf-8")

    content = isolate_broker_urls(content)
    content = enforce_capital_hard_lock(content)

    OUTPUT_FILE.write_text(content, encoding="utf-8")

    print("[SUCCESS] R11 BROKER LOCK FILE CREATED")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()