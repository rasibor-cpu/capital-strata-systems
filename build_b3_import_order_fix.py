from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "scripts" / "css_live_dashboard.py"

text = TARGET.read_text(encoding="utf-8")

backup = TARGET.with_name(
    f"css_live_dashboard_PRE_B3_IMPORT_ORDER_FIX_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
)
backup.write_text(text, encoding="utf-8")

bad_import = "from backend.governance.css_unified_trade_gate import CSSUnifiedTradeGate\n"
text = text.replace(bad_import, "")

anchor = '''if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")
'''

replacement = '''if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.governance.css_unified_trade_gate import CSSUnifiedTradeGate

load_dotenv(PROJECT_ROOT / ".env")
'''

if anchor not in text:
    raise RuntimeError("PROJECT_ROOT/sys.path anchor not found. No file modified.")

text = text.replace(anchor, replacement, 1)

TARGET.write_text(text, encoding="utf-8")

print("[PCNRASS B3 IMPORT ORDER FIX COMPLETE]")
print(f"Backup created: {backup}")
print("Next: python -m py_compile scripts\\css_live_dashboard.py")