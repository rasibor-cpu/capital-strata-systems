import sys
import os

# Ensure repo root is on Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.adapters.coinbase_adapter import CoinbaseAdapter

adapter = CoinbaseAdapter("cdp_api_key (2).json")

balances = adapter.get_balance_summary()
print("Balances:", balances)