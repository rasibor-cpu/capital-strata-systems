import os
import threading
from typing import Callable, List, Optional

from alpaca.data.live import StockDataStream
from alpaca.data.models import Quote


class AlpacaLiveDataAdapter:
    """
    Data-only Alpaca live data adapter.
    - Quotes + Trades
    - Paper / IEX
    - NO execution
    """

    def __init__(self, api_key: str, secret_key: str, base_url: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = base_url

        self._quote_handler: Optional[Callable[[Quote], None]] = None
        self._stream: Optional[StockDataStream] = None
        self._thread: Optional[threading.Thread] = None

    @classmethod
    def from_env(cls):
        return cls(
            api_key=os.environ["ALPACA_API_KEY_ID"],
            secret_key=os.environ["ALPACA_SECRET_KEY"],
            base_url=os.environ.get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets"),
        )

    # ---------- handlers ----------
    def set_quote_handler(self, fn: Callable[[Quote], None]):
        self._quote_handler = fn

    # ---------- streaming ----------
    def start_streaming_quotes(self, symbols: List[str]):
        if not self._quote_handler:
            raise RuntimeError("Quote handler not set")

        self._stream = StockDataStream(
            self.api_key,
            self.secret_key,
            raw_data=False,
        )

        async def _on_quote(q: Quote):
            self._quote_handler(q)

        for sym in symbols:
            self._stream.subscribe_quotes(_on_quote, sym)

        self._thread = threading.Thread(
            target=self._stream.run, daemon=True
        )
        self._thread.start()

    def stop_streaming(self):
        if self._stream:
            self._stream.stop()
