from pathlib import Path

INPUT_FILE = Path("scripts/css_live_dashboard.py")   # canonical
OUTPUT_FILE = Path("scripts/css_live_dashboard_R16A_EXIT_FIX.py")


def normalize_future(text: str) -> str:
    lines = text.splitlines()
    future = [l for l in lines if l.startswith("from __future__")]
    rest = [l for l in lines if not l.startswith("from __future__")]
    return "\n".join(future + [""] + rest)


def insert_guard(text: str) -> str:
    """
    Insert:
        if pos["forced_exit"]:
            continue

    immediately AFTER R15B block and BEFORE legacy block
    """

    lines = text.splitlines()
    out = []
    inserted = False

    for i, line in enumerate(lines):
        out.append(line)

        # detect end of R15B block by TAKE_PROFIT section
        if (
            not inserted
            and "TIME EXIT" in line.upper()
        ):
            indent = line[:len(line) - len(line.lstrip())]

            out.append(indent + "if pos.get('forced_exit', False):")
            out.append(indent + "    continue  # R16A guard: prevent dual exit execution")

            inserted = True

    if not inserted:
        raise RuntimeError("R15B block not detected — no modification applied")

    return "\n".join(out)


def main():
    text = INPUT_FILE.read_text(encoding="utf-8")

    text = insert_guard(text)
    text = normalize_future(text)

    OUTPUT_FILE.write_text(text, encoding="utf-8")

    print("[SUCCESS] R16A EXIT GUARD FILE CREATED")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()