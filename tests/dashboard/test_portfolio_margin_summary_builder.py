import pytest
from dashboard.runtime.summary_builders.portfolio_margin_summary_builder import PortfolioMarginSummaryBuilder
from engine.risk.portfolio_margin_snapshot import PortfolioMarginSnapshot
from engine.risk.margin_state import MarginState

@pytest.fixture
def builder():
    return PortfolioMarginSummaryBuilder()

def test_builder_rejects_invalid_snapshot(builder):
    """Test 5: Builder rejects invalid snapshot."""
    with pytest.raises(ValueError, match="Invalid snapshot: Must be an instance of PortfolioMarginSnapshot"):
        builder.build({"portfolio_equity": 1000})

def test_builder_rejects_none_snapshot(builder):
    """Test 6: Builder rejects None snapshot."""
    with pytest.raises(ValueError, match="Invalid snapshot: Must be an instance of PortfolioMarginSnapshot"):
        builder.build(None)

def test_normal_portfolio_state(builder):
    """Test 1: Normal portfolio state."""
    snapshot = PortfolioMarginSnapshot(
        portfolio_equity=100000.0,
        portfolio_buying_power=200000.0,
        portfolio_margin_used=10000.0,
        portfolio_margin_available=90000.0,
        portfolio_risk_state=MarginState.NORMAL,
        broker_count=2
    )
    result = builder.build(snapshot)
    
    assert result["portfolio_equity"] == 100000.0
    assert result["portfolio_buying_power"] == 200000.0
    assert result["portfolio_margin_used"] == 10000.0
    assert result["portfolio_margin_available"] == 90000.0
    assert result["portfolio_risk_state"] == "NORMAL"
    assert result["broker_count"] == 2
    assert result["risk_banner"] == "Portfolio Margin Healthy"

def test_warning_portfolio_state(builder):
    """Test 2: Warning portfolio state."""
    snapshot = PortfolioMarginSnapshot(
        portfolio_equity=100000.0,
        portfolio_buying_power=50000.0,
        portfolio_margin_used=60000.0,
        portfolio_margin_available=40000.0,
        portfolio_risk_state=MarginState.WARNING,
        broker_count=2
    )
    result = builder.build(snapshot)
    assert result["portfolio_risk_state"] == "WARNING"
    assert result["risk_banner"] == "Portfolio Margin Warning"

def test_critical_portfolio_state(builder):
    """Test 3: Critical portfolio state."""
    snapshot = PortfolioMarginSnapshot(
        portfolio_equity=100000.0,
        portfolio_buying_power=10000.0,
        portfolio_margin_used=90000.0,
        portfolio_margin_available=10000.0,
        portfolio_risk_state=MarginState.CRITICAL,
        broker_count=2
    )
    result = builder.build(snapshot)
    assert result["portfolio_risk_state"] == "CRITICAL"
    assert result["risk_banner"] == "Margin Stress Detected"

def test_liquidation_portfolio_state(builder):
    """Test 4: Liquidation portfolio state."""
    snapshot = PortfolioMarginSnapshot(
        portfolio_equity=100000.0,
        portfolio_buying_power=0.0,
        portfolio_margin_used=105000.0,
        portfolio_margin_available=0.0,
        portfolio_risk_state=MarginState.LIQUIDATION_RISK,
        broker_count=2
    )
    result = builder.build(snapshot)
    assert result["portfolio_risk_state"] == "LIQUIDATION_RISK"
    assert result["risk_banner"] == "Immediate Margin Intervention Required"

def test_banner_mapping_validation(builder):
    """Test 7: Banner mapping validation."""
    # We already tested NORMAL, WARNING, CRITICAL, LIQUIDATION_RISK in the above tests.
    # We just need to ensure RESTRICTED maps properly for full coverage of the 5 states.
    snapshot = PortfolioMarginSnapshot(
        portfolio_equity=100000.0,
        portfolio_buying_power=0.0,
        portfolio_margin_used=80000.0,
        portfolio_margin_available=20000.0,
        portfolio_risk_state=MarginState.RESTRICTED,
        broker_count=1
    )
    result = builder.build(snapshot)
    assert result["portfolio_risk_state"] == "RESTRICTED"
    assert result["risk_banner"] == "Margin Restrictions Active"
