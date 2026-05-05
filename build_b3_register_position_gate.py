from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "scripts" / "css_live_dashboard.py"

text = TARGET.read_text(encoding="utf-8")

backup = TARGET.with_name(
    f"css_live_dashboard_PRE_B3_REGISTER_GATE_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
)
backup.write_text(text, encoding="utf-8")

old = '''                    position = mtm_engine.register_position(
'''

new = '''                    # PCNRASS B3: single execution authority checkpoint
                    # All paper/broker test positions must pass this gate before registration.
                    try:
                        trade_candidate = {
                            "symbol": symbol,
                            "asset_class": str(asset_class).lower(),
                            "expected_value": float(signal_score),
                            "cost": 0.0,
                            "probability": float(prob_positive),
                        }

                        gate_decision = trade_gate.approve_trade(
                            candidate=trade_candidate,
                            session={
                                "role": str(SESSION_USER_CTX.get("role", "TRADER")),
                                "created": float(SESSION_USER_CTX.get("session_created", time.time())),
                            },
                            portfolio_state={
                                "crypto": open_counts.get("CRYPTO", 0),
                                "fx": open_counts.get("FX", 0),
                                "futures": open_counts.get("FUTURES", 0),
                                "options": open_counts.get("OPTIONS", 0),
                            },
                            engine_mode=ENGINE_MODE,
                        )

                        if not gate_decision.approved:
                            print(f"[CSS GATE BLOCKED] {symbol} | {gate_decision.reason}")
                            continue

                    except Exception as e:
                        print(f"[CSS GATE ERROR - FAIL CLOSED] {symbol} | {str(e)[:80]}")
                        continue

                    position = mtm_engine.register_position(
'''

if old not in text:
    raise RuntimeError("register_position anchor not found. No file modified.")

text = text.replace(old, new, 1)

# Ensure import and instance exist
if "from backend.governance.css_unified_trade_gate import CSSUnifiedTradeGate" not in text:
    text = text.replace(
        "from dotenv import load_dotenv\n",
        "from dotenv import load_dotenv\nfrom backend.governance.css_unified_trade_gate import CSSUnifiedTradeGate\n",
        1,
    )

if "trade_gate = CSSUnifiedTradeGate()" not in text:
    anchor = "audit_ledger = AuditLedger()\n"
    text = text.replace(anchor, anchor + "trade_gate = CSSUnifiedTradeGate()\n", 1)

TARGET.write_text(text, encoding="utf-8")

print("[PCNRASS B3 REGISTER POSITION GATE COMPLETE]")
print(f"Backup created: {backup}")
print("Next: python -m py_compile scripts\\css_live_dashboard.py")