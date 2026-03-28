from __future__ import annotations
from typing import Dict


class ProfitabilityGate:
    """
    Ensures trades have sufficient edge AFTER costs.

    This is a NON-REGRESSION ADDITION.
    It does NOT interfere with existing scoring logic.
    """

    def __init__(
        self,
        min_net_edge_bps: float = 10.0,   # minimum acceptable edge after costs
        assumed_slippage_bps: float = 2.0,
        assumed_fee_bps: float = 1.5,
    ):
        self.min_net_edge = min_net_edge_bps
        self.slippage = assumed_slippage_bps
        self.fees = assumed_fee_bps

    def evaluate(self, row: Dict) -> Dict:
        """
        Input row must contain:
        - spread_bps
        - decision_score OR vwap_dev_abs as proxy for edge
        """

        spread = float(row.get("spread_bps", 0.0))

        # Use best available proxy for edge
        gross_edge = float(
            row.get("expected_edge_bps") or
            row.get("decision_score", 0.0) * 10.0 or
            row.get("vwap_dev_abs", 0.0) * 10000.0
        )

        total_cost = spread + self.slippage + self.fees
        net_edge = gross_edge - total_cost

        passed = net_edge >= self.min_net_edge

        return {
            "pass_profitability_gate": passed,
            "gross_edge_bps": gross_edge,
            "estimated_cost_bps": total_cost,
            "net_edge_bps": net_edge,
            "reason": (
                "net edge acceptable"
                if passed else
                "net edge too low after costs"
            ),
        }
