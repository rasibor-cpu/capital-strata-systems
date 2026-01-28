from dataclasses import dataclass
from typing import List, Optional

from engine.domain.orders import OrderIntent
from engine.domain.executions import ExecutionReport
from engine.domain.fees import FeeSchedule
from engine.execution.paper_broker import PaperBrokerAdapter
from engine.execution.broker_base import BrokerAdapter


@dataclass
class ExecutionRoutingConfig:
    """
    Minimal routing config.
    Later this can be pulled from EngineConfig / RBAC config store.
    """
    execution_mode: str = "PAPER"  # PAPER / LIVE (future)
    paper_seed: int = 42
    base_latency_ms: int = 25
    slippage_bps: float = 1.0
    broker_name: str = "PAPER"


class OrderRouter:
    """
    Routes OrderIntent to the configured BrokerAdapter.
    Strategy is unaware of which broker is active.
    """

    def __init__(self, fee_schedule: FeeSchedule, cfg: Optional[ExecutionRoutingConfig] = None):
        self.fee_schedule = fee_schedule
        self.cfg = cfg or ExecutionRoutingConfig()
        self._broker: Optional[BrokerAdapter] = None

    def _get_broker(self) -> BrokerAdapter:
        if self._broker is not None:
            return self._broker

        mode = (self.cfg.execution_mode or "PAPER").upper()

        if mode == "PAPER":
            self._broker = PaperBrokerAdapter(
                self.fee_schedule,
                broker_name=self.cfg.broker_name,
                seed=self.cfg.paper_seed,
                base_latency_ms=self.cfg.base_latency_ms,
                slippage_bps=self.cfg.slippage_bps,
            )
            return self._broker

        # LIVE mode will be added later (Module 9+)
        raise ValueError(f"Unsupported execution_mode: {self.cfg.execution_mode}")

    def submit(self, order: OrderIntent) -> List[ExecutionReport]:
        broker = self._get_broker()
        return broker.submit_order(order)