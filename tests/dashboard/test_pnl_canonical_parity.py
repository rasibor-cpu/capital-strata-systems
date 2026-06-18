from __future__ import annotations

import sys
from decimal import Decimal

from dashboard.runtime.summary_builders.pnl_summary_builder import PnLSummaryBuilder
from engine.ledger import CANONICAL_PNL_SOURCE
from engine.ledger.pnl_snapshot_adapter import CanonicalPnLSnapshotContract


def _canonical_adapter_summary() -> dict:
    canonical_output = CanonicalPnLSnapshotContract(
        realized_pnl=Decimal("50.0"),
        unrealized_pnl=Decimal("30.0"),
        net_pnl=Decimal("80.0"),
        equity=Decimal("1080.0"),
        peak_equity=Decimal("1100.0"),
        current_drawdown=Decimal("0.01818181818181818"),
        max_drawdown=Decimal("0.02"),
        asset_realized_pnl={
            "CRYPTO": Decimal("40.0"),
            "FX": Decimal("10.0"),
        },
        asset_unrealized_pnl={
            "CRYPTO": Decimal("25.0"),
            "FX": Decimal("5.0"),
        },
        open_positions=2,
        closed_positions=1,
        source=CANONICAL_PNL_SOURCE,
    ).to_runtime_dict()

    return PnLSummaryBuilder().build(
        account_state={"equity": 0.0},
        position_state=canonical_output,
    )


def test_dashboard_consumes_canonical_adapter_output() -> None:
    summary = _canonical_adapter_summary()

    assert summary["realized_pnl"] == 50.0
    assert summary["unrealized_pnl"] == 30.0
    assert summary["net_pnl"] == 80.0
    assert summary["asset_realized_pnl"] == {
        "CRYPTO": 40.0,
        "FX": 10.0,
    }
    assert summary["asset_unrealized_pnl"] == {
        "CRYPTO": 25.0,
        "FX": 5.0,
    }


def test_dashboard_does_not_report_legacy_position_state_as_source() -> None:
    summary = _canonical_adapter_summary()

    # The builder must pass through the source from canonical contract
    assert summary["source"] == CANONICAL_PNL_SOURCE
    assert summary["source"] != "LEGACY_POSITION_STATE"

    # Even with an empty position state, the default source is CANONICAL_PNL_SOURCE
    empty_summary = PnLSummaryBuilder().build(None, None)
    assert empty_summary["source"] == CANONICAL_PNL_SOURCE


def test_dashboard_pnl_totals_match_canonical_realized_and_unrealized_pnl() -> None:
    summary = _canonical_adapter_summary()
    assert summary["net_pnl"] == summary["realized_pnl"] + summary["unrealized_pnl"]
