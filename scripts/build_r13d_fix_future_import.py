from pathlib import Path

INPUT_FILE = Path("scripts/css_live_dashboard_R13C_MODE_DOMINANCE.py")
OUTPUT_FILE = Path("scripts/css_live_dashboard_R13D_MODE_DOMINANCE_FIXED.py")


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Missing input file: {INPUT_FILE}")

    text = INPUT_FILE.read_text(encoding="utf-8")
    lines = text.splitlines()

    future_lines = []
    other_lines = []

    for line in lines:
        if line.startswith("from __future__"):
            future_lines.append(line)
        else:
            other_lines.append(line)

    if not future_lines:
        raise RuntimeError("No __future__ import found. Aborting.")

    OUTPUT_FILE.write_text("\n".join(future_lines + [""] + other_lines), encoding="utf-8")

    print("[SUCCESS] R13D FUTURE IMPORT FIX FILE CREATED")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()