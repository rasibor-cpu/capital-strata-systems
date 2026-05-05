from pathlib import Path

INPUT_FILE = Path("scripts/css_live_dashboard_R13F_BOUNDARY_ORDER_SAFE.py")
OUTPUT_FILE = Path("scripts/css_live_dashboard_R14B_PROFITABILITY.py")


def inject_engine(content: str) -> str:
    if "compute_opportunity_score" in content:
        return content

    injection = '''
# === R14B PROFITABILITY ENGINE ===

def compute_opportunity_score(data: dict) -> float:
    price = float(data.get("price", 0.0) or 0.0)
    vwap = float(data.get("vwap", price or 1.0) or 1.0)

    vwap_edge = abs(price - vwap) / max(vwap, 1e-9)

    momentum = float(data.get("momentum", 0.0) or 0.0)
    pressure = float(data.get("pressure_score", 0.0) or 0.0)

    score = (
        0.4 * min(vwap_edge * 5.0, 1.0) +
        0.3 * min(abs(momentum), 1.0) +
        0.3 * min(abs(pressure), 1.0)
    )

    return max(0.0, min(score, 1.0))


def threshold_for_mode(mode: str) -> float:
    return {
        "SAFE": 0.80,
        "CONSERVATIVE": 0.70,
        "BALANCED": 0.60,
        "AGGRESSIVE": 0.50,
        "EXPANSION": 0.40,
    }.get(mode.upper(), 0.65)


def evaluate_trade(symbol: str, data: dict):
    score = compute_opportunity_score(data)
    threshold = threshold_for_mode(ENGINE_MODE)

    if score < threshold:
        print(f"[R14 BLOCK] {symbol} score={score:.2f}")
        return False, score

    print(f"[R14 PASS] {symbol} score={score:.2f}")
    return True, score
'''
    return injection + "\n" + content


def inject_into_loop(content: str) -> str:
    """
    Insert evaluation right after candles are fetched
    """

    target = "Fetched candles for"

    lines = content.splitlines()
    new_lines = []

    inserted = False

    for i, line in enumerate(lines):
        new_lines.append(line)

        if target in line and not inserted:
            new_lines.append(
                "        allow_trade, score = evaluate_trade(symbol, data if 'data' in locals() else {})"
            )
            new_lines.append("        if not allow_trade:")
            new_lines.append("            continue")
            inserted = True

    if not inserted:
        print("[WARN] Could not auto-hook profitability engine. Manual check may be needed.")

    return "\n".join(new_lines)


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError("Input file missing")

    content = INPUT_FILE.read_text(encoding="utf-8")

    content = inject_engine(content)
    content = inject_into_loop(content)

    OUTPUT_FILE.write_text(content, encoding="utf-8")

    print("[SUCCESS] R14B PROFITABILITY FILE CREATED")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()