from pathlib import Path

INPUT_FILE = Path("scripts/css_live_dashboard_R12B_OPTIONS_IDENTITY_FIXED.py")
OUTPUT_FILE = Path("scripts/css_live_dashboard_R13_EXECUTION_BOUNDARY.py")


def inject_execution_guard(content: str) -> str:
    """
    Add strict execution boundary enforcement
    """

    if "def enforce_execution_boundary()" in content:
        return content

    injection = '''
# === R13 EXECUTION BOUNDARY ENFORCEMENT ===
def enforce_execution_boundary():
    mode = str(SELECTED_BROKER_MODE).lower()

    if mode == "live":
        # Live mode must not use simulated paths
        if capital_governor.capital_source_label().upper() == "SIMULATED":
            print("[BOUNDARY VIOLATION] Live mode cannot use simulated capital")
            import sys
            sys.exit(1)

    elif mode == "paper":
        # Paper mode must not attempt live execution
        if "LIVE" in str(globals()):
            pass  # safeguard placeholder

    else:
        print(f"[UNKNOWN MODE] {mode}")
        import sys
        sys.exit(1)
'''

    return injection + "\n" + content


def hook_into_startup(content: str) -> str:
    """
    Ensure boundary enforcement runs after mode selection
    """

    anchor = 'print(f"[ENGINE MODE SELECTED] {ENGINE_MODE}")'

    if anchor not in content:
        raise Exception("Engine mode selection anchor not found")

    replacement = anchor + "\n\nenforce_execution_boundary()"

    return content.replace(anchor, replacement, 1)


def block_paper_trades_in_live(content: str) -> str:
    """
    Prevent any paper trade creation in live mode
    """

    old = '[OPTIONS PAPER OPENED]'
    new = '''[OPTIONS PAPER OPENED]
if str(SELECTED_BROKER_MODE).lower() == "live":
    print("[BOUNDARY BLOCK] Paper trade blocked in live mode")
    continue
'''

    content = content.replace(old, new)

    old2 = '[FX PAPER OPENED]'
    new2 = '''[FX PAPER OPENED]
if str(SELECTED_BROKER_MODE).lower() == "live":
    print("[BOUNDARY BLOCK] Paper FX blocked in live mode")
    continue
'''

    content = content.replace(old2, new2)

    old3 = '[CRYPTO PAPER OPENED]'
    new3 = '''[CRYPTO PAPER OPENED]
if str(SELECTED_BROKER_MODE).lower() == "live":
    print("[BOUNDARY BLOCK] Paper crypto blocked in live mode")
    continue
'''

    content = content.replace(old3, new3)

    return content


def main():
    if not INPUT_FILE.exists():
        print(f"[ERROR] Input file not found: {INPUT_FILE}")
        return

    content = INPUT_FILE.read_text(encoding="utf-8")

    content = inject_execution_guard(content)
    content = hook_into_startup(content)
    content = block_paper_trades_in_live(content)

    OUTPUT_FILE.write_text(content, encoding="utf-8")

    print("[SUCCESS] R13 EXECUTION BOUNDARY FILE CREATED")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()