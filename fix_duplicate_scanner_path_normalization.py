from pathlib import Path

TARGET_FILE = Path(
    r"governance/scanners/duplicate_symbol_scanner.py"
)

print("[CSS GOVERNANCE] Path normalization fix builder starting...")

if not TARGET_FILE.exists():
    print(f"[ERROR] Target file not found: {TARGET_FILE}")
    raise SystemExit(1)

original = TARGET_FILE.read_text(encoding="utf-8")

updated = original

# =========================================================
# Inject normalize_path helper if missing
# =========================================================

helper_block = '''
def normalize_path(path_str: str) -> str:
    """
    Normalize all paths into governance-safe POSIX form.
    Prevents false duplicate mismatches caused by slash direction.
    """
    return str(Path(path_str).as_posix()).lower()
'''

if "def normalize_path(" not in updated:

    insertion_anchor = "from pathlib import Path"

    updated = updated.replace(
        insertion_anchor,
        insertion_anchor + "\n" + helper_block
    )

# =========================================================
# Replace direct canonical path comparisons
# =========================================================

updated = updated.replace(
    "canonical_path == file_path",
    "normalize_path(canonical_path) == normalize_path(file_path)"
)

updated = updated.replace(
    "canonical_path != file_path",
    "normalize_path(canonical_path) != normalize_path(file_path)"
)

# =========================================================
# Replace raw path storage with normalized paths
# =========================================================

updated = updated.replace(
    '"file": str(file_path)',
    '"file": normalize_path(str(file_path))'
)

# =========================================================
# Save updated scanner
# =========================================================

TARGET_FILE.write_text(updated, encoding="utf-8")

print("[SUCCESS] duplicate_symbol_scanner path normalization applied.")
print(f"[UPDATED] {TARGET_FILE}")