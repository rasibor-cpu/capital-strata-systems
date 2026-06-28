"""
Event Models for CSS Enterprise Event Bus

This module defines the canonical Event object and its serialization.
"""

import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional

@dataclass
class Event:
    event_type: str
    severity: str
    category: str
    source: str
    payload: Dict[str, Any]
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    correlation_id: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    schema_version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        """Convert Event instance to a JSON-serializable dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """Reconstruct an Event instance from a dictionary representation."""
        return cls(
            event_type=data["event_type"],
            severity=data["severity"],
            category=data["category"],
            source=data["source"],
            payload=data.get("payload", {}),
            event_id=data.get("event_id", str(uuid.uuid4())),
            timestamp=data.get("timestamp", time.time()),
            correlation_id=data.get("correlation_id"),
            session_id=data.get("session_id"),
            user_id=data.get("user_id"),
            schema_version=data.get("schema_version", "1.0.0")
        )
