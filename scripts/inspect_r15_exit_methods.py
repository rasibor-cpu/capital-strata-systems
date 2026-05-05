from pathlib import Path

TARGET = Path("scripts/css_live_dashboard_R15AB_EXIT_INTELLIGENCE_FIXED.py")
OUT = Path("artifacts/r15_exit_method_inspection.txt")

KEYWORDS = [
    "close_position",
    "release_trade",
    "remove_position",
    "exit_position",
    "forced_exit",
    "record_forced_exit",
    "mtm_engine",
    "capital_governor",
    "pnl_observer",
]

text = TARGET.read_text(encoding="utf-8", errors="ignore").splitlines()

matches = []
for i, line in enumerate(text, start=1):
    if any(k.lower() in line.lower() for k in KEYWORDS):
        start = max(1, i - 5)
        end = min(len(text), i + 8)
        matches.append(f"\n--- MATCH AROUND LINE {i}: {line.strip()} ---")
        for n in range(start, end + 1):
            matches.append(f"{n}: {text[n-1]}")

OUT.parent.mkdir(exist_ok=True)
OUT.write_text("\n".join(matches), encoding="utf-8")

print("[SUCCESS] R15 exit method inspection complete")
print(f"Output: {OUT}")