from decimal import Decimal
from typing import Dict


class OperationalRiskEngine:
    """
    Basel Basic Indicator placeholder
    Operational RWA not computed per transaction in Phase 1
    """

    def compute(self, journal: Dict) -> Dict:
        return {
            "operational_rwa_delta": 0.0
        }