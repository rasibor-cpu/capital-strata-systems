from __future__ import annotations

from dashboard.runtime.dashboard_state_factory import DashboardStateFactory
from dashboard.runtime.runtime_smoke_test import build_smoke_payloads
from dashboard.runtime.state_builders.position_state_builder import PositionStateBuilder
from dashboard.runtime.summary_builders.pnl_summary_builder import PnLSummaryBuilder
from engine.ledger import CANONICAL_PNL_SOURCE


def test_smoke_positions_produce_deterministic_unrealized_pnl_evidence() -> None:
    payloads = build_smoke_payloads()
    position_state = PositionStateBuilder().build(payloads["positions_payload"])

    assert position_state["positions"] == [
        {
            "symbol": "BTC-USD",
            "asset_class": "CRYPTO",
            "side": "LONG",
            "qty": 0.05,
            "entry_price": 65000.0,
            "current_price": 65500.0,
            "exposure": 3275.0,
            "unrealized_pnl": 25.0,
            "realized_pnl": 0.0,
        },
        {
            "symbol": "EUR_USD",
            "asset_class": "FX",
            "side": "SHORT",
            "qty": 1000.0,
            "entry_price": 1.09,
            "current_price": 1.0875,
            "exposure": 1087.5,
            "unrealized_pnl": 2.5,
            "realized_pnl": 0.0,
        },
    ]
    assert position_state["asset_unrealized_pnl"] == {
        "CRYPTO": 25.0,
        "FX": 2.5,
    }
    assert position_state["total_unrealized_pnl"] == 27.5
    assert position_state["total_realized_pnl"] == 0.0
    assert position_state["net_pnl"] == 27.5


def test_pnl_summary_consumes_normalized_position_totals_from_runtime_builder() -> None:
    payloads = build_smoke_payloads()
    position_state = PositionStateBuilder().build(payloads["positions_payload"])

    summary = PnLSummaryBuilder().build(
        account_state=payloads["account_payload"],
        position_state=position_state,
    )

    assert summary["realized_pnl"] == 0.0
    assert summary["unrealized_pnl"] == 27.5
    assert summary["net_pnl"] == 27.5
    assert summary["account_equity"] == 10250.0
    assert summary["open_positions"] == 2
    assert summary["asset_unrealized_pnl"] == {
        "CRYPTO": 25.0,
        "FX": 2.5,
    }


def test_pnl_summary_keeps_realized_and_unrealized_position_totals_separate() -> None:
    position_state = PositionStateBuilder().build(
        {
            "positions": [
                {
                    "symbol": "SPY",
                    "asset_class": "equity",
                    "side": "long",
                    "qty": 2,
                    "entry_price": 100,
                    "current_price": 103,
                    "realized_pnl": 4.0,
                    "unrealized_pnl": 6.0,
                },
                {
                    "symbol": "TLT",
                    "asset_class": "equity",
                    "side": "short",
                    "qty": 1,
                    "entry_price": 90,
                    "current_price": 88,
                    "realized_pnl": -1.0,
                    "unrealized_pnl": 2.0,
                },
            ]
        }
    )

    summary = PnLSummaryBuilder().build(
        account_state={"total_equity": 1008.0},
        position_state=position_state,
    )

    assert summary["realized_pnl"] == 3.0
    assert summary["unrealized_pnl"] == 8.0
    assert summary["net_pnl"] == 11.0


def test_canonical_pnl_fields_take_precedence_over_position_total_aliases() -> None:
    summary = PnLSummaryBuilder().build(
        account_state={"total_equity": 1000.0},
        position_state={
            "realized_pnl": 5.0,
            "total_realized_pnl": 500.0,
            "unrealized_pnl": 7.0,
            "total_unrealized_pnl": 700.0,
            "source": CANONICAL_PNL_SOURCE,
        },
    )

    assert summary["realized_pnl"] == 5.0
    assert summary["unrealized_pnl"] == 7.0
    assert summary["net_pnl"] == 12.0
    assert summary["source"] == CANONICAL_PNL_SOURCE


def test_dashboard_factory_runtime_snapshot_pnl_matches_smoke_position_totals() -> None:
    payloads = build_smoke_payloads()

    state = DashboardStateFactory().build(
        account_payload=payloads["account_payload"],
        positions_payload=payloads["positions_payload"],
        market_payload=payloads["market_payload"],
        governance_payload=payloads["governance_payload"],
        risk_payload=payloads["risk_payload"],
        execution_payload=payloads["execution_payload"],
        session_payload=payloads["session_payload"],
        diagnostics_payload=payloads["diagnostics_payload"],
    )

    summary = state.last_scan_results["pnl_summary"]
    assert state.unrealized_pnl == 27.5
    assert summary["unrealized_pnl"] == 27.5
    assert summary["net_pnl"] == 27.5
