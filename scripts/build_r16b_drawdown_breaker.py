from pathlib import Path

INPUT_FILE = Path("scripts/css_live_dashboard.py")
OUTPUT_FILE = Path("scripts/css_live_dashboard_R16B_DRAWDOWN_BREAKER.py")


def normalize_future(text: str) -> str:
    lines = text.splitlines()
    future = [l for l in lines if l.startswith("from __future__")]
    rest = [l for l in lines if not l.startswith("from __future__")]
    return "\n".join(future + [""] + rest)


def inject_drawdown_gate(text: str) -> str:
    target = "def can_open_position("

    if target not in text:
        raise RuntimeError("can_open_position not found")

    insert_block = '''
    # =========================
    # R16B DRAWDOWN CIRCUIT BREAKER
    # =========================
    try:
        current_dd = float(getattr(pnl_tracker, "max_drawdown", 0.0))
        if current_dd >= 0.05:
            print(f"[R16B BLOCK] Drawdown limit reached: {current_dd:.2%}")
            return False, "DRAWDOWN_LIMIT"
    except Exception:
        pass
'''

    lines = text.splitlines()
    out = []
    inserted = False

    for line in lines:
        out.append(line)

        if (not inserted) and target in line:
            out.append(insert_block)
            inserted = True

    return "\n".join(out)


def main():
    text = INPUT_FILE.read_text(encoding="utf-8")

    text = inject_drawdown_gate(text)
    text = normalize_future(text)

    OUTPUT_FILE.write_text(text, encoding="utf-8")

    print("[SUCCESS] R16B DRAWDOWN BREAKER CREATED")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()