from pathlib import Path

INPUT_FILE = Path("scripts/css_live_dashboard_R13F_BOUNDARY_ORDER_SAFE.py")
OUTPUT_FILE = Path("scripts/css_live_dashboard_R14D_PROFITABILITY_SAFE.py")


def normalize_future_import(text: str) -> str:
    lines = text.splitlines()
    future = [l for l in lines if l.startswith("from __future__")]
    rest = [l for l in lines if not l.startswith("from __future__")]
    return "\n".join(future + [""] + rest) + "\n"


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Missing input file: {INPUT_FILE}")

    text = INPUT_FILE.read_text(encoding="utf-8")

    engine = '''
# === R14D PROFITABILITY ENGINE ===
def threshold_for_mode(mode: str) -> float:
    return {
        "SAFE": 0.80,
        "CONSERVATIVE": 0.70,
        "BALANCED": 0.60,
        "AGGRESSIVE": 0.50,
        "EXPANSION": 0.40,
    }.get(str(mode).upper(), 0.65)
'''

    if "# === R14D PROFITABILITY ENGINE ===" not in text:
        text = engine + "\n" + text

    target = 'print(f"[ENGINE MODE SELECTED] {ENGINE_MODE}")'

    replacement = '''print(f"[ENGINE MODE SELECTED] {ENGINE_MODE}")
print(f"[R14D PROFITABILITY ACTIVE] mode={ENGINE_MODE} threshold={threshold_for_mode(ENGINE_MODE):.2f}")'''

    if "[R14D PROFITABILITY ACTIVE]" not in text:
        if target not in text:
            raise RuntimeError("Engine mode selected print anchor not found.")
        text = text.replace(target, replacement, 1)

    text = normalize_future_import(text)

    OUTPUT_FILE.write_text(text, encoding="utf-8")

    print("[SUCCESS] R14D PROFITABILITY SAFE FILE CREATED")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()