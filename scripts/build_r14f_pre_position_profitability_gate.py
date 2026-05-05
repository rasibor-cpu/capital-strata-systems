from pathlib import Path

INPUT_FILE = Path("scripts/css_live_dashboard_R13F_BOUNDARY_ORDER_SAFE.py")
OUTPUT_FILE = Path("scripts/css_live_dashboard_R14F_PRE_POSITION_GATE.py")


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
# === R14F PRE-POSITION PROFITABILITY GATE ===
def css_profitability_threshold(mode: str) -> float:
    return {
        "SAFE": 18.0,
        "CONSERVATIVE": 16.0,
        "BALANCED": 14.0,
        "AGGRESSIVE": 12.0,
        "EXPANSION": 10.0,
    }.get(str(mode).upper(), 14.0)


def css_profitability_allows(symbol: str, asset_class: str, sig: float, prob: float) -> tuple[bool, float, float]:
    """
    Uses existing dashboard signal score and probability before creating a position.
    Score remains compatible with current sig scale.
    """
    signal_score = float(sig or 0.0)
    probability = float(prob or 0.0)
    threshold = css_profitability_threshold(ENGINE_MODE)

    composite = signal_score + (probability * 5.0)

    if composite < threshold:
        print(
            f"[R14F BLOCK] {asset_class} {symbol} "
            f"composite={composite:.2f} threshold={threshold:.2f} "
            f"sig={signal_score:.2f} prob={probability:.2f}"
        )
        return False, composite, threshold

    print(
        f"[R14F PASS] {asset_class} {symbol} "
        f"composite={composite:.2f} threshold={threshold:.2f} "
        f"sig={signal_score:.2f} prob={probability:.2f}"
    )
    return True, composite, threshold
'''

    if "# === R14F PRE-POSITION PROFITABILITY GATE ===" not in text:
        text = engine + "\n" + text

    target = '''                    if not gate_ok:
                        last_trade = f"{symbol} UNIFIED_GATE_BLOCKED {gate_reason}"
                        continue

                    position = mtm_engine.register_position('''

    replacement = '''                    if not gate_ok:
                        last_trade = f"{symbol} UNIFIED_GATE_BLOCKED {gate_reason}"
                        continue

                    r14f_ok, r14f_score, r14f_threshold = css_profitability_allows(
                        symbol=symbol,
                        asset_class=asset_class,
                        sig=sig,
                        prob=prob,
                    )

                    if not r14f_ok:
                        last_trade = f"{symbol} R14F_BLOCKED"
                        continue

                    position = mtm_engine.register_position('''

    if target not in text:
        raise RuntimeError("Exact pre-position gate target not found. No output written.")

    text = text.replace(target, replacement, 1)
    text = normalize_future_import(text)

    OUTPUT_FILE.write_text(text, encoding="utf-8")
    print("[SUCCESS] R14F PRE-POSITION GATE FILE CREATED")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()