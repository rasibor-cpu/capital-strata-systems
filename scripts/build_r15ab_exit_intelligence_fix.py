from pathlib import Path

INPUT_FILE = Path("scripts/css_live_dashboard_R14G_CALIBRATED.py")
OUTPUT_FILE = Path("scripts/css_live_dashboard_R15AB_EXIT_INTELLIGENCE_FIXED.py")


def normalize_future(text: str) -> str:
    lines = text.splitlines()
    future = [l for l in lines if l.startswith("from __future__")]
    rest = [l for l in lines if not l.startswith("from __future__")]
    return "\n".join(future + [""] + rest)


def inject_exit_engine(text: str) -> str:
    if "def evaluate_exit_signal" in text:
        return text

    block = '''
# === R15A EXIT INTELLIGENCE ENGINE ===

def evaluate_exit_signal(position: dict) -> str:
    entry = float(position.get("entry_price", 0.0))
    current = float(position.get("current_price", entry))

    if entry == 0:
        return "HOLD"

    pnl_pct = (current - entry) / entry

    if pnl_pct >= 0.015:
        return "TAKE_PROFIT"

    if pnl_pct <= -0.010:
        return "STOP_LOSS"

    if pnl_pct >= 0.010:
        return "RUNNER"

    return "HOLD"
'''
    return block + "\n" + text


def inject_into_position_loop(text: str) -> str:
    lines = text.splitlines()
    out = []
    inserted = False

    for line in lines:
        out.append(line)

        if "pnl_observer.add_position" in line and not inserted:
            indent = line[:len(line) - len(line.lstrip())]

            out.append(indent + "exit_signal = evaluate_exit_signal(position)")
            out.append(indent + 'print(f"[R15A EXIT] {symbol} signal={exit_signal}")')

            inserted = True

    return "\n".join(out)


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(INPUT_FILE)

    text = INPUT_FILE.read_text(encoding="utf-8")

    text = inject_exit_engine(text)
    text = inject_into_position_loop(text)
    text = normalize_future(text)

    OUTPUT_FILE.write_text(text, encoding="utf-8")

    print("[SUCCESS] R15AB FIXED EXIT INTELLIGENCE FILE CREATED")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()