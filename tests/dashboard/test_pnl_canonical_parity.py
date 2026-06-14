from __future__ import annotations

import sys
from decimal import Decimal

from dashboard.runtime.summary_builders.pnl_parity_check import (
    compare_pnl_summary_parity,
)
from dashboard.runtime.summary_builders.pnl_summary_builder import PnLSummaryBuilder
from engine.ledger import CANONICAL_PNL_SOURCE
from engine.ledger.pnl_snapshot_adapter import CanonicalPnLSnapshotContract


def _legacy_dashboard_summary() -> dict:
    return PnLSummaryBuilder().build(
        account_state={"equity": 1080.0},
        position_state={
            "total_realized_pnl": 50.0,
            "total_unrealized_pnl": 30.0,
            "total_exposure": 250.0,
            "winner_count": 2,
            "loser_count": 1,
            "asset_realized_pnl": {
                "CRYPTO": 40.0,
                "FX": 10.0,
            },
            "asset_unrealized_pnl": {
                "CRYPTO": 25.0,
                "FX": 5.0,
            },
            "open_count": 2,
        },
    )


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


def test_dashboard_and_canonical_pnl_parity_matches_core_fields() -> None:
    parity = compare_pnl_summary_parity(
        _legacy_dashboard_summary(),
        _canonical_adapter_summary(),
    )

    assert parity["matches"] is True
    assert parity["field_diffs"] == {
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
        "net_pnl": 0.0,
    }


def test_dashboard_and_canonical_pnl_parity_matches_asset_maps() -> None:
    parity = compare_pnl_summary_parity(
        _legacy_dashboard_summary(),
        _canonical_adapter_summary(),
    )

    assert parity["asset_realized_diffs"] == {
        "CRYPTO": 0.0,
        "FX": 0.0,
    }
    assert parity["asset_unrealized_diffs"] == {
        "CRYPTO": 0.0,
        "FX": 0.0,
    }


def test_dashboard_and_canonical_pnl_parity_preserves_canonical_source() -> None:
    canonical_summary = _canonical_adapter_summary()
    parity = compare_pnl_summary_parity(
        _legacy_dashboard_summary(),
        canonical_summary,
    )

    assert canonical_summary["source"] == CANONICAL_PNL_SOURCE
    assert parity["canonical_source"] == CANONICAL_PNL_SOURCE
    assert parity["canonical_source_expected"] == CANONICAL_PNL_SOURCE


def test_legacy_dashboard_summary_behavior_remains_intact() -> None:
    summary = _legacy_dashboard_summary()

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
    assert summary["source"] == "LEGACY_POSITION_STATE"


def test_parity_helper_does_not_import_live_dashboard_runtime() -> None:
    compare_pnl_summary_parity(
        _legacy_dashboard_summary(),
        _canonical_adapter_summary(),
    )

    assert "scripts.css_live_dashboard" not in sys.modules
