from pathlib import Path

TARGET_FILE = Path(
    r"governance/scanners/duplicate_symbol_scanner.py"
)

print("[CSS GOVERNANCE] Scanner exclusion builder starting...")

if not TARGET_FILE.exists():
    print(f"[ERROR] Missing target: {TARGET_FILE}")
    raise SystemExit(1)

original = TARGET_FILE.read_text(encoding="utf-8")

updated = original

# =========================================================
# EXCLUDED DIRECTORIES
# =========================================================

exclusion_block = '''
EXCLUDED_DIRECTORIES = [
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
    "old"
]
'''

if "EXCLUDED_DIRECTORIES =" not in updated:

    anchor = "from pathlib import Path"

    updated = updated.replace(
        anchor,
        anchor + "\n\n" + exclusion_block
    )

# =========================================================
# Inject exclusion filtering
# =========================================================

old_loop = "for file_path in project_root.rglob(\"*.py\"):"

new_loop = '''
for file_path in project_root.rglob("*.py"):

        normalized = str(file_path).replace("\\\\", "/")

        if any(
            excluded.lower() in normalized.lower()
            for excluded in EXCLUDED_DIRECTORIES
        ):
            continue
'''

updated = updated.replace(old_loop, new_loop)

# =========================================================
# Save
# =========================================================

TARGET_FILE.write_text(updated, encoding="utf-8")

print("[SUCCESS] Scanner exclusions applied.")
print(f"[UPDATED] {TARGET_FILE}")