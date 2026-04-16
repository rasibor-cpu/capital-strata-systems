from backend.broker.coinbase_adapter import CoinbaseAdapter

cb = CoinbaseAdapter(
    paper_mode=False
)

print("Connecting to Coinbase...")

result = cb.ping_live_auth()

print("SUCCESS")
print(result)

acct = cb.get_account()

print("ACCOUNT DATA:")
print(acct)