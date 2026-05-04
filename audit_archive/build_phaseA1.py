from pathlib import Path
import re

src = Path("scripts/css_live_dashboard.py")
dst = Path("scripts/css_live_dashboard_PHASEA1.py")

code = src.read_text(encoding="utf-8")

pattern = r"(?P<indent>\s*)raw_candidates\s*=\s*\[(.*?)\]"

match = re.search(pattern, code, re.DOTALL)
if not match:
    raise SystemExit("raw_candidates block not found")

indent = match.group("indent")

new_block = f"""{indent}# ============================================================
{indent}# PHASE A1 - FULL UNIVERSE CANDIDATE GENERATION (PCNRASS SAFE)
{indent}# ============================================================
{indent}raw_candidates = []

{indent}# CRYPTO
{indent}for sym in SYMBOLS:
{indent}    raw_candidates.append(("CRYPTO", sym))

{indent}# FX
{indent}for sym in FX_SYMBOLS:
{indent}    raw_candidates.append(("FX", sym))

{indent}# OPTIONS
{indent}for sym in OPTION_SYMBOLS:
{indent}    raw_candidates.append(("OPTIONS", sym))

{indent}# FUTURES
{indent}for sym in FUTURES_SYMBOLS:
{indent}    raw_candidates.append(("FUTURES", sym))
"""

code = re.sub(pattern, new_block, code, flags=re.DOTALL)

dst.write_text(code, encoding="utf-8")

print("Created:", dst)