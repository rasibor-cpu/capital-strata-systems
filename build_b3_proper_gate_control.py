from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "scripts" / "css_live_dashboard.py"

text = TARGET.read_text(encoding="utf-8")

backup = TARGET.with_name(
    f"css_live_dashboard_PRE_B3_PROPER_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
)
backup.write_text(text, encoding="utf-8")

# --- STEP 1: Ensure gate import ---
if "CSSUnifiedTradeGate" not in text:
    text = text.replace(
        "from dotenv import load_dotenv\n",
        "from dotenv import load_dotenv\nfrom backend.governance.css_unified_trade_gate import CSSUnifiedTradeGate\n",
        1,
    )

# --- STEP 2: Ensure gate instance ---
if "trade_gate = CSSUnifiedTradeGate()" not in text:
    anchor = "audit_ledger = AuditLedger()\n"
    text = text.replace(anchor, anchor + "trade_gate = CSSUnifiedTradeGate()\n", 1)

# --- STEP 3: Intercept trade candidates BEFORE execution loop ---
# We hook into where signals/candidates are iterated

anchor = "for symbol, signal in candidates.items():"

gate_block = '''
for symbol, signal in candidates.items():

    # PCNRASS B3 FINAL: enforce gate BEFORE execution
    try:
        candidate = {
            "symbol": symbol,
            "asset_class": str(signal.get("asset_class", "")).lower(),
            "expected_value": float(signal.get("expected_value", 1.0)),
            "cost": float(signal.get("cost", 0.0)),
            "probability": float(signal.get("probability", 0.6)),
        }

        gate_result = trade_gate.approve_trade(
            candidate=candidate,
            session={
                "role": str(SESSION_USER_CTX.get("role", "TRADER")),
                "created": float(SESSION_USER_CTX.get("session_created", time.time())),
            },
            portfolio_state={},
            engine_mode=ENGINE_MODE,
        )

        if not gate_result.approved:
            print(f"[CSS GATE BLOCKED] {symbol} | {gate_result.reason}")
            continue

    except Exception as e:
        print(f"[CSS GATE ERROR - FAIL CLOSED] {symbol} | {str(e)[:80]}")
        continue
'''

if anchor not in text:
    raise RuntimeError("Candidate loop anchor not found. No changes made.")

text = text.replace(anchor, gate_block, 1)

TARGET.write_text(text, encoding="utf-8")

print("[PCNRASS B3 FINAL PROPER CONTROL COMPLETE]")
print(f"Backup created: {backup}")
print("Next: python -m py_compile scripts\\css_live_dashboard.py")