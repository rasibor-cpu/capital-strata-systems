import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.adapters.coinbase_adapter import CoinbaseAdapter
from backend.adapters.coinbase_execution import CoinbaseExecutionGate, RiskLimits

adapter = CoinbaseAdapter("cdp_api_key (2).json")
gate = CoinbaseExecutionGate(adapter, limits=RiskLimits())

pnl = gate.sync_realized_pnl(product_id="BTC-USDC")
print("Current realized daily PnL (USD):", pnl)