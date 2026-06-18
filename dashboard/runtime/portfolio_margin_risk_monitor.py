import datetime
from typing import Dict, Any

from engine.risk.portfolio_margin_snapshot import PortfolioMarginSnapshot
from engine.risk.margin_state import MarginState
from dashboard.runtime.summary_builders.portfolio_margin_summary_builder import PortfolioMarginSummaryBuilder

class PortfolioMarginRiskMonitor:
    """
    Read-only institutional portfolio margin risk escalation monitor.
    Provides governance and observability into portfolio margin stress.
    This component does not affect any execution authority, broker behavior, or order routing.
    """

    def __init__(self):
        self._summary_builder = PortfolioMarginSummaryBuilder()

    def evaluate(self, snapshot: PortfolioMarginSnapshot) -> Dict[str, Any]:
        """
        Evaluates the portfolio margin snapshot and returns the risk escalation state.
        
        Args:
            snapshot: The canonical PortfolioMarginSnapshot.
            
        Returns:
            Dict containing exactly:
            - risk_state
            - risk_banner
            - escalation_level
            - escalation_required
            - escalation_message
            - timestamp
        """
        if not isinstance(snapshot, PortfolioMarginSnapshot):
            raise ValueError("Invalid snapshot type: Must be PortfolioMarginSnapshot")
            
        summary = self._summary_builder.build(snapshot)
        state = snapshot.portfolio_risk_state
        
        escalation_level = 0
        escalation_required = False
        escalation_message = ""
        
        if state == MarginState.NORMAL:
            escalation_level = 0
            escalation_required = False
            escalation_message = "Portfolio margin is healthy. No escalation required."
        elif state == MarginState.WARNING:
            escalation_level = 1
            escalation_required = True
            escalation_message = "Level 1 Escalation: Portfolio margin warning. Monitor closely."
        elif state == MarginState.RESTRICTED:
            escalation_level = 2
            escalation_required = True
            escalation_message = "Level 2 Escalation: Margin restrictions active. New risk must be restricted."
        elif state == MarginState.CRITICAL:
            escalation_level = 3
            escalation_required = True
            escalation_message = "Level 3 Escalation: Margin stress detected. Prepare for possible intervention."
        elif state == MarginState.LIQUIDATION_RISK:
            escalation_level = 4
            escalation_required = True
            escalation_message = "Level 4 Escalation: Immediate margin intervention required to prevent liquidation."
        else:
            escalation_level = 0
            escalation_required = False
            escalation_message = "Unknown margin state."

        # Format timestamp
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        return {
            "risk_state": summary["portfolio_risk_state"],
            "risk_banner": summary["risk_banner"],
            "escalation_level": escalation_level,
            "escalation_required": escalation_required,
            "escalation_message": escalation_message,
            "timestamp": timestamp
        }
