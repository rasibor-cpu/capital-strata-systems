"""
CSS Production Pilot Framework

Manages configuration, approval workflow, execution state, completion summary,
success/failure criteria, and rollback triggers for controlled production pilots.
"""

import time
from typing import Dict, Any, List

class ProductionPilotFramework:
    """
    Manages the lifecycle of a controlled live production pilot.
    """
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {
            "max_capital_usd": 1000.0,
            "target_duration_hours": 24,
            "allowed_asset_classes": ["FX", "CRYPTO"],
            "max_drawdown_percent": 2.0,
            "max_connection_drops": 3
        }
        self.state = "INACTIVE"  # INACTIVE, RUNNING, COMPLETED, ROLLED_BACK
        self.approvals = {
            "operator_signoff": False,
            "risk_committee": False,
            "deployment_approval": False
        }
        self.metrics = {
            "connection_drops": 0,
            "current_drawdown_percent": 0.0,
            "trades_executed": 0,
            "realized_pnl_usd": 0.0
        }
        self.rollback_reason = None

    def approve_pilot(self, role: str) -> None:
        """Approves the pilot for the specified stakeholder role."""
        if role in self.approvals:
            self.approvals[role] = True

    def start_pilot(self) -> str:
        """Transitions pilot state to RUNNING if all approvals are met."""
        if not all(self.approvals.values()):
            return "NO_GO: Approvals missing"
        self.state = "RUNNING"
        return "RUNNING"

    def record_connection_drop(self) -> None:
        """Records a connection drop and evaluates rollback triggers."""
        self.metrics["connection_drops"] += 1
        self._check_rollback_triggers()

    def record_pnl(self, pnl: float) -> None:
        """Records realized P&L and updates current drawdown percent."""
        self.metrics["realized_pnl_usd"] += pnl
        if self.metrics["realized_pnl_usd"] < 0:
            loss = abs(self.metrics["realized_pnl_usd"])
            self.metrics["current_drawdown_percent"] = (loss / self.config["max_capital_usd"]) * 100.0
        self._check_rollback_triggers()

    def trigger_rollback(self, reason: str) -> None:
        """Forces immediate pilot rollback."""
        self.state = "ROLLED_BACK"
        self.rollback_reason = reason

    def _check_rollback_triggers(self) -> None:
        """Evaluates pilot success/failure criteria to trigger auto-rollback."""
        if self.metrics["connection_drops"] >= self.config["max_connection_drops"]:
            self.trigger_rollback("Max connection drops exceeded")
        elif self.metrics["current_drawdown_percent"] >= self.config["max_drawdown_percent"]:
            self.trigger_rollback("Max drawdown limit violated")

    def get_completion_summary(self) -> Dict[str, Any]:
        """Generates completion summary and final success/failure evaluation."""
        success = False
        if self.state == "COMPLETED" and not self.rollback_reason:
            success = True

        return {
            "state": self.state,
            "success": success,
            "metrics": self.metrics,
            "rollback_reason": self.rollback_reason,
            "timestamp": time.time()
        }
