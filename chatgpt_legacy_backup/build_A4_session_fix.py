from pathlib import Path

src = Path("backend/intelligence/trade_decision_orchestrator.py")
dst = Path("backend/intelligence/trade_decision_orchestrator_A4_SESSION_FIX.py")

text = src.read_text(encoding="utf-8")

old = '''        gate_decision = self.trade_gate.approve_trade(
            candidate=gate_candidate,
            session=session or {"created": 0, "role": "ADMIN"},
            engine_mode=engine_mode,
            portfolio_state=portfolio_state,
        )
'''

new = '''        if session is None:
            return self._reject(asset, "NO_ACTIVE_SESSION")

        gate_decision = self.trade_gate.approve_trade(
            candidate=gate_candidate,
            session=session,
            engine_mode=engine_mode,
            portfolio_state=portfolio_state,
        )
'''

if old not in text:
    raise SystemExit("ERROR: Target block not found. No file created.")

updated = text.replace(old, new, 1)
dst.write_text(updated, encoding="utf-8")

print(f"Created: {dst}")
print("PCNRASS: only session fallback block replaced; all other content preserved.")