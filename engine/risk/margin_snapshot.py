from dataclasses import dataclass
from engine.risk.margin_state import MarginState

@dataclass(frozen=True)
class MarginSnapshot:
    broker: str
    account_id: str
    timestamp: str
    equity: float
    cash: float
    buying_power: float
    maintenance_margin: float
    initial_margin: float
    margin_used: float
    margin_available: float
    margin_ratio: float
    margin_state: MarginState
