from pathlib import Path

INPUT_FILE = Path("scripts/css_live_dashboard_R13B_EXECUTION_BOUNDARY_FIXED.py")
OUTPUT_FILE = Path("scripts/css_live_dashboard_R13C_MODE_DOMINANCE.py")


def enforce_mode_dominance(content: str) -> str:
    """
    Force broker mode to follow global mode strictly
    """

    injection = '''
# === R13C GLOBAL MODE DOMINANCE ===
def enforce_mode_dominance():
    global SELECTED_BROKER_MODE

    if str(GLOBAL_BROKER_MODE).lower() == "live":
        if str(SELECTED_BROKER_MODE).lower() != "live":
            print("[MODE CORRECTION] Forcing broker mode to LIVE due to global mode")
            SELECTED_BROKER_MODE = "live"
'''

    if "def enforce_mode_dominance()" not in content:
        content = injection + "\n" + content

    return content


def hook_into_flow(content: str) -> str:
    anchor = 'print(f"[ENGINE MODE SELECTED] {ENGINE_MODE}")'

    if anchor not in content:
        raise Exception("Engine mode anchor not found")

    replacement = anchor + "\n\nenforce_mode_dominance()"

    return content.replace(anchor, replacement, 1)


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError("Input file missing")

    content = INPUT_FILE.read_text(encoding="utf-8")

    content = enforce_mode_dominance(content)
    content = hook_into_flow(content)

    OUTPUT_FILE.write_text(content, encoding="utf-8")

    print("[SUCCESS] R13C MODE DOMINANCE FILE CREATED")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()