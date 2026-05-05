from pathlib import Path

INPUT_FILE = Path("scripts/css_live_dashboard.py")
OUTPUT_FILE = Path("scripts/css_live_dashboard_R16B_DRAWDOWN_BREAKER_FIXED.py")


def normalize_future(text: str) -> str:
    lines = text.splitlines()
    future = [l for l in lines if l.startswith("from __future__")]
    rest = [l for l in lines if not l.startswith("from __future__")]
    return "\n".join(future + [""] + rest)


def inject_drawdown_gate(text: str) -> str:
    lines = text.splitlines()
    out = []
    inserted = False

    for i, line in enumerate(lines):
        out.append(line)

        if not inserted and line.strip().startswith("def can_open_position("):
            # detect indentation level of function body
            next_line = lines[i + 1]
            base_indent = next_line[:len(next_line) - len(next_line.lstrip())]

            block = [
                base_indent + "# =========================",
                base_indent + "# R16B DRAWDOWN CIRCUIT BREAKER",
                base_indent + "# =========================",
                base_indent + "try:",
                base_indent + "    current_dd = float(getattr(pnl_tracker, 'max_drawdown', 0.0))",
                base_indent + "    if current_dd >= 0.05:",
                base_indent + "        print(f\"[R16B BLOCK] Drawdown limit reached: {current_dd:.2%}\")",
                base_indent + "        return False, 'DRAWDOWN_LIMIT'",
                base_indent + "except Exception:",
                base_indent + "    pass",
                ""
            ]

            out.extend(block)
            inserted = True

    if not inserted:
        raise RuntimeError("Failed to inject drawdown breaker")

    return "\n".join(out)


def main():
    text = INPUT_FILE.read_text(encoding="utf-8")

    text = inject_drawdown_gate(text)
    text = normalize_future(text)

    OUTPUT_FILE.write_text(text, encoding="utf-8")

    print("[SUCCESS] R16B FIXED DRAWdown BREAKER CREATED")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()