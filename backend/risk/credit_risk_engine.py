from decimal import Decimal
from typing import Dict, List


class CreditRiskEngine:
    """
    Basel-style Credit Risk Engine (Phase 1)
    Uses GL metadata: regulatory_weight_default
    """

    def compute(self, journal: Dict, coa_lookup: Dict) -> Dict:
        """
        journal: normalized journal
        coa_lookup: dict mapping gl_code -> metadata
        """

        credit_rwa = Decimal("0")
        credit_exposure = Decimal("0")

        for line in journal["lines"]:
            gl_code = line["gl_code"]
            metadata = coa_lookup.get(gl_code)

            if not metadata:
                continue

            if metadata.get("risk_type") != "credit":
                continue

            weight = Decimal(str(metadata.get("regulatory_weight_default", 0)))
            amount = line["amount"]

            # Only debit side increases exposure for assets
            if line["dc"] == "D":
                exposure = amount
                rwa = exposure * weight
                credit_exposure += exposure
                credit_rwa += rwa

        return {
            "credit_exposure_delta": float(credit_exposure),
            "credit_rwa_delta": float(credit_rwa),
        }