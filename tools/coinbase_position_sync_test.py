import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.adapters.coinbase_adapter import CoinbaseAdapter
from backend.adapters.coinbase_execution import CoinbaseExecutionGate, RiskLimits

adapter = CoinbaseAdapter("cdp_api_key (2).json")
gate = CoinbaseExecutionGate(adapter, limits=RiskLimits())

count = gate.sync_open_positions()
print("Open positions count (non-fiat, non-stable):", count)