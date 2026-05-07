from pathlib import Path
from datetime import datetime
import re

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "scripts" / "css_live_dashboard.py"

if not TARGET.exists():
    raise FileNotFoundError(f"Dashboard file not found: {TARGET}")

text = TARGET.read_text(encoding="utf-8")

backup = TARGET.with_name(
    f"css_live_dashboard_PRE_R1_REAL_BALANCE_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
)
backup.write_text(text, encoding="utf-8")

new_class = r'''class CapitalDeploymentGovernor:
    """
    PCNRASS R1 UPGRADE:
    Dynamic capital source:
    - PAPER mode keeps controlled simulated test capital.
    - LIVE mode attempts broker-fetched account balance through RealBalanceEngine.
    - Fail-closed: if real balance fetch fails, available live capital becomes 0.0.
    """

    def __init__(self) -> None:
        self.paper_mode = True
        self.simulated_capital_pool = 200.00
        self.max_capital_per_trade = 25.00
        self.max_broker_test_positions = 5
        self.active_test_allocations: dict[str, float] = {}
        self.real_balance = 0.0
        self.real_equity = 0.0
        self.balance_source = "SIMULATED"

    def _get_adapter(self):
        try:
            if str(SELECTED_BROKER).upper() == "OANDA":
                return oanda
            if str(SELECTED_BROKER).upper() == "COINBASE":
                return coinbase
        except Exception:
            return None
        return None

    def refresh_real_balance(self) -> dict:
        try:
            from backend.app.accounting.real_balance_engine import RealBalanceEngine

            engine = RealBalanceEngine(SELECTED_BROKER, self._get_adapter())
            data = engine.get_balance()

            self.real_balance = float(data.get("balance", 0.0) or 0.0)
            self.real_equity = float(data.get("equity", self.real_balance) or 0.0)
            self.balance_source = str(data.get("source", "UNKNOWN"))

            print(
                f"[REAL BALANCE LOADED] broker={SELECTED_BROKER} "
                f"mode={SELECTED_BROKER_MODE} balance=${self.real_balance:,.2f} "
                f"equity=${self.real_equity:,.2f} source={self.balance_source}"
            )

            return data

        except Exception as e:
            self.real_balance = 0.0
            self.real_equity = 0.0
            self.balance_source = f"REAL_BALANCE_ERROR_{str(e)[:40]}"
            print(f"[REAL BALANCE ERROR] {str(e)[:80]}")
            return {
                "balance": 0.0,
                "equity": 0.0,
                "source": self.balance_source,
            }

    def available_capital(self) -> float:
        allocated = sum(self.active_test_allocations.values())

        if self.paper_mode:
            base_capital = float(self.simulated_capital_pool)
        else:
            base_capital = float(self.real_balance)

        return round(base_capital - allocated, 4)

    def capital_source_label(self) -> str:
        if self.paper_mode:
            return "SIMULATED"
        return self.balance_source or "REAL_BROKER"

    def can_fund_trade(self, position_id: str) -> bool:
        if self.paper_mode:
            return False
        if position_id in self.active_test_allocations:
            return False
        if len(self.active_test_allocations) >= self.max_broker_test_positions:
            return False
        if self.available_capital() < self.max_capital_per_trade:
            return False
        return True

    def allocate_trade(self, position_id: str) -> bool:
        if not self.can_fund_trade(position_id):
            return False
        self.active_test_allocations[position_id] = self.max_capital_per_trade
        return True

    def release_trade(self, position_id: str) -> None:
        if position_id in self.active_test_allocations:
            del self.active_test_allocations[position_id]

    def live_positions_count(self) -> int:
        return len(self.active_test_allocations)

    def funded_amount(self) -> float:
        return round(sum(self.active_test_allocations.values()), 4)

    def set_live_mode(self) -> None:
        self.paper_mode = False
        self.refresh_real_balance()

    def set_paper_mode(self) -> None:
        self.paper_mode = True
        self.balance_source = "SIMULATED"
'''

pattern = re.compile(
    r"class CapitalDeploymentGovernor:\n"
    r".*?"
    r"\n\ncapital_governor = CapitalDeploymentGovernor\(\)",
    re.DOTALL,
)

replacement = new_class + "\n\ncapital_governor = CapitalDeploymentGovernor()"

new_text, count = pattern.subn(replacement, text, count=1)

if count != 1:
    raise RuntimeError("Could not safely replace CapitalDeploymentGovernor block. No file was modified.")

activation = '''
# PCNRASS R1: activate correct capital source after broker/mode selection.
if str(SELECTED_BROKER_MODE).lower() == "live":
    capital_governor.set_live_mode()
else:
    capital_governor.set_paper_mode()
'''

anchor = "capital_governor = CapitalDeploymentGovernor()\n"
if activation.strip() not in new_text:
    new_text = new_text.replace(anchor, anchor + activation + "\n", 1)

TARGET.write_text(new_text, encoding="utf-8")

print("[PCNRASS BUILDER COMPLETE]")
print(f"Target updated: {TARGET}")
print(f"Backup created: {backup}")
print("Next: python -m py_compile scripts\\css_live_dashboard.py")