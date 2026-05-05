from pathlib import Path

INPUT_FILE = Path("scripts/css_live_dashboard_R13D_MODE_DOMINANCE_FIXED.py")
OUTPUT_FILE = Path("scripts/css_live_dashboard_R13F_BOUNDARY_ORDER_SAFE.py")


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Missing input file: {INPUT_FILE}")

    lines = INPUT_FILE.read_text(encoding="utf-8").splitlines()

    cleaned = []
    for line in lines:
        if line.strip() in {"enforce_execution_boundary()", "enforce_mode_dominance()"}:
            continue
        cleaned.append(line)

    # Find the real standalone activation CALL, not the def line.
    activation_indexes = [
        i for i, line in enumerate(cleaned)
        if line.strip() == "pcnrass_activate_capital_source()"
    ]

    if not activation_indexes:
        raise RuntimeError("Standalone pcnrass_activate_capital_source() call not found.")

    idx = activation_indexes[-1]

    fixed = (
        cleaned[:idx]
        + ["enforce_mode_dominance()"]
        + [cleaned[idx]]
        + ["enforce_execution_boundary()"]
        + cleaned[idx + 1:]
    )

    OUTPUT_FILE.write_text("\n".join(fixed) + "\n", encoding="utf-8")

    print("[SUCCESS] R13F SAFE BOUNDARY ORDER FILE CREATED")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()