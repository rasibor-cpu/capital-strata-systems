import os
import time
import threading


def main():
    from alpaca.data.live import CryptoDataStream

    api_key = os.environ["ALPACA_API_KEY_ID"]
    secret_key = os.environ["ALPACA_SECRET_KEY"]

    stream = CryptoDataStream(api_key, secret_key)

    async def on_trade(t):
        # t typically has: symbol, price, size, timestamp
        symbol = getattr(t, "symbol", None) or getattr(t, "S", "")
        price = getattr(t, "price", None) or getattr(t, "p", None)
        size = getattr(t, "size", None) or getattr(t, "s", None)
        ts = getattr(t, "timestamp", None) or getattr(t, "t", None)
        print(f"{ts} | {symbol} | {price} | {size}")

    # Crypto symbols use the slash format on Alpaca
    stream.subscribe_trades(on_trade, "BTC/USD", "ETH/USD")

    th = threading.Thread(target=stream.run, daemon=True)
    th.start()

    time.sleep(20)

    stream.stop()
    th.join(timeout=5)
    print("CRYPTO STREAM TEST COMPLETE")

if __name__ == "__main__":
    main()
