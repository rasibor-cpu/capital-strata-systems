from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "backend" / "intelligence" / "trade_decision_orchestrator.py"

text = TARGET.read_text(encoding="utf-8")

backup = TARGET.with_name(
    f"trade_decision_orchestrator_PRE_B3_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
)
backup.write_text(text, encoding="utf-8")

# --- CHECK if gate already used ---
if "CSSUnifiedTradeGate" not in text:
    text = "from backend.governance.css_unified_trade_gate import CSSUnifiedTradeGate\n\n" + text

# --- ADD GATE INIT ---
if "self.trade_gate" not in text:
    text = text.replace(
        "class TradeDecisionOrchestrator:",
        '''class TradeDecisionOrchestrator:
    def __init__(self, *args, **kwargs):
        self.trade_gate = CSSUnifiedTradeGate()
''',
        1
    )

# --- ENFORCE APPROVAL ---
# Find execution point
anchor = "return trade_decision"

gate_block = '''
        # PCNRASS B3: enforce gate authority
        gate_result = self.trade_gate.approve_trade(
            candidate=trade_decision,
            session=session,
            portfolio_state=portfolio_state,
            engine_mode=engine_mode,
        )

        if not gate_result.approved:
            return {
                "approved": False,
                "reason": gate_result.reason,
                "blocked_by": "CSSUnifiedTradeGate"
            }

'''

if gate_block.strip() not in text:
    text = text.replace(anchor, gate_block + "\n" + anchor, 1)

TARGET.write_text(text, encoding="utf-8")

print("[PCNRASS B3 ORCHESTRATOR BUILDER COMPLETE]")
print(f"Backup created: {backup}")
print("Next: python -m py_compile backend\\intelligence\\trade_decision_orchestrator.py")