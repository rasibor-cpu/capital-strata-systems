"""AR-006 regression: paper trading authority honesty."""

from backend.engine.css_trading_engine import CSSTradingEngine


def test_css_trading_engine_is_non_authoritative():
    assert CSSTradingEngine.AUTHORITATIVE_PAPER_ENGINE is False
    engine = CSSTradingEngine()
    assert engine.AUTHORITATIVE_PAPER_ENGINE is False
