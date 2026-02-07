import time
from live_data.alpaca_adapter import AlpacaLiveDataAdapter

def on_quote(q):
    # Quote has: symbol, bid_price, ask_price, bid_size, ask_size, timestamp
    print(f"{q.timestamp} | {q.symbol} | bid {q.bid_price} x{q.bid_size} | ask {q.ask_price} x{q.ask_size}")

adapter = AlpacaLiveDataAdapter.from_env()
adapter.set_quote_handler(on_quote)

adapter.start_streaming_quotes(["SPY", "QQQ"])

time.sleep(20)

adapter.stop_streaming()
print("QUOTE STREAM TEST COMPLETE")
