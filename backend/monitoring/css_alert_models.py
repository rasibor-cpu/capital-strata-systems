from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any

class AlertType(Enum):
    ENGINE = "ENGINE"
    TRADE = "TRADE"
    RISK = "RISK"
    BROKER = "BROKER"
    SYSTEM = "SYSTEM"

class AlertSeverity(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

@dataclass
class CSSAlert:
    alert_id: str
    timestamp: str
    alert_type: AlertType
    severity: AlertSeverity
    message: str
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)
