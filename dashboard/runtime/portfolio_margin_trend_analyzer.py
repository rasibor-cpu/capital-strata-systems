from typing import List, Dict, Any, Optional

class PortfolioMarginTrendAnalyzer:
    """
    Read-only analytics layer that consumes historical portfolio margin snapshots and risk events 
    and produces institutional early-warning indicators.
    """

    def __init__(self, history_store):
        self.history_store = history_store

    def calculate_margin_utilization_trend(self) -> str:
        snapshots = self.history_store.list_snapshots()
        if not snapshots:
            return "DATA_UNAVAILABLE"
            
        self._validate_snapshots(snapshots)
        
        if len(snapshots) < 2:
            return "FLAT"
            
        latest = snapshots[-1]
        previous = snapshots[-2]
        
        # Avoid division by zero
        if latest["portfolio_margin_available"] == 0 and previous["portfolio_margin_available"] == 0:
             return "FLAT"
        if previous["portfolio_margin_available"] == 0:
             return "IMPROVING" if latest["portfolio_margin_available"] > 0 else "FLAT"

        latest_ratio = latest["portfolio_margin_used"] / (latest["portfolio_margin_used"] + latest["portfolio_margin_available"]) if (latest["portfolio_margin_used"] + latest["portfolio_margin_available"]) > 0 else 0
        previous_ratio = previous["portfolio_margin_used"] / (previous["portfolio_margin_used"] + previous["portfolio_margin_available"]) if (previous["portfolio_margin_used"] + previous["portfolio_margin_available"]) > 0 else 0
        
        if latest_ratio > previous_ratio:
            return "DETERIORATING"
        elif latest_ratio < previous_ratio:
            return "IMPROVING"
        else:
            return "FLAT"

    def calculate_buying_power_trend(self) -> str:
        snapshots = self.history_store.list_snapshots()
        if not snapshots:
            return "DATA_UNAVAILABLE"
            
        self._validate_snapshots(snapshots)
        
        if len(snapshots) < 2:
            return "FLAT"
            
        latest = snapshots[-1]["portfolio_buying_power"]
        previous = snapshots[-2]["portfolio_buying_power"]
        
        if latest < previous:
            return "DETERIORATING"
        elif latest > previous:
            return "IMPROVING"
        else:
            return "FLAT"

    def calculate_equity_trend(self) -> str:
        snapshots = self.history_store.list_snapshots()
        if not snapshots:
            return "DATA_UNAVAILABLE"
            
        self._validate_snapshots(snapshots)
        
        if len(snapshots) < 2:
            return "FLAT"
            
        latest = snapshots[-1]["portfolio_equity"]
        previous = snapshots[-2]["portfolio_equity"]
        
        if latest < previous:
            return "DETERIORATING"
        elif latest > previous:
            return "IMPROVING"
        else:
            return "FLAT"

    def calculate_risk_state_trend(self) -> str:
        snapshots = self.history_store.list_snapshots()
        if not snapshots:
            return "DATA_UNAVAILABLE"
            
        self._validate_snapshots(snapshots)
        
        if len(snapshots) < 2:
            return "FLAT"
            
        latest = snapshots[-1]["portfolio_risk_state"]
        previous = snapshots[-2]["portfolio_risk_state"]
        
        state_severity = {
            "NORMAL": 0,
            "WARNING": 1,
            "RESTRICTED": 2,
            "CRITICAL": 3,
            "LIQUIDATION_RISK": 4
        }
        
        latest_sev = state_severity.get(latest, -1)
        prev_sev = state_severity.get(previous, -1)
        
        if latest_sev > prev_sev:
            return "DETERIORATING"
        elif latest_sev < prev_sev:
            return "IMPROVING"
        else:
            return "FLAT"

    def calculate_escalation_frequency(self) -> float:
        events = self.history_store.list_risk_events()
        if not events:
            return 0.0
            
        self._validate_events(events)
        
        return float(len(events))

    def generate_early_warning_summary(self) -> Dict[str, Any]:
        snapshots = self.history_store.list_snapshots()
        events = self.history_store.list_risk_events()
        
        if not snapshots:
            return {
                "warning_level": "DATA_UNAVAILABLE",
                "snapshot_count": 0,
                "event_count": 0,
                "trend_direction": "DATA_UNAVAILABLE",
                "summary": "Data unavailable"
            }
            
        self._validate_snapshots(snapshots)
        self._validate_events(events)
        
        event_count = len(events)
        snapshot_count = len(snapshots)
        
        margin_trend = self.calculate_margin_utilization_trend()
        risk_trend = self.calculate_risk_state_trend()
        
        latest_state = snapshots[-1]["portfolio_risk_state"]
        
        warning_level = "GREEN"
        summary = "No material deterioration."
        trend_direction = margin_trend
        
        if latest_state in ["CRITICAL", "LIQUIDATION_RISK"] or (risk_trend == "DETERIORATING" and event_count > 3):
            warning_level = "RED"
            summary = "Persistent escalation trend or liquidation proximity."
        elif event_count > 1 or latest_state in ["RESTRICTED"]:
            warning_level = "ORANGE"
            summary = "Repeated escalation events."
        elif margin_trend == "DETERIORATING" or latest_state == "WARNING":
            warning_level = "YELLOW"
            summary = "Observable deterioration."
            
        return {
            "warning_level": warning_level,
            "snapshot_count": snapshot_count,
            "event_count": event_count,
            "trend_direction": trend_direction,
            "summary": summary
        }
        
    def _validate_snapshots(self, snapshots: List[Dict[str, Any]]) -> None:
        required_keys = [
            "portfolio_equity", 
            "portfolio_buying_power", 
            "portfolio_margin_used", 
            "portfolio_margin_available", 
            "portfolio_risk_state",
            "timestamp"
        ]
        for snap in snapshots:
            if not isinstance(snap, dict):
                raise ValueError("Malformed snapshot: not a dictionary")
            for k in required_keys:
                if k not in snap or snap[k] is None:
                    raise ValueError(f"Malformed snapshot: missing {k}")

    def _validate_events(self, events: List[Dict[str, Any]]) -> None:
        required_keys = ["risk_state", "escalation_level", "timestamp"]
        for evt in events:
            if not isinstance(evt, dict):
                raise ValueError("Malformed event: not a dictionary")
            for k in required_keys:
                if k not in evt or evt[k] is None:
                    raise ValueError(f"Malformed event: missing {k}")
