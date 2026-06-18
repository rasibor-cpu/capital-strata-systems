import os
import json
from typing import List, Dict, Any, Optional

from engine.risk.portfolio_margin_snapshot import PortfolioMarginSnapshot

class PortfolioMarginHistoryStore:
    """
    Read-only historical tracking layer for portfolio margin risk states.
    Records portfolio margin snapshots and risk events to append-only JSONL files.
    """

    def __init__(self, storage_dir: str = "artifacts/portfolio_margin_history"):
        self.storage_dir = storage_dir
        self.snapshots_file = os.path.join(self.storage_dir, "portfolio_margin_snapshots.jsonl")
        self.events_file = os.path.join(self.storage_dir, "portfolio_margin_risk_events.jsonl")
        
        # Ensure directory exists
        if not os.path.exists(self.storage_dir):
            os.makedirs(self.storage_dir, exist_ok=True)

    def append_snapshot(self, snapshot: PortfolioMarginSnapshot) -> None:
        if not isinstance(snapshot, PortfolioMarginSnapshot):
            raise ValueError("Invalid snapshot: Must be an instance of PortfolioMarginSnapshot")
            
        if not hasattr(snapshot, "portfolio_risk_state") or snapshot.portfolio_risk_state is None:
            raise ValueError("Invalid snapshot: missing risk state")
            
        if not hasattr(snapshot, "timestamp") or not snapshot.timestamp:
            raise ValueError("Invalid snapshot: missing timestamp")

        record = {
            "portfolio_equity": snapshot.portfolio_equity,
            "portfolio_buying_power": snapshot.portfolio_buying_power,
            "portfolio_margin_used": snapshot.portfolio_margin_used,
            "portfolio_margin_available": snapshot.portfolio_margin_available,
            "portfolio_risk_state": snapshot.portfolio_risk_state.name,
            "broker_count": snapshot.broker_count,
            "timestamp": snapshot.timestamp
        }
        
        self._append_line(self.snapshots_file, record)

    def append_risk_event(self, event: Dict[str, Any]) -> None:
        if not isinstance(event, dict):
            raise ValueError("Invalid event: must be a dict")
            
        required_keys = ["risk_state", "escalation_level", "timestamp"]
        for k in required_keys:
            if k not in event or event[k] is None:
                raise ValueError(f"Invalid event: missing {k}")

        self._append_line(self.events_file, event)

    def list_snapshots(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        return self._read_lines(self.snapshots_file, limit)

    def list_risk_events(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        return self._read_lines(self.events_file, limit)

    def latest_snapshot(self) -> Optional[Dict[str, Any]]:
        snapshots = self.list_snapshots(limit=1)
        return snapshots[0] if snapshots else None

    def latest_risk_event(self) -> Optional[Dict[str, Any]]:
        events = self.list_risk_events(limit=1)
        return events[0] if events else None

    def _append_line(self, filepath: str, record: Dict[str, Any]) -> None:
        with open(filepath, "a") as f:
            f.write(json.dumps(record, sort_keys=True) + "\n")

    def _read_lines(self, filepath: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        if not os.path.exists(filepath):
            return []
            
        records = []
        with open(filepath, "r") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        
        # We need to return the latest 'limit' records or all of them. 
        # The prompt says "Returns historical portfolio margin snapshots in append order."
        # If limit is specified, it usually means the *latest* N records, or first N?
        # Usually it means latest N. But if we return in append order, let's take the last 'limit' items.
        if limit is not None and limit > 0:
            records = records[-limit:]
            
        return records
