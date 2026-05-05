from pathlib import Path

INPUT_FILE = Path("scripts/css_live_dashboard_R13F_BOUNDARY_ORDER_SAFE.py")
OUTPUT_FILE = Path("scripts/css_live_dashboard_R14C_PROFITABILITY_SAFE.py")


def normalize_future_import(text: str) -> str:
    lines = text.splitlines()
    future = [l for l in lines if l.startswith("from __future__")]
    rest = [l for l in lines if not l.startswith("from __future__")]
    return "\n".join(future + [""] + rest) + "\n"


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Missing input file: {INPUT_FILE}")

    text = INPUT_FILE.read_text(encoding="utf-8")

    marker = "# === R14C PROFITABILITY ENGINE ==="
    engine = '''
# === R14C PROFITABILITY ENGINE ===
def compute_opportunity_score(data: dict) -> float:
    price = float(data.get("price", 0.0) or 0.0)
    vwap = float(data.get("vwap", price or 1.0) or 1.0)
    momentum = float(data.get("momentum", 0.0) or 0.0)
    pressure = float(data.get("pressure_score", 0.0) or 0.0)

    vwap_edge = abs(price - vwap) / max(vwap, 1e-9)
    score = (
        0.4 * min(vwap_edge * 5.0, 1.0)
        + 0.3 * min(abs(momentum), 1.0)
        + 0.3 * min(abs(pressure), 1.0)
    )
    return max(0.0, min(score, 1.0))


def threshold_for_mode(mode: str) -> float:
    return {
        "SAFE": 0.80,
        "CONSERVATIVE": 0.70,
        "BALANCED": 0.60,
        "AGGRESSIVE": 0.50,
        "EXPANSION": 0.40,
    }.get(str(mode).upper(), 0.65)
'''

    if marker not in text:
        text = engine + "\n" + text

    # Safe visibility-only integration first: print threshold at startup.
    target = 'print(f"[ENGINE MODE SELECTED] {ENGINE_MODE}")'
    replacement = (
        target
        + '\\nprint(f"[R14C PROFITABILITY ACTIVE] mode={ENGINE_MODE} threshold={threshold_for_mode(ENGINE_MODE):.2f}")'
    )

    if "[R14C PROFITABILITY ACTIVE]" not in text:
        if target not in text:
            raise RuntimeError("Engine mode selected print anchor not found.")
        text = text.replace(target, replacement, 1)

    text = normalize_future_import(text)
    OUTPUT_FILE.write_text(text, encoding="utf-8")

    print("[SUCCESS] R14C PROFITABILITY SAFE FILE CREATED")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()