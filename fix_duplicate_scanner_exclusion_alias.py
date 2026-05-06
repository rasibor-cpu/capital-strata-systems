from pathlib import Path

TARGET_FILE = Path(
    r"governance/scanners/duplicate_symbol_scanner.py"
)

print("[CSS GOVERNANCE] Exclusion alias fix builder starting...")

if not TARGET_FILE.exists():
    print(f"[ERROR] Missing target: {TARGET_FILE}")
    raise SystemExit(1)

original = TARGET_FILE.read_text(encoding="utf-8")

updated = original

# =========================================================
# Add compatibility alias
# =========================================================

if "EXCLUDED_DIRS = EXCLUDED_DIRECTORIES" not in updated:

    target = "EXCLUDED_DIRECTORIES = ["

    replacement = '''
EXCLUDED_DIRECTORIES = [
'''

    updated = updated.replace(target, replacement)

    insertion_point = updated.find("]", updated.find("EXCLUDED_DIRECTORIES = ["))

    if insertion_point != -1:
        insertion_point += 1

        updated = (
            updated[:insertion_point]
            + "\n\nEXCLUDED_DIRS = EXCLUDED_DIRECTORIES\n"
            + updated[insertion_point:]
        )

# =========================================================
# Save
# =========================================================

TARGET_FILE.write_text(updated, encoding="utf-8")

print("[SUCCESS] Exclusion alias compatibility applied.")
print(f"[UPDATED] {TARGET_FILE}")