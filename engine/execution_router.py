"""
Execution Router – Capability-Aware, Fail-Closed (Repo-Proof Imports)
---------------------------------------------------------------------

Responsibilities:
- Enforce firewall decision (ABSOLUTE)
- Enforce broker capability validation BEFORE execution
- Route only valid orders to broker adapters
- Produce standardized execution receipts

Key feature:
- Adapter imports are auto-detected across common repo layouts:
  - live_data.<adapter>
  - engine.live_data.<adapter>
  - engine.adapters.<adapter>
"""

from __future__ import annotations

import importlib
from typing import Dict, Any, Callable, Optional, Tuple

from engine.brokers.capabilities import validate_order, BrokerCapabilityError


class ExecutionRouterError(RuntimeError):
    pass


def _import_symbol(module_paths: list[str], symbol: str) -> Any:
    """
    Try to import `symbol` from the first module that has it.
    Fail-closed with explicit diagnostics.
    """
    tried: list[str] = []
    for mod in module_paths:
        tried.append(mod)
        try:
            m = importlib.import_module(mod)
            if hasattr(m, symbol):
                return getattr(m, symbol)
        except Exception:
            continue

    raise ExecutionRouterError(
        f"Adapter import failed. Could not find symbol '{symbol}'. "
        f"Tried modules: {tried}. "
        f"Fix: ensure your adapter file exists (e.g., live_data\\oanda_adapter.py) "
        f"and that the class name matches (e.g., OandaPaperAdapter)."
    )


# -------------------------------------------------------------------
# Resolve adapters (repo-proof)
# -------------------------------------------------------------------

_OANDA_ADAPTER_CLS = _import_symbol(
    module_paths=[
        "live_data.oanda_adapter",
        "engine.live_data.oanda_adapter",
        "engine.adapters.oanda_adapter",
    ],
    symbol="OandaPaperAdapter",
)

_ALPACA_ADAPTER_CLS = _import_symbol(
    module_paths=[
        "live_data.alpaca_adapter",
        "engine.live_data.alpaca_adapter",
        "engine.adapters.alpaca_adapter",
    ],
    symbol="AlpacaPaperAdapter",
)


class ExecutionRouter:
    def __init__(self) -> None:
        self._adapters = {
            "OANDA_PAPER": _OANDA_ADAPTER_CLS(),
            "ALPACA_PAPER": _ALPACA_ADAPTER_CLS(),
        }

    def route(
        self,
        *,
        broker_name: str,
        instrument: str,
        side: str,
        quantity: int,
        order_type: str,
        price: float | None,
        decision_envelope: Dict[str, Any],
        firewall_result: Dict[str, Any],
    ) -> Dict[str, Any]:

        # ------------------------------------------------------------------
        # Firewall enforcement (ABSOLUTE)
        # ------------------------------------------------------------------
        if not firewall_result.get("allowed"):
            raise ExecutionRouterError(f"Execution blocked by firewall: {firewall_result}")

        # ------------------------------------------------------------------
        # Broker capability validation (PRE-EXECUTION)
        # ------------------------------------------------------------------
        try:
            validate_order(
                broker_name=broker_name,
                instrument=instrument,
                order_type=order_type,
                quantity=quantity,
                side=side,
            )
        except BrokerCapabilityError as e:
            raise ExecutionRouterError(f"Broker capability violation: {e}") from e

        # ------------------------------------------------------------------
        # Adapter resolution
        # ------------------------------------------------------------------
        adapter = self._adapters.get(broker_name)
        if adapter is None:
            raise ExecutionRouterError(f"No adapter registered for broker={broker_name}")

        # ------------------------------------------------------------------
        # Execute via adapter (TEST/PAPER safe)
        # ------------------------------------------------------------------
        receipt = adapter.execute(
            instrument=instrument,
            side=side,
            quantity=quantity,
            order_type=order_type,
            price=price,
        )

        # ------------------------------------------------------------------
        # Standardized receipt
        # ------------------------------------------------------------------
        return {
            "broker": broker_name,
            "execution": receipt,
            "engine_run_id": decision_envelope.get("engine_run_id"),
            "decision": decision_envelope.get("final_decision"),
            "firewall": firewall_result,
        }
