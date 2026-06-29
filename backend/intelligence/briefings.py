"""
Executive Briefing Generator for CSS Trading Intelligence Foundation
"""

from typing import Dict, Any

class BriefingGenerator:
    """
    Compiles operational intelligence details into executive text briefings.
    """
    @staticmethod
    def generate_briefing(briefing_type: str, intelligence_report: Dict[str, Any]) -> Dict[str, Any]:
        """Format briefing summary maps by briefing type category."""
        bt = briefing_type.upper()
        regime = intelligence_report.get("market_regime", "UNKNOWN")
        win_loss = intelligence_report.get("win_loss_statistics", {})
        drawdown = intelligence_report.get("drawdown_trends", {})
        portfolio = intelligence_report.get("portfolio_concentration", {})
        recs = intelligence_report.get("recommendations", [])
        
        if bt == "MORNING":
            title = "Morning Executive Briefing"
            message = (
                f"Active market regime classified as {regime}. "
                f"Advisory confidence: {intelligence_report.get('advisory_confidence_score', 0.5):.2f}. "
                f"Top recommendation: {recs[0]['message'] if recs else 'None'}"
            )
        elif bt == "EVENING":
            title = "Evening Strategy Summary"
            message = (
                f"Trading completed with {win_loss.get('total_trades', 0)} total trades today. "
                f"Win rate: {win_loss.get('win_rate', 0.0)*100:.1f}%. "
                f"Cumulative PnL: {drawdown.get('cumulative_pnl', 0.0):.2f}."
            )
        elif bt == "INCIDENT":
            title = "System Incident Alert"
            message = "Critical: abnormal operations heartbeat age detected. Verification recommended."
        elif bt == "PORTFOLIO":
            title = "Portfolio Concentration Report"
            message = (
                f"Highest exposure is in {portfolio.get('highest_exposure_asset', 'NONE')} "
                f"with a risk score of {portfolio.get('risk_concentration_score', 0.0):.1f}%."
            )
        elif bt == "RISK":
            title = "Risk Advisory Briefing"
            message = (
                f"Max drawdown peak-to-trough measured at {drawdown.get('max_drawdown', 0.0):.2f}. "
                f"Risk concentration score is {portfolio.get('risk_concentration_score', 0.0):.1f}%."
            )
        else:
            title = "Executive Briefing"
            message = f"Market conditions: {regime}."
            
        return {
            "title": title,
            "message": message,
            "briefing_type": bt
        }
