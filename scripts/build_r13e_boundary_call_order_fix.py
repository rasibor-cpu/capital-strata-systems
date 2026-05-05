from pathlib import Path

INPUT_FILE = Path("scripts/css_live_dashboard_R13D_MODE_DOMINANCE_FIXED.py")
OUTPUT_FILE = Path("scripts/css_live_dashboard_R13E_BOUNDARY_ORDER_FIXED.py")


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Missing input file: {INPUT_FILE}")

    text = INPUT_FILE.read_text(encoding="utf-8")

    # Remove premature boundary call near engine mode selection.
    text = text.replace(
        'print(f"[ENGINE MODE SELECTED] {ENGINE_MODE}")\n\nenforce_execution_boundary()',
        'print(f"[ENGINE MODE SELECTED] {ENGINE_MODE}")',
        1,
    )

    # Insert boundary call after capital source activation.
    anchor = "pcnrass_activate_capital_source()"

    if anchor not in text:
        raise RuntimeError("Capital activation anchor not found. No output written.")

    text = text.replace(
        anchor,
        anchor + "\n\nenforce_mode_dominance()\nenforce_execution_boundary()",
        1,
    )

    OUTPUT_FILE.write_text(text, encoding="utf-8")

    print("[SUCCESS] R13E BOUNDARY ORDER FIX FILE CREATED")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()