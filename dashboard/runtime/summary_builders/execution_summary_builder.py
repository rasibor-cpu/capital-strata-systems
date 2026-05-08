from __future__ import annotations

from typing import Any, Dict

from dashboard.runtime._utils import safe_float, safe_int


class ExecutionSummaryBuilder:
    """
    PCNRASS-safe execution summary builder.

    Purpose:
    - Normalize execution-cost and trade-routing telemetry.
    - Keep execution summaries separate from renderers.
    - Avoid broker or execution side effects.
    """

    def build(
        self,
        execution_payload: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        execution = execution_payload or {}

        return {
            "execution_state": str(execution.get("execution_state", "IDLE")),
            "accepted_trade_count": safe_int(
                execution.get("accepted_trade_count", 0)
            ),
            "rejected_trade_count": safe_int(
                execution.get("rejected_trade_count", 0)
            ),
            "pending_trade_count": safe_int(execution.get("pending_trade_count", 0)),
            "total_execution_cost": safe_float(
                execution.get("total_execution_cost", 0.0)
            ),
            "slippage_cost": safe_float(execution.get("slippage_cost", 0.0)),
            "spread_cost": safe_float(execution.get("spread_cost", 0.0)),
            "fee_cost": safe_float(execution.get("fee_cost", 0.0)),
            "avg_slippage_bps": safe_float(
                execution.get("avg_slippage_bps", 0.0)
            ),
            "avg_spread_bps": safe_float(
                execution.get("avg_spread_bps", 0.0)
            ),
            "execution_cost_state": str(
                execution.get("execution_cost_state", "UNKNOWN")
            ),
            "last_execution_event": str(
                execution.get("last_execution_event", "")
            ),
        }
