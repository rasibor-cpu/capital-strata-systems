from pathlib import Path

INPUT_FILE = Path("scripts/css_live_dashboard_R15AB_EXIT_INTELLIGENCE_FIXED.py")
OUTPUT_FILE = Path("scripts/css_live_dashboard_R15B_ENHANCED_EXIT.py")


def normalize_future(text: str) -> str:
    lines = text.splitlines()
    future = [l for l in lines if l.startswith("from __future__")]
    rest = [l for l in lines if not l.startswith("from __future__")]
    return "\n".join(future + [""] + rest)


def inject_exit_profiles(text: str) -> str:
    if "R15B_EXIT_PROFILE" in text:
        return text

    block = '''
# === R15B MODE-AWARE EXIT PROFILE ===

R15B_EXIT_PROFILE = {
    "SAFE":        {"tp": 0.010, "sl": -0.006},
    "CONSERVATIVE":{"tp": 0.012, "sl": -0.008},
    "BALANCED":    {"tp": 0.015, "sl": -0.010},
    "AGGRESSIVE":  {"tp": 0.020, "sl": -0.012},
    "EXPANSION":   {"tp": 0.025, "sl": -0.015},
}


def r15b_profile():
    return R15B_EXIT_PROFILE.get(str(ENGINE_MODE).upper(), R15B_EXIT_PROFILE["BALANCED"])
'''
    return block + "\n" + text


def enhance_exit_block(text: str) -> str:
    target = "# PROFIT DOMINANCE EXIT ENGINE"

    if target not in text:
        raise RuntimeError("Exit engine block not found.")

    enhanced = '''
            # =========================
            # R15B ENHANCED EXIT ENGINE
            # =========================

            profile = r15b_profile()

            # Convert floating PnL to %
            entry_price = float(pos.get("entry_price", 100.0))
            pnl_pct = pos["floating"] / max(entry_price, 1e-6)

            sig = float(pos.get("signal_score", 0.0))
            prob = float(pos.get("prob_positive", 0.0))

            # =========================
            # EARLY WEAK TRADE CUT
            # =========================
            if pnl_pct <= profile["sl"] * 0.7 and sig < 11.5:
                book_position_exit(pos, "FAST_STOP")
                pnl_observer.close_position(observer_symbol, observer_price)

            # =========================
            # STANDARD STOP
            # =========================
            elif pnl_pct <= profile["sl"]:
                book_position_exit(pos, "STOP")
                pnl_observer.close_position(observer_symbol, observer_price)

            # =========================
            # TAKE PROFIT / RUNNER LOGIC
            # =========================
            elif pnl_pct >= profile["tp"]:
                if sig >= 13.5 and prob >= 0.70:
                    # strong trade → let run
                    pos["age_cycles"] = max(0, pos["age_cycles"] - 3)
                    print(f"[R15B RUNNER] {pos['symbol']} strong signal extended")

                elif sig >= 12.5 and prob >= 0.66:
                    # medium trade → slight extension
                    pos["age_cycles"] = max(0, pos["age_cycles"] - 2)
                    print(f"[R15B EXTEND] {pos['symbol']} moderate extension")

                else:
                    # weak profit → take it
                    book_position_exit(pos, "TAKE_PROFIT")
                    pnl_observer.close_position(observer_symbol, observer_price)

            # =========================
            # TIME EXIT (WEAK ONLY)
            # =========================
            elif pos["age_cycles"] >= exit_profile["max_age"]:
                if sig >= 12.0 and prob >= 0.65:
                    pos["age_cycles"] = max(0, pos["age_cycles"] - 2)
                else:
                    book_position_exit(pos, "TIME_EXIT")
                    pnl_observer.close_position(observer_symbol, observer_price)
'''

    # Replace ONLY the original exit block header onward
    return text.replace(
        "# PROFIT DOMINANCE EXIT ENGINE",
        enhanced,
        1
    )


def main():
    text = INPUT_FILE.read_text(encoding="utf-8")

    text = inject_exit_profiles(text)
    text = enhance_exit_block(text)
    text = normalize_future(text)

    OUTPUT_FILE.write_text(text, encoding="utf-8")

    print("[SUCCESS] R15B ENHANCED EXIT FILE CREATED")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()