from pathlib import Path

INPUT_FILE = Path("scripts/css_live_dashboard_R13F_BOUNDARY_ORDER_SAFE.py")
OUTPUT_FILE = Path("scripts/css_live_dashboard_R14_PROFITABILITY.py")


def inject_profitability_engine(content: str) -> str:
    if "def compute_opportunity_score" in content:
        return content

    injection = '''
# === R14 PROFITABILITY ENGINE ===

def compute_opportunity_score(data: dict) -> float:
    """
    Score in [0,1] combining VWAP edge, momentum, pressure.
    Expects keys (if present): price, vwap, momentum, pressure_score
    """
    price = float(data.get("price", 0.0) or 0.0)
    vwap = float(data.get("vwap", price or 1.0) or 1.0)

    # VWAP edge (distance from VWAP, normalized)
    if vwap != 0:
        vwap_edge = abs(price - vwap) / max(vwap, 1e-9)
    else:
        vwap_edge = 0.0

    momentum = float(data.get("momentum", 0.0) or 0.0)
    pressure = float(data.get("pressure_score", 0.0) or 0.0)

    # Normalize components to [0,1] heuristically
    vwap_component = min(vwap_edge * 5.0, 1.0)      # amplify small edges
    momentum_component = min(abs(momentum), 1.0)
    pressure_component = min(abs(pressure), 1.0)

    score = (
        0.4 * vwap_component +
        0.3 * momentum_component +
        0.3 * pressure_component
    )

    return max(0.0, min(score, 1.0))


def get_threshold_for_mode(mode: str) -> float:
    mode = str(mode).upper()
    return {
        "SAFE": 0.80,
        "CONSERVATIVE": 0.70,
        "BALANCED": 0.60,
        "AGGRESSIVE": 0.50,
        "EXPANSION": 0.40,
    }.get(mode, 0.65)


def get_position_size(score: float) -> float:
    """
    Position size fraction of available capital.
    """
    if score >= 0.80:
        return 0.10
    elif score >= 0.70:
        return 0.07
    elif score >= 0.60:
        return 0.05
    elif score >= 0.50:
        return 0.03
    return 0.0


def should_take_trade(symbol: str, data: dict) -> tuple[bool, float, float]:
    """
    Returns: (allow, score, size_fraction)
    """
    score = compute_opportunity_score(data)
    threshold = get_threshold_for_mode(ENGINE_MODE)

    if score < threshold:
        return False, score, 0.0

    size = get_position_size(score)
    return size > 0.0, score, size
'''
    return injection + "\n" + content


def hook_into_trade_flow(content: str) -> str:
    """
    Insert profitability gate before trade prints.
    We gate on common print anchors.
    """

    anchors = [
        '[CRYPTO PAPER OPENED]',
        '[FX PAPER OPENED]',
        '[OPTIONS PAPER OPENED]',
        '[FUTURES PAPER OPENED]',
    ]

    injected = False
    for anchor in anchors:
        if anchor in content:
            content = content.replace(
                anchor,
                f'''# R14 PROFITABILITY GATE
allow_trade, score, size = should_take_trade(symbol, data if 'data' in locals() else {{}})
if not allow_trade:
    print(f"[R14 BLOCK] {{symbol}} score={{score:.2f}} below threshold")
    continue
print(f"[R14 PASS] {{symbol}} score={{score:.2f}} size={{size:.2f}}")

{anchor}''',
                1
            )
            injected = True

    if not injected:
        print("[WARN] No trade anchors replaced. Manual inspection may be required.")

    return content


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Missing input file: {INPUT_FILE}")

    content = INPUT_FILE.read_text(encoding="utf-8")

    content = inject_profitability_engine(content)
    content = hook_into_trade_flow(content)

    OUTPUT_FILE.write_text(content, encoding="utf-8")

    print("[SUCCESS] R14 PROFITABILITY FILE CREATED")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()