from pathlib import Path

INPUT_FILE = Path("scripts/css_live_dashboard_R14D_PROFITABILITY_SAFE.py")
OUTPUT_FILE = Path("scripts/css_live_dashboard_R14E_PROFITABILITY_GATE.py")


def inject_engine(text: str) -> str:
    if "compute_opportunity_score" in text:
        return text

    block = '''
# === R14E PROFITABILITY ENGINE ===

def compute_opportunity_score(data: dict) -> float:
    price = float(data.get("price", 0.0) or 0.0)
    vwap = float(data.get("vwap", price or 1.0) or 1.0)
    momentum = float(data.get("momentum", 0.0) or 0.0)
    pressure = float(data.get("pressure_score", 0.0) or 0.0)

    vwap_edge = abs(price - vwap) / max(vwap, 1e-9)

    return max(0.0, min(
        0.4 * min(vwap_edge * 5.0, 1.0) +
        0.3 * min(abs(momentum), 1.0) +
        0.3 * min(abs(pressure), 1.0),
        1.0
    ))
'''

    return block + "\n" + text


def inject_guard(text: str) -> str:
    target = "Fetched candles for"

    lines = text.splitlines()
    out = []
    inserted = False

    for line in lines:
        out.append(line)

        if target in line and not inserted:
            out.append("        score = compute_opportunity_score(data if 'data' in locals() else {})")
            out.append("        threshold = threshold_for_mode(ENGINE_MODE)")
            out.append("        allow_trade = score >= threshold")
            out.append("        print(f\"[R14E CHECK] {symbol} score={score:.2f} threshold={threshold:.2f}\")")
            inserted = True

    return "\n".join(out)


def normalize_future(text: str) -> str:
    lines = text.splitlines()
    future = [l for l in lines if l.startswith("from __future__")]
    rest = [l for l in lines if not l.startswith("from __future__")]
    return "\n".join(future + [""] + rest)


def main():
    text = INPUT_FILE.read_text(encoding="utf-8")

    text = inject_engine(text)
    text = inject_guard(text)
    text = normalize_future(text)

    OUTPUT_FILE.write_text(text, encoding="utf-8")

    print("[SUCCESS] R14E PROFITABILITY GATE FILE CREATED")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()