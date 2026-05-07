from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionRenderContract:
    """
    PCNRASS-safe immutable render contract for execution display.
    """

    execution_state: str
    accepted_trade_count: int
    rejected_trade_count: int
    pending_trade_count: int
    total_execution_cost: float
    slippage_cost: float
    spread_cost: float
    fee_cost: float
    avg_slippage_bps: float
    avg_spread_bps: float
    execution_cost_state: str
    last_execution_event: str

    @classmethod
    def from_summary(cls, execution_summary: dict) -> "ExecutionRenderContract":
        summary = execution_summary or {}

        return cls(
            execution_state=str(summary.get("execution_state", "IDLE")),
            accepted_trade_count=int(summary.get("accepted_trade_count", 0)),
            rejected_trade_count=int(summary.get("rejected_trade_count", 0)),
            pending_trade_count=int(summary.get("pending_trade_count", 0)),
            total_execution_cost=float(
                summary.get("total_execution_cost", 0.0)
            ),
            slippage_cost=float(summary.get("slippage_cost", 0.0)),
            spread_cost=float(summary.get("spread_cost", 0.0)),
            fee_cost=float(summary.get("fee_cost", 0.0)),
            avg_slippage_bps=float(summary.get("avg_slippage_bps", 0.0)),
            avg_spread_bps=float(summary.get("avg_spread_bps", 0.0)),
            execution_cost_state=str(
                summary.get("execution_cost_state", "UNKNOWN")
            ),
            last_execution_event=str(summary.get("last_execution_event", "")),
        )
