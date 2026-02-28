from typing import Dict

from .credit_risk_engine import CreditRiskEngine
from .market_risk_engine import MarketRiskEngine
from .operational_risk_engine import OperationalRiskEngine


class RiskDeltaCalculator:

    def __init__(self):
        self.credit_engine = CreditRiskEngine()
        self.market_engine = MarketRiskEngine()
        self.operational_engine = OperationalRiskEngine()

    def compute(self, journal: Dict, coa_lookup: Dict) -> Dict:

        credit = self.credit_engine.compute(journal, coa_lookup)
        market = self.market_engine.compute(journal, coa_lookup)
        operational = self.operational_engine.compute(journal)

        return {
            "credit": credit,
            "market": market,
            "operational": operational,
        }