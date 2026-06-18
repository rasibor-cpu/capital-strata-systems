from engine.risk.broker_margin_contract import (
    BrokerMarginProvider,
    BrokerMarginSnapshot,
)


def test_margin_snapshot_fields():
    snapshot = BrokerMarginSnapshot(
        broker_name="TEST",
        account_id="ABC123",
        required_margin=1000.0,
        available_margin=5000.0,
        free_margin=4000.0,
        margin_utilization_pct=20.0,
        margin_source="BROKER",
        timestamp="2026-06-12T00:00:00",
    )

    assert snapshot.broker_name == "TEST"
    assert snapshot.required_margin == 1000.0
    assert snapshot.available_margin == 5000.0
    assert snapshot.free_margin == 4000.0


class DummyProvider(BrokerMarginProvider):
    def get_margin_snapshot(self):
        return BrokerMarginSnapshot(
            broker_name="TEST",
            account_id="ABC123",
            required_margin=0.0,
            available_margin=1000.0,
            free_margin=1000.0,
            margin_utilization_pct=0.0,
            margin_source="SIMULATED",
            timestamp="2026-06-12T00:00:00",
        )


def test_provider_contract():
    provider = DummyProvider()

    snapshot = provider.get_margin_snapshot()

    assert snapshot.broker_name == "TEST"
    assert snapshot.margin_source == "SIMULATED"