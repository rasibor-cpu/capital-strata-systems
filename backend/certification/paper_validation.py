"""
Extended Paper Trading Validator for CSS Certification Subsystem
"""

from typing import Dict, Any, List

class PaperValidator:
    """
    Validates paper trading simulation consistency, restarts, and capital limits.
    """
    @staticmethod
    def validate_session_consistency(
        events: List[Any],
        trades: List[Dict[str, Any]],
        health: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Verify matches between trade logs, capital limits, and event bus counts."""
        findings = []
        warnings = []
        
        restarts = health.get("restart_count", 0)
        if restarts > 3:
            warnings.append(f"High restart count detected: {restarts} restarts logged.")
            
        approvals = len([e for e in events if e.event_type == "TRADE_APPROVED"])
        rejections = len([e for e in events if e.event_type == "TRADE_REJECTED"])
        total_trade_events = approvals + rejections
        
        if len(trades) != total_trade_events:
            findings.append(f"Trade event mismatch: {len(trades)} trades recorded but {total_trade_events} events published.")
            
        negative_pnl = [t for t in trades if float(t.get("realized_pnl", 0.0)) < -10000.0]
        if negative_pnl:
            findings.append("Capital limit breached: large trade loss detected.")
            
        is_consistent = len(findings) == 0
        
        return {
            "is_consistent": is_consistent,
            "session_count": 1,
            "simulated_trades_count": len(trades),
            "findings": findings,
            "warnings": warnings,
            "consistency_ratio": 1.0 if is_consistent else 0.8
        }
