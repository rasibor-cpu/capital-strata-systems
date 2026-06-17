from enum import Enum

class MarginState(Enum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    RESTRICTED = "RESTRICTED"
    CRITICAL = "CRITICAL"
    LIQUIDATION_RISK = "LIQUIDATION_RISK"
