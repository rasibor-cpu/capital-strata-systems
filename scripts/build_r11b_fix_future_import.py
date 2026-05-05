from pathlib import Path

INPUT_FILE = Path("scripts/css_live_dashboard_R11_BROKER_LOCK.py")
OUTPUT_FILE = Path("scripts/css_live_dashboard_R11B_BROKER_LOCK_FIXED.py")


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
        raise RuntimeError("No __future__ import found. Aborting to prevent regression.")

    # Reconstruct file with future imports at top
    new_text = "\n".join(future_lines + [""] + other_lines)

    OUTPUT_FILE.write_text(new_text, encoding="utf-8")

    print("[SUCCESS] R11B FUTURE IMPORT FIX FILE CREATED")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()