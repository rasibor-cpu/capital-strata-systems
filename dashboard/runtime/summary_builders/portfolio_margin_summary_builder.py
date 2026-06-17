from typing import Any, Dict
from engine.risk.portfolio_margin_snapshot import PortfolioMarginSnapshot
from engine.risk.margin_state import MarginState

class PortfolioMarginSummaryBuilder:
    """
    Read-only presentation builder for Portfolio Margin Governance Observability.
    
    Transforms the canonical PortfolioMarginSnapshot into the standardized 
    dictionary format consumed by web and mobile dashboards. Assigns institutional 
    classification banners without changing any execution routing or risk logic.
    """

    def build(self, snapshot: PortfolioMarginSnapshot) -> Dict[str, Any]:
        """
        Builds the observability dictionary from a PortfolioMarginSnapshot.
        
        Args:
            snapshot: The canonical PortfolioMarginSnapshot.
            
        Returns:
            Dict containing exactly:
            - portfolio_equity
            - portfolio_buying_power
            - portfolio_margin_used
            - portfolio_margin_available
            - portfolio_risk_state
            - broker_count
            - risk_banner
        """
        if not isinstance(snapshot, PortfolioMarginSnapshot):
            raise ValueError("Invalid snapshot: Must be an instance of PortfolioMarginSnapshot")
            
        return {
            "portfolio_equity": snapshot.portfolio_equity,
            "portfolio_buying_power": snapshot.portfolio_buying_power,
            "portfolio_margin_used": snapshot.portfolio_margin_used,
            "portfolio_margin_available": snapshot.portfolio_margin_available,
            "portfolio_risk_state": snapshot.portfolio_risk_state.name,
            "broker_count": snapshot.broker_count,
            "risk_banner": self._get_risk_banner(snapshot.portfolio_risk_state)
        }
        
    def _get_risk_banner(self, state: MarginState) -> str:
        """
        Maps institutional classifications to executive summary banners.
        """
        if state == MarginState.NORMAL:
            return "Portfolio Margin Healthy"
        elif state == MarginState.WARNING:
            return "Portfolio Margin Warning"
        elif state == MarginState.RESTRICTED:
            return "Margin Restrictions Active"
        elif state == MarginState.CRITICAL:
            return "Margin Stress Detected"
        elif state == MarginState.LIQUIDATION_RISK:
            return "Immediate Margin Intervention Required"
        else:
            return "Unknown Margin State"
