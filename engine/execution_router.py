"""
Execution Router (Paper-Safe)
=============================

Responsibilities:
- Consume execution decision envelope
- Enforce firewall outcome
- Route orders to paper broker adapters
- Return normalized execution receipt

This module NEVER decides.
It only enforces.
"""

from __future__ import annotations

from typing import Dict, Any

from engine.brokers.base_broker import BaseBroker
from engine.brokers.alpaca_paper_broker import AlpacaPaperBroker
from engine.brokers.oanda_paper_broker import OandaPaperBroker
from engine.brokers.binance_paper_broker import BinancePaperBroker


class ExecutionRouter:
    """
    Routes execution to the correct broker.
    """

    def __init__(self) -> None:
        # Register paper brokers only
        self._brokers: Dict[str, BaseBroker] = {
            "ALPACA_PAPER": AlpacaPaperBroker(),
            "OANDA_PAPER": OandaPaperBroker(),
            "BINANCE_PAPER": BinancePaperBroker(),
        }

    def route(
        self,
        *,
        broker_name: str,
        instrument: str,
        side: str,
        quantity: float,
        order_type: str,
        price: float | None,
        decision_envelope: Dict[str, Any],
        firewall_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Route execution to broker after ALL checks.
        """

        # ---------------------------------------------------------
        # Firewall enforcement
        # ---------------------------------------------------------
        if not firewall_result.get("allowed"):
            raise RuntimeError(
                f"Execution blocked by firewall: {firewall_result.get('reason')}"
            )

        # ---------------------------------------------------------
        # Decision enforcement
        # ---------------------------------------------------------
        if decision_envelope.get("final_decision") != "ALLOW":
            raise RuntimeError(
                f"Execution denied: decision envelope = {decision_envelope.get('final_decision')}"
            )

        # ---------------------------------------------------------
        # Broker selection
        # ---------------------------------------------------------
        broker = self._brokers.get(broker_name)
        if broker is None:
            raise ValueError(f"Unknown broker: {broker_name}")

        # ---------------------------------------------------------
        # Submit order
        # ---------------------------------------------------------
        execution_result = broker.submit_order(
            instrument=instrument,
            side=side,
            quantity=quantity,
            order_type=order_type,
            price=price,
            decision_envelope=decision_envelope,
        )

        return {
            "broker": broker_name,
            "execution": execution_result,
        }
