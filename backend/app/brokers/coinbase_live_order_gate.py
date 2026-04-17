"""
Capital Strata Systems (CSS)
Coinbase Live Order Readiness Gate

Purpose
-------
Final safety gate before any real Coinbase live order is allowed.

This module does NOT place orders.
It only validates whether Coinbase live order execution is permitted.

Core protections
----------------
1. Global broker execution must be armed.
2. Selected broker must be COINBASE.
3. Broker mode must be live.
4. COINBASE_ENABLE_LIVE_ORDERS must be true.
5. Engine mode must not be SAFE.
6. Symbol must be an approved crypto symbol.
7. Order size must be within hard test limits.
8. Coinbase adapter must be initialized and live-authenticated.
9. Optional manual confirmation phrase can be required.

Default behavior
----------------
Fail closed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Iterable, Optional


@dataclass(frozen=True)
class CoinbaseLiveOrderGateResult:
    allowed: bool
    reason: str
    symbol: str = ""
    size_usd: float = 0.0
    mode: str = ""
    selected_broker: str = ""


class CoinbaseLiveOrderGate:
    """
    Fail-closed live-order safety gate for Coinbase.

    This class is intentionally independent of the dashboard so it can later be
    reused by execution engines, broker runners, and audit-governed live trading.
    """

    DEFAULT_MAX_ORDER_USD = 1.00

    def __init__(
        self,
        *,
        approved_symbols: Optional[Iterable[str]] = None,
        max_order_usd: Optional[float] = None,
        require_manual_phrase: bool = False,
        manual_phrase: str = "ALLOW_COINBASE_LIVE_ORDER",
    ) -> None:
        self.approved_symbols = set(approved_symbols or [])
        self.max_order_usd = float(
            max_order_usd
            if max_order_usd is not None
            else os.getenv("COINBASE_MAX_LIVE_ORDER_USD", self.DEFAULT_MAX_ORDER_USD)
        )
        self.require_manual_phrase = require_manual_phrase
        self.manual_phrase = manual_phrase

    @staticmethod
    def live_orders_flag_enabled() -> bool:
        return (os.getenv("COINBASE_ENABLE_LIVE_ORDERS") or "").strip().lower() in {
            "1",
            "true",
            "yes",
            "y",
            "on",
        }

    def evaluate(
        self,
        *,
        broker_execution_armed: bool,
        selected_broker: str,
        broker_mode: str,
        engine_mode: str,
        symbol: str,
        size_usd: float,
        coinbase_adapter: Any,
        manual_confirmation: str = "",
    ) -> CoinbaseLiveOrderGateResult:
        selected = (selected_broker or "").strip().upper()
        mode = (broker_mode or "").strip().lower()
        engine = (engine_mode or "").strip().upper()
        symbol_clean = (symbol or "").strip().upper()

        try:
            size = float(size_usd)
        except Exception:
            size = 0.0

        if not broker_execution_armed:
            return CoinbaseLiveOrderGateResult(
                False,
                "BROKER_EXECUTION_NOT_ARMED",
                symbol_clean,
                size,
                mode,
                selected,
            )

        if selected != "COINBASE":
            return CoinbaseLiveOrderGateResult(
                False,
                f"SELECTED_BROKER_NOT_COINBASE_{selected}",
                symbol_clean,
                size,
                mode,
                selected,
            )

        if mode != "live":
            return CoinbaseLiveOrderGateResult(
                False,
                f"COINBASE_NOT_LIVE_MODE_{mode}",
                symbol_clean,
                size,
                mode,
                selected,
            )

        if not self.live_orders_flag_enabled():
            return CoinbaseLiveOrderGateResult(
                False,
                "COINBASE_LIVE_ORDER_FLAG_OFF",
                symbol_clean,
                size,
                mode,
                selected,
            )

        if engine == "SAFE":
            return CoinbaseLiveOrderGateResult(
                False,
                "ENGINE_SAFE_MODE_BLOCKS_LIVE_ORDERS",
                symbol_clean,
                size,
                mode,
                selected,
            )

        if not symbol_clean:
            return CoinbaseLiveOrderGateResult(
                False,
                "MISSING_SYMBOL",
                symbol_clean,
                size,
                mode,
                selected,
            )

        if self.approved_symbols and symbol_clean not in self.approved_symbols:
            return CoinbaseLiveOrderGateResult(
                False,
                f"SYMBOL_NOT_APPROVED_{symbol_clean}",
                symbol_clean,
                size,
                mode,
                selected,
            )

        if size <= 0:
            return CoinbaseLiveOrderGateResult(
                False,
                "INVALID_ORDER_SIZE",
                symbol_clean,
                size,
                mode,
                selected,
            )

        if size > self.max_order_usd:
            return CoinbaseLiveOrderGateResult(
                False,
                f"ORDER_SIZE_EXCEEDS_LIMIT_{self.max_order_usd}",
                symbol_clean,
                size,
                mode,
                selected,
            )

        if coinbase_adapter is None:
            return CoinbaseLiveOrderGateResult(
                False,
                "COINBASE_ADAPTER_NOT_INITIALIZED",
                symbol_clean,
                size,
                mode,
                selected,
            )

        if not hasattr(coinbase_adapter, "ping_live_auth"):
            return CoinbaseLiveOrderGateResult(
                False,
                "COINBASE_ADAPTER_MISSING_PING_LIVE_AUTH",
                symbol_clean,
                size,
                mode,
                selected,
            )

        try:
            ping = coinbase_adapter.ping_live_auth()
        except Exception as exc:
            return CoinbaseLiveOrderGateResult(
                False,
                f"COINBASE_LIVE_AUTH_FAILED_{str(exc)[:60]}",
                symbol_clean,
                size,
                mode,
                selected,
            )

        if not isinstance(ping, dict) or not ping.get("ok"):
            return CoinbaseLiveOrderGateResult(
                False,
                "COINBASE_LIVE_AUTH_NOT_OK",
                symbol_clean,
                size,
                mode,
                selected,
            )

        if self.require_manual_phrase and manual_confirmation != self.manual_phrase:
            return CoinbaseLiveOrderGateResult(
                False,
                "MANUAL_CONFIRMATION_REQUIRED",
                symbol_clean,
                size,
                mode,
                selected,
            )

        return CoinbaseLiveOrderGateResult(
            True,
            "COINBASE_LIVE_ORDER_GATE_PASSED",
            symbol_clean,
            size,
            mode,
            selected,
        )