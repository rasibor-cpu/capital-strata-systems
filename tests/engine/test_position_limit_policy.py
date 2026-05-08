from __future__ import annotations

from engine.governance.position_limit_policy import (
    PositionLimitConfig,
    PositionLimitPolicy,
    evaluate_position_limits,
)


def test_total_position_cap_blocks_new_position() -> None:
    policy = PositionLimitPolicy(
        PositionLimitConfig(
            max_total_open_positions=3,
            max_open_per_asset_class=3,
            max_new_positions_per_cycle=2,
        )
    )

    decision = policy.evaluate(
        {
            "positions": [
                {"symbol": "EUR_USD", "asset_class": "FX"},
                {"symbol": "GBP_USD", "asset_class": "FX"},
                {"symbol": "BTC-USD", "asset_class": "CRYPTO"},
            ]
        },
        asset_class="FX",
        new_positions_requested=1,
    )

    assert decision.allowed is False
    assert decision.reason == "total_position_limit_reached"
    assert decision.total_open_positions == 3


def test_per_asset_position_cap_blocks_new_position() -> None:
    policy = PositionLimitPolicy(
        PositionLimitConfig(
            max_total_open_positions=10,
            max_open_per_asset_class=2,
            max_new_positions_per_cycle=2,
        )
    )

    decision = policy.evaluate(
        {
            "open_count": 2,
            "asset_counts": {"fx": 2},
        },
        asset_class="FX",
        new_positions_requested=1,
    )

    assert decision.allowed is False
    assert decision.reason == "asset_class_position_limit_reached"
    assert decision.open_positions_by_asset_class == {"FX": 2}


def test_new_positions_per_cycle_cap_blocks_batch() -> None:
    decision = evaluate_position_limits(
        {
            "open_positions": {
                "total": 0,
                "by_asset": {},
            }
        },
        asset_class="CRYPTO",
        new_positions_requested=3,
        config=PositionLimitConfig(
            max_total_open_positions=10,
            max_open_per_asset_class=5,
            max_new_positions_per_cycle=2,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == "new_positions_per_cycle_limit_reached"


def test_missing_payload_fails_closed_without_throwing() -> None:
    decision = evaluate_position_limits(
        None,
        asset_class="FX",
        new_positions_requested=1,
    )

    assert decision.allowed is False
    assert decision.reason == "positions_payload_missing"
    assert decision.as_dict()["total_open_positions"] == 0


def test_normal_payload_allows_within_limits() -> None:
    decision = evaluate_position_limits(
        {
            "positions": [
                {"symbol": "EUR_USD", "asset_class": "FX"},
            ]
        },
        asset_class="CRYPTO",
        new_positions_requested=1,
        config=PositionLimitConfig(
            max_total_open_positions=3,
            max_open_per_asset_class=2,
            max_new_positions_per_cycle=1,
        ),
    )

    assert decision.allowed is True
    assert decision.reason == "allowed"
    assert decision.total_open_positions == 1
    assert decision.open_positions_by_asset_class == {"FX": 1}
