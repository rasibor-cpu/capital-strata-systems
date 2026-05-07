from pathlib import Path

SOURCE = Path(r"scripts/css_live_dashboard.py")
TARGET = Path(r"scripts/css_live_dashboard_R18C_CAPITAL_FINAL.py")

code = SOURCE.read_text()

capital_block = r'''
# ==================================================
# CAPITAL ALLOCATION ENGINE - R18C
# ==================================================
CAPITAL_TOTAL = 200.0
CAPITAL_MAX_POSITIONS = 10
CAPITAL_PER_TRADE = CAPITAL_TOTAL / CAPITAL_MAX_POSITIONS
capital_deployed = 0.0
capital_available = CAPITAL_TOTAL

def r18c_allocate_capital():
    global capital_deployed, capital_available
    if capital_available >= CAPITAL_PER_TRADE:
        capital_deployed += CAPITAL_PER_TRADE
        capital_available -= CAPITAL_PER_TRADE
        print(f"[CAPITAL] Allocated: ${CAPITAL_PER_TRADE:.2f}")
        return True
    print("[CAPITAL BLOCK] No capital available")
    return False

def r18c_capital_line():
    print(f"[R18C CAPITAL] DEPLOYED=${capital_deployed:.2f} | AVAILABLE=${capital_available:.2f}")
# ==================================================
'''

if "CAPITAL ALLOCATION ENGINE - R18C" not in code:
    marker = "from __future__ import annotations"
    if marker in code:
        code = code.replace(marker, marker + "\n" + capital_block, 1)
    else:
        code = capital_block + "\n" + code

# Hook after confirmed paper-open print lines.
for txt in [
    'print(f"[OPTIONS PAPER OPENED] {',
    'print("[OPTIONS PAPER OPENED]',
    'print(f"[FUTURES PAPER OPENED] {',
    'print("[FUTURES PAPER OPENED]',
]:
    idx = code.find(txt)
    while idx != -1:
        line_end = code.find("\n", idx)
        insert_at = line_end + 1
        indent = code[idx:line_end].split("print")[0]
        hook = indent + "r18c_allocate_capital()\n" + indent + "r18c_capital_line()\n"
        if hook not in code[insert_at:insert_at + 300]:
            code = code[:insert_at] + hook + code[insert_at:]
            idx = code.find(txt, insert_at + len(hook))
        else:
            idx = code.find(txt, insert_at)

TARGET.write_text(code, encoding="utf-8")
print("[SUCCESS] R18C capital final created:", TARGET)