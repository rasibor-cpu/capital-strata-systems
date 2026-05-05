from pathlib import Path
import re

SRC = Path("scripts/css_live_dashboard_R23_ADAPTIVE_THRESHOLD.py")
DST = Path("scripts/css_live_dashboard_R23B_FX_OVERRIDE_REGEX.py")

code = SRC.read_text(encoding="utf-8")

pattern = re.compile(
    r"(?P<call>^[ \t]*allowed_to_open,\s*open_reason\s*=\s*can_open_position\(\s*\n"
    r"(?:^[ \t]+.*\n)*?"
    r"^[ \t]*\)\s*\n)",
    re.MULTILINE,
)

match = pattern.search(code)
if not match:
    raise SystemExit("[FAILED] can_open_position call block not found")

call_block = match.group("call")
indent = re.match(r"^[ \t]*", call_block).group(0)

inject = f'''{call_block}
{indent}# ===== R23B FX OVERRIDE REGEX =====
{indent}try:
{indent}    if asset_class == "FX":
{indent}        current_counts = mtm_engine.count_open_positions_by_asset()
{indent}        if current_counts.get("FX", 0) == 0:
{indent}            allowed_to_open = True
{indent}            open_reason = "R23B_FX_DIVERSIFICATION_OVERRIDE"
{indent}            print(f"[R23B OVERRIDE] FX slot forced for {{symbol}}")
{indent}except Exception as e:
{indent}    print(f"[R23B WARN] FX override skipped: {{str(e)[:60]}}")
{indent}# ==================================
'''

code = code[:match.start()] + inject + code[match.end():]

DST.write_text(code, encoding="utf-8")
print("R23B REGEX BUILT:", DST)