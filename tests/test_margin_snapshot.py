from engine.risk.margin_snapshot import MarginSnapshot
from engine.risk.margin_state import MarginState

def test_margin_snapshot_creation():
    snapshot = MarginSnapshot(
        broker="TEST",
        account_id="123",
        timestamp="2026-06-17T00:00:00Z",
        equity=10000.0,
        cash=10000.0,
        buying_power=5000.0,
        maintenance_margin=2500.0,
        initial_margin=5000.0,
        margin_used=5000.0,
        margin_available=5000.0,
        margin_ratio=0.5,
        margin_state=MarginState.NORMAL
    )
    assert snapshot.broker == "TEST"
    assert snapshot.margin_state == MarginState.NORMAL
    assert snapshot.buying_power == 5000.0
