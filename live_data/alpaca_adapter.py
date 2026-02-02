"""
alpaca_adapter.py — Live market data adapter (DATA-ONLY)

Scope (LOCKED):
- Alpaca PAPER trading environment
- Market data ingestion ONLY (no orders, no execution)
- Safe for research, prompts, and future extension

This module:
- Validates environment variables
- Provides a clean adapter interface
- Stubs streaming / REST hooks without side effects
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Iterable, Optional, Dict, Any, List


# -------------------------
# Configuration & Contracts
# -------------------------

ALPACA_API_KEY_ENV = "ALPACA_API_KEY_ID"
ALPACA_SECRET_KEY_ENV = "ALPACA_SECRET_KEY"
ALPACA_BASE_URL_ENV = "ALPACA_BASE_URL"


@dataclass
class AlpacaConfig:
    api_key_id: str
    secret_key: str
    base_url: str = "https://paper-api.alpaca.markets"


@dataclass
class MarketTick:
    symbol: str
    price: float
    size: Optional[int]
    ts_utc: str


# -------------------------
# Adapter
# -------------------------

class AlpacaLiveDataAdapter:
    """
    Data-only adapter for Alpaca live feeds.

    Hard guarantees:
    - NO order placement
    - NO account mutation
    - NO execution
    """

    def __init__(self, config: AlpacaConfig):
        self.config = config
        self._validate_config()

    @classmethod
    def from_env(cls) -> "AlpacaLiveDataAdapter":
        """
        Create adapter from environment variables only.
        """
        api_key = os.getenv(ALPACA_API_KEY_ENV)
        secret_key = os.getenv(ALPACA_SECRET_KEY_ENV)
        base_url = os.getenv(ALPACA_BASE_URL_ENV, "https://paper-api.alpaca.markets")

        if not api_key or not secret_key:
            raise RuntimeError(
                "Missing Alpaca credentials. "
                "Set ALPACA_API_KEY_ID and ALPACA_SECRET_KEY as environment variables."
            )

        cfg = AlpacaConfig(
            api_key_id=api_key,
            secret_key=secret_key,
            base_url=base_url,
        )
        return cls(cfg)

    def _validate_config(self) -> None:
        if not self.config.api_key_id:
            raise ValueError("API key is empty")
        if not self.config.secret_key:
            raise ValueError("Secret key is empty")
        if not self.config.base_url.startswith("http"):
            raise ValueError("Base URL must be http(s)")

    # -------------------------
    # Public API (SAFE)
    # -------------------------

    def connect(self) -> None:
        """
        Placeholder for websocket connection setup.

        NOTE:
        - This does NOT open a socket yet.
        - Wiring happens in a later instruction.
        """
        return None

    def disconnect(self) -> None:
        """
        Placeholder for clean shutdown.
        """
        return None

    def stream_ticks(self, symbols: Iterable[str]) -> Iterable[MarketTick]:
        """
        Generator stub for streaming market ticks.

        SAFE DEFAULT:
        - Yields nothing.
        - Never blocks indefinitely.
        """
        for _ in []:
            yield _  # pragma: no cover

    def fetch_latest_price(self, symbol: str) -> Optional[float]:
        """
        REST fallback stub.

        SAFE DEFAULT:
        - Returns None (no data)
        """
        return None

    # -------------------------
    # Health / Diagnostics
    # -------------------------

    def heartbeat(self) -> Dict[str, Any]:
        """
        Lightweight health check (no network calls).
        """
        return {
            "adapter": "alpaca",
            "mode": "paper",
            "data_only": True,
            "base_url": self.config.base_url,
            "ok": True,
            "ts": time.time(),
        }
