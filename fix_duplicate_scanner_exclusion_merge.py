from pathlib import Path
import re

TARGET_FILE = Path(r"governance/scanners/duplicate_symbol_scanner.py")

print("[CSS GOVERNANCE] Exclusion merge fix builder starting...")

if not TARGET_FILE.exists():
    print(f"[ERROR] Missing target: {TARGET_FILE}")
    raise SystemExit(1)

text = TARGET_FILE.read_text(encoding="utf-8")

new_block = '''EXCLUDED_DIRS = {
    "css-gemini",
    "CSS-CLAUDE",
    "CLAUDE_REVIEW_2026_05_01",
    "CLAUDE_REVIEW_2026_05_02",
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "archive",
    "backup",
    "old",
    "out",
    "feeds",
    "data_fx",
}
'''

text = re.sub(
    r"EXCLUDED_DIRS\s*=\s*\{.*?\}\n",
    new_block,
    text,
    flags=re.DOTALL,
)

TARGET_FILE.write_text(text, encoding="utf-8")

print("[SUCCESS] Exclusion sets merged.")
print(f"[UPDATED] {TARGET_FILE}")