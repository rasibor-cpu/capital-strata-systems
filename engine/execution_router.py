"""
Execution Router (Paper-Safe, Journal-Aware)
============================================

Responsibilities:
- Consume execution decision envelope
- Enforce firewall outcome
- Route orders to paper broker adapters
- Optionally journal execution lifecycle
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
from engine.brokers.ibkr_paper_broker import IbkrPaperBroker

# Optional execution journal (may be gitignored / unavailable)
try:
    from engine.execution_journal import ExecutionJournal
except Exception:  # pragma: no cover
    ExecutionJournal = None  # type: ignore


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
            "IBKR_PAPER": IbkrPaperBroker(),
        }

        self._journal = ExecutionJournal() if ExecutionJournal else None

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

        engine_run_id = decision_envelope.get("engine_run_id", "UNKNOWN")

        execution_request = {
            "broker": broker_name,
            "instrument": instrument,
            "side": side,
            "quantity": quantity,
            "order_type": order_type,
            "price": price,
        }

        # ---------------------------------------------------------
        # Firewall enforcement
        # ---------------------------------------------------------
        if not firewall_result.get("allowed"):
            if self._journal:
                self._journal.record(
                    engine_run_id=engine_run_id,
                    decision_envelope=decision_envelope,
                    firewall_result=firewall_result,
                    execution_request=execution_request,
                    execution_result=None,
                )
            raise RuntimeError(
                f"Execution blocked by firewall: {firewall_result.get('reason')}"
            )

        # ---------------------------------------------------------
        # Decision enforcement
        # ---------------------------------------------------------
        if decision_envelope.get("final_decision") != "ALLOW":
            if self._journal:
                self._journal.record(
                    engine_run_id=engine_run_id,
                    decision_envelope=decision_envelope,
                    firewall_result=firewall_result,
                    execution_request=execution_request,
                    execution_result=None,
                )
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

        # ---------------------------------------------------------
        # Optional journaling (non-blocking)
        # ---------------------------------------------------------
        if self._journal:
            self._journal.record(
                engine_run_id=engine_run_id,
                decision_envelope=decision_envelope,
                firewall_result=firewall_result,
                execution_request=execution_request,
                execution_result=execution_result,
            )

        return {
            "broker": broker_name,
            "execution": execution_result,
        }
