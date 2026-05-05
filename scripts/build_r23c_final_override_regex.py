from pathlib import Path
import re

SRC = Path("scripts/css_live_dashboard_R23B_FX_OVERRIDE_REGEX.py")
DST = Path("scripts/css_live_dashboard_R23C_FINAL_OVERRIDE_REGEX.py")

code = SRC.read_text(encoding="utf-8")

pattern = re.compile(
    r'(?P<indent>^[ \t]*)print\(f"\[\{asset_class\}\] PAPER OPENED.*?\n',
    re.MULTILINE,
)

match = pattern.search(code)
if not match:
    raise SystemExit("[FAILED] final PAPER OPENED print line not found")

indent = match.group("indent")
line = match.group(0)

inject = f'''{indent}# ===== R23C FINAL FX OVERRIDE =====
{indent}try:
{indent}    current_counts = mtm_engine.count_open_positions_by_asset()
{indent}    if asset_class == "FX" and current_counts.get("FX", 0) == 0:
{indent}        print("[R23C FINAL] Forcing FX execution bypassing final filters")
{indent}        force_execute = True
{indent}    else:
{indent}        force_execute = False
{indent}except Exception:
{indent}    force_execute = False
{indent}# ==================================
'''

code = code[:match.start()] + inject + line + code[match.end():]

code = code.replace(
    "if not allowed_to_open:",
    "if not allowed_to_open and not force_execute:",
    1
)

DST.write_text(code, encoding="utf-8")
print("R23C REGEX BUILT:", DST)