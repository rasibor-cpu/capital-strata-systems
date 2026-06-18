import time


def on_tick(tick):
    print(f"{tick.ts_utc} | {tick.symbol} | {tick.price} | {tick.size}")


def main() -> None:
    from live_data.alpaca_adapter import AlpacaLiveDataAdapter

    adapter = AlpacaLiveDataAdapter.from_env()
    adapter.set_tick_handler(on_tick)

    # Use a very liquid symbol (IEX stream on free tier)
    adapter.start_streaming_trades(["AAPL"])

    time.sleep(20)

    adapter.stop_streaming()
    print("STREAM TEST COMPLETE")


if __name__ == "__main__":
    main()
