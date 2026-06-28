"""
Event Models for CSS Enterprise Event Bus

This module defines the canonical Event object and its serialization.
"""

import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional
from backend.common.exceptions import ValidationException
from backend.common.validation import validate_required_fields, validate_field_type
from backend.common.versioning import validate_schema_version
from backend.common.serialization import JSONSerializable

@dataclass
class Event(JSONSerializable):
    """
    Canonical Enterprise Event representation.
    
    Responsibility: Standard data payload exchange model for all subsystems.
    Dependencies: backend.common.serialization.JSONSerializable
    Thread-safety: Immutable fields by design, fully thread-safe for reads.
    """
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

    def validate(self) -> None:
        """Validate event fields and schema compatibility."""
        validate_schema_version(self.schema_version, "1.0.0")

        if not self.event_type:
            raise ValidationException("event_type cannot be empty")
        if not self.severity:
            raise ValidationException("severity cannot be empty")
        if not self.category:
            raise ValidationException("category cannot be empty")
        if not self.source:
            raise ValidationException("source cannot be empty")
        if self.payload is None:
            raise ValidationException("payload cannot be None")

        validate_field_type("event_type", self.event_type, str)
        validate_field_type("severity", self.severity, str)
        validate_field_type("category", self.category, str)
        validate_field_type("source", self.source, str)
        validate_field_type("payload", self.payload, dict)
        validate_field_type("event_id", self.event_id, str)
        validate_field_type("timestamp", self.timestamp, (int, float))

    def to_dict(self) -> Dict[str, Any]:
        """Convert Event instance to a JSON-serializable dictionary."""
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """Reconstruct an Event instance from a dictionary representation."""
        validate_required_fields(data, ["event_type", "severity", "category", "source"])
        
        event = cls(
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
        event.validate()
        return event

