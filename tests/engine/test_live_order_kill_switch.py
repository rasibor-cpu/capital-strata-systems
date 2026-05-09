from __future__ import annotations

from engine.execution.live_order_kill_switch import evaluate_live_order_kill_switch


def test_live_order_kill_switch_clear_by_default() -> None:
    decision = evaluate_live_order_kill_switch({}, env={})

    assert decision.blocked is False
    assert decision.reason == "live_order_kill_switch_clear"
    assert decision.as_dict()["source"] == "default"


def test_live_order_kill_switch_blocks_from_env() -> None:
    decision = evaluate_live_order_kill_switch(
        {},
        env={"CSS_LIVE_ORDER_KILL_SWITCH": "true"},
    )

    assert decision.blocked is True
    assert decision.reason == "env_kill_switch_engaged"
    assert decision.source == "CSS_LIVE_ORDER_KILL_SWITCH"


def test_live_order_kill_switch_blocks_from_mobile_controls() -> None:
    decision = evaluate_live_order_kill_switch(
        {"live_order_kill_switch": True},
        env={},
    )

    assert decision.blocked is True
    assert decision.reason == "mobile_control_kill_switch_engaged"
    assert decision.source == "mobile_controls"
