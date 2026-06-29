"""
Explainability Engine for CSS Trading Intelligence Foundation
"""

from typing import Dict, Any

class Explainability:
    """
    Translates automated gate decisions and execution outcomes into natural language.
    """
    @staticmethod
    def explain_trade_outcome(trade: Dict[str, Any]) -> str:
        """Formulate explanation text based on PnL sign and trade parameters."""
        pnl = float(trade.get("realized_pnl", 0.0))
        symbol = trade.get("symbol", "UNKNOWN")
        side = trade.get("side", "BUY")
        aclass = trade.get("asset_class", "UNKNOWN")
        
        if pnl > 0:
            return (
                f"Trade on {symbol} ({side} {aclass}) was completed successfully, yielding a gain of {pnl:.2f}. "
                f"The outcome matches positive momentum trends."
            )
        elif pnl < 0:
            return (
                f"Trade on {symbol} ({side} {aclass}) incurred a loss of {abs(pnl):.2f}. "
                f"The adverse movement was influenced by temporary slippage or execution timing."
            )
        else:
            return f"Trade on {symbol} ({side} {aclass}) broke even."
            
    @staticmethod
    def explain_gate_decision(decision_event: Any) -> str:
        """Formulate explanations for pre-trade gate approvals/rejections."""
        etype = decision_event.event_type
        payload = decision_event.payload or {}
        trade_id = payload.get("trade_id", "UNKNOWN")
        reason = payload.get("reason", "None provided")
        
        if etype == "TRADE_APPROVED":
            return f"Trade {trade_id} was approved by the gate as all pre-trade parameters and risk thresholds were satisfied."
        elif etype == "TRADE_REJECTED":
            return f"Trade {trade_id} was rejected by the gate. Reason: {reason}."
            
        return f"Event {etype} received with no corresponding gate decision outcome."
