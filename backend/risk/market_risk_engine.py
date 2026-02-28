from decimal import Decimal
from typing import Dict


class MarketRiskEngine:
    """
    Simplified Market Risk Engine (Phase 1)
    Applies risk weight to trading book exposures (lane T=2)
    """

    def compute(self, journal: Dict, coa_lookup: Dict) -> Dict:

        market_rwa = Decimal("0")
        market_exposure = Decimal("0")

        for line in journal["lines"]:
            gl_code = line["gl_code"]
            metadata = coa_lookup.get(gl_code)

            if not metadata:
                continue

            if metadata.get("risk_type") != "market":
                continue

            weight = Decimal(str(metadata.get("regulatory_weight_default", 0)))
            amount = line["amount"]

            exposure = amount
            rwa = exposure * weight

            market_exposure += exposure
            market_rwa += rwa

        return {
            "market_exposure_delta": float(market_exposure),
            "market_rwa_delta": float(market_rwa),
        }