import json

from analytics.portfolio_allocation_audit import PortfolioAllocationAudit
from analytics.portfolio_optimizer import PortfolioAllocationPlan, StrategyAllocation


def test_write_plan(tmp_path):
    audit = PortfolioAllocationAudit(output_dir=str(tmp_path))

    plan = PortfolioAllocationPlan(
        generated_at="2026-06-28T16:00:00Z",
        market_regime="TRENDING",
        risk_profile="BALANCED",
        total_capital=1000.0,
    )
    plan.allocations.append(
        StrategyAllocation(
            strategy_id="trend",
            allocation_percent=100.0,
            allocation_amount=1000.0,
            confidence=1.0,
            expected_risk=0.0,
            rationale="test",
        )
    )

    path = audit.write_plan(plan)

    assert path.exists()

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["risk_profile"] == "BALANCED"
    assert data["market_regime"] == "TRENDING"
    assert data["total_allocated_percent"] == 100.0
    assert len(data["allocations"]) == 1
