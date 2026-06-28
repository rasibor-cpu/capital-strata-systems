from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from analytics.portfolio_optimizer import PortfolioAllocationPlan


class PortfolioAllocationAudit:
    """
    Writes portfolio allocation plans as JSON records.

    This component is append-only and does not modify existing
    allocation plans.
    """

    def __init__(self, output_dir: str = "artifacts/portfolio_audit"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_plan(self, plan: PortfolioAllocationPlan) -> Path:
        data: dict[str, Any] = plan.to_dict()
        timestamp = (
            data["generated_at"]
            .replace(":", "")
            .replace("-", "")
            .replace(".", "")
        )
        path = self.output_dir / f"portfolio_allocation_{timestamp}.json"
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return path
