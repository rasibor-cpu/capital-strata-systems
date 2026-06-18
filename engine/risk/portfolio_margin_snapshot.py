from dataclasses import dataclass
from engine.risk.margin_state import MarginState

@dataclass(frozen=True)
class PortfolioMarginSnapshot:
    portfolio_equity: float
    portfolio_buying_power: float
    portfolio_margin_used: float
    portfolio_margin_available: float
    portfolio_risk_state: MarginState
    broker_count: int
    timestamp: str = ""
