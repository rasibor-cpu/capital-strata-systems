from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.executive_intelligence.freshness_policy import gate_config, load_freshness_policy
from backend.runtime.coinbase_live_read_only_balance_promotion import (
    ALLOWED_PROMOTION_MODES,
    SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY,
    apply_coinbase_balance_only_promotion,
    coinbase_balance_only_promotion_allowed,
    evaluate_canonical_broker_snapshot_freshness,
    proven_independent_pnl_evidence,
    proven_independent_position_evidence,
    resolve_broker_snapshot_max_age_seconds,
)
from dashboard.runtime.frontend_contract import build_frontend_payload


NOW = datetime(2026, 9, 4, 20, 0, tzinfo=timezone.utc)


def _canonical_max_age() -> float:
    policy = load_freshness_policy()
    cfg = gate_config(policy, "broker_snapshot")
    return float(cfg["max_age_seconds"])


def _snapshot(**overrides):
    payload = {
        "balances_loaded": True,
        "cash": 250.5,
        "equity": 260.25,
        "buying_power": 240.0,
        "available_balance": 240.0,
        "margin_available": 240.0,
        "margin_required": 0.0,
        "currency": "CAD",
        "timestamp": "2026-09-04T20:00:00+00:00",
    }
    payload.update(overrides)
    return payload


def _validation(snapshot=None, **overrides):
    snap = snapshot if snapshot is not None else _snapshot()
    payload = {
        "validation_status": "PASS",
        "balances_loaded": True,
        "broker_validation": {
            "validation_status": "PASS",
            "balances_loaded": True,
            "canonical_account_snapshot": snap,
        },
    }
    payload.update(overrides)
    return payload


def test_promotion_consumes_canonical_broker_snapshot_policy() -> None:
    decision = resolve_broker_snapshot_max_age_seconds()
    assert decision["ok"] is True
    assert decision["max_age_seconds"] == _canonical_max_age()
    assert decision["max_age_seconds"] == float(
        gate_config(load_freshness_policy(), "broker_snapshot")["max_age_seconds"]
    )


def test_freshness_exact_canonical_boundary_is_fresh_and_over_is_stale() -> None:
    max_age = _canonical_max_age()
    exact = evaluate_canonical_broker_snapshot_freshness(
        {"timestamp": (NOW - timedelta(seconds=max_age)).isoformat()},
        now=NOW,
    )
    assert exact["ok"] is True
    assert exact["reason"] == "fresh"
    assert exact["max_age_seconds"] == max_age

    stale = evaluate_canonical_broker_snapshot_freshness(
        {"timestamp": (NOW - timedelta(seconds=max_age + 1)).isoformat()},
        now=NOW,
    )
    assert stale["ok"] is False
    assert stale["reason"] == "stale_timestamp"
    assert stale["max_age_seconds"] == max_age


def test_freshness_uses_injected_policy_not_hardcoded_threshold() -> None:
    policy = {"gates": {"broker_snapshot": {"max_age_seconds": 90}}}
    fresh = evaluate_canonical_broker_snapshot_freshness(
        {"timestamp": (NOW - timedelta(seconds=90)).isoformat()},
        now=NOW,
        policy=policy,
    )
    stale = evaluate_canonical_broker_snapshot_freshness(
        {"timestamp": (NOW - timedelta(seconds=91)).isoformat()},
        now=NOW,
        policy=policy,
    )
    assert fresh["ok"] is True
    assert stale["ok"] is False
    assert stale["reason"] == "stale_timestamp"
    assert stale["max_age_seconds"] == 90.0


def test_freshness_fails_closed_for_missing_malformed_naive_and_future() -> None:
    assert evaluate_canonical_broker_snapshot_freshness({}, now=NOW)["reason"] == "missing_canonical_account_snapshot"
    assert evaluate_canonical_broker_snapshot_freshness({"cash": 1}, now=NOW)["reason"] == "missing_timestamp"
    assert (
        evaluate_canonical_broker_snapshot_freshness({"timestamp": "not-a-time"}, now=NOW)["reason"]
        == "malformed_timestamp"
    )
    assert (
        evaluate_canonical_broker_snapshot_freshness({"timestamp": "2026-09-04T20:00:00"}, now=NOW)["reason"]
        == "naive_timestamp"
    )
    assert (
        evaluate_canonical_broker_snapshot_freshness({"timestamp": "2026-09-04T21:00:00+00:00"}, now=NOW)["reason"]
        == "future_timestamp"
    )
    fresh = evaluate_canonical_broker_snapshot_freshness({"timestamp": NOW.isoformat()}, now=NOW)
    assert fresh["ok"] is True


def test_freshness_fails_closed_on_unusable_policy_config() -> None:
    cases = [
        ({}, "policy_policy_missing"),
        ({"gates": "nope"}, "policy_policy_malformed"),
        ({"gates": {}}, "policy_broker_snapshot_gate_missing"),
        ({"gates": {"broker_snapshot": "nope"}}, "policy_broker_snapshot_gate_malformed"),
        ({"gates": {"broker_snapshot": {}}}, "policy_max_age_missing"),
        ({"gates": {"broker_snapshot": {"max_age_seconds": "abc"}}}, "policy_max_age_unusable"),
        ({"gates": {"broker_snapshot": {"max_age_seconds": 0}}}, "policy_max_age_unusable"),
        ({"gates": {"broker_snapshot": {"max_age_seconds": -5}}}, "policy_max_age_unusable"),
        ({"gates": {"broker_snapshot": {"max_age_seconds": True}}}, "policy_max_age_unusable"),
    ]
    for policy, reason in cases:
        result = evaluate_canonical_broker_snapshot_freshness(
            {"timestamp": NOW.isoformat()},
            now=NOW,
            policy=policy,
        )
        assert result["ok"] is False, policy
        assert result["reason"] == reason, (policy, result["reason"])


def test_promotion_denied_when_policy_unusable() -> None:
    denied = coinbase_balance_only_promotion_allowed(
        selected_broker="COINBASE",
        canonical_mode="LIVE_READ_ONLY",
        coinbase_validation=_validation(),
        now=NOW,
        policy={"gates": {"broker_snapshot": {"max_age_seconds": "nope"}}},
    )
    assert denied["allowed"] is False
    assert any(reason.startswith("freshness_policy_") for reason in denied["reasons"])


def test_promotion_gates_require_coinbase_live_read_only_pass_and_fresh_snapshot() -> None:
    assert ALLOWED_PROMOTION_MODES == frozenset({"LIVE_READ_ONLY"})

    denied = coinbase_balance_only_promotion_allowed(
        selected_broker="OANDA",
        canonical_mode="LIVE_READ_ONLY",
        coinbase_validation=_validation(),
        now=NOW,
    )
    assert denied["allowed"] is False
    assert "selected_broker_not_coinbase" in denied["reasons"]

    paper = coinbase_balance_only_promotion_allowed(
        selected_broker="COINBASE",
        canonical_mode="PAPER",
        coinbase_validation=_validation(),
        now=NOW,
    )
    assert paper["allowed"] is False
    assert "canonical_mode_not_live_read_only" in paper["reasons"]

    live = coinbase_balance_only_promotion_allowed(
        selected_broker="COINBASE",
        canonical_mode="LIVE",
        coinbase_validation=_validation(),
        now=NOW,
    )
    assert live["allowed"] is False
    assert "canonical_mode_not_live_read_only" in live["reasons"]

    failed = coinbase_balance_only_promotion_allowed(
        selected_broker="COINBASE",
        canonical_mode="LIVE_READ_ONLY",
        coinbase_validation=_validation(
            validation_status="FAIL_CLOSED",
            broker_validation={
                "validation_status": "FAIL_CLOSED",
                "balances_loaded": True,
                "canonical_account_snapshot": _snapshot(),
            },
        ),
        now=NOW,
    )
    assert failed["allowed"] is False

    allowed = coinbase_balance_only_promotion_allowed(
        selected_broker="COINBASE",
        canonical_mode="LIVE_READ_ONLY",
        coinbase_validation=_validation(),
        now=NOW,
    )
    assert allowed["allowed"] is True
    assert allowed["source"] == SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY


def test_promoted_balances_do_not_imply_zero_pnl_or_positions() -> None:
    raw = apply_coinbase_balance_only_promotion(
        {
            "account_summary": {},
            "pnl_summary": {},
            "position_state": {},
            "open_positions": {},
        },
        selected_broker="COINBASE",
        canonical_mode="LIVE_READ_ONLY",
        coinbase_validation=_validation(),
        position_evidence=False,
        pnl_evidence=False,
        now=NOW,
    )
    assert raw["account_summary"]["cash_balance"] == 250.5
    assert raw["account_summary"]["source"] == SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY
    assert raw["pnl_summary"]["realized_pnl"] == 0.0
    assert raw["pnl_summary"]["realized_pnl_availability"] == "UNAVAILABLE"
    assert raw["position_state"]["open_count"] == 0
    assert raw["position_state"]["open_count_availability"] == "UNAVAILABLE"

    frontend = build_frontend_payload(raw)
    pnl = frontend["sections"]["pnl_summary"]
    positions = frontend["sections"]["positions"]
    account = frontend["sections"]["account_summary"]
    assert account["cash_balance"] == 250.5
    assert account["cash_balance_availability"] == "AVAILABLE"
    assert isinstance(pnl["realized_pnl"], float)
    assert pnl["realized_pnl_availability"] == "UNAVAILABLE"
    assert isinstance(positions["total"], int)
    assert positions["total_availability"] == "UNAVAILABLE"
    assert pnl["source"] == SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY


def test_presence_and_empty_list_are_not_independent_evidence() -> None:
    assert proven_independent_pnl_evidence({"realized_pnl": 0.0, "source": "LAUNCHER_ACCOUNT_ARTIFACT"}) is False
    assert proven_independent_pnl_evidence(True) is False
    assert proven_independent_position_evidence({"positions": [{"symbol": "BTC-USD"}], "source": "LAUNCHER_POSITION_ARTIFACT"}) is False
    assert proven_independent_position_evidence([]) is False
    assert proven_independent_position_evidence({"positions": [], "source": "COINBASE_LIVE_READ_ONLY_POSITIONS"}) is False


def test_explicit_compatible_fresh_evidence_is_retained() -> None:
    raw = apply_coinbase_balance_only_promotion(
        {
            "account_summary": {},
            "pnl_summary": {
                "realized_pnl": 12.5,
                "unrealized_pnl": -1.0,
                "net_pnl": 11.5,
                "account_equity": 260.25,
                "realized_pnl_availability": "AVAILABLE",
                "unrealized_pnl_availability": "AVAILABLE",
                "net_pnl_availability": "AVAILABLE",
                "account_equity_availability": "AVAILABLE",
                "availability_state": "AVAILABLE",
                "source": "COINBASE_LIVE_READ_ONLY_PNL",
                "timestamp": NOW.isoformat(),
                "validation_status": "PASS",
            },
            "position_state": {
                "open_count": 1,
                "open_count_availability": "AVAILABLE",
                "positions": [{"symbol": "BTC-USD", "qty": 0.01}],
                "source": "COINBASE_LIVE_READ_ONLY_POSITIONS",
                "timestamp": NOW.isoformat(),
                "validation_status": "PASS",
            },
            "open_positions": {"total": 1, "total_availability": "AVAILABLE"},
        },
        selected_broker="COINBASE",
        canonical_mode="LIVE_READ_ONLY",
        coinbase_validation=_validation(),
        pnl_evidence={
            "source": "COINBASE_LIVE_READ_ONLY_PNL",
            "timestamp": NOW.isoformat(),
            "validation_status": "PASS",
        },
        position_evidence={
            "source": "COINBASE_LIVE_READ_ONLY_POSITIONS",
            "timestamp": NOW.isoformat(),
            "validation_status": "PASS",
        },
        now=NOW,
    )
    assert raw["pnl_summary"]["realized_pnl"] == 12.5
    assert raw["pnl_summary"]["realized_pnl_availability"] == "AVAILABLE"
    assert raw["pnl_summary"]["source"] == "COINBASE_LIVE_READ_ONLY_PNL"
    assert raw["position_state"]["open_count"] == 1
    assert raw["position_state"]["open_count_availability"] == "AVAILABLE"
    assert raw["position_state"]["source"] == "COINBASE_LIVE_READ_ONLY_POSITIONS"


def test_true_flags_still_require_compatible_fresh_payload_provenance() -> None:
    raw = apply_coinbase_balance_only_promotion(
        {
            "pnl_summary": {
                "realized_pnl": 0.0,
                "unrealized_pnl": 0.0,
                "net_pnl": 0.0,
                "account_equity": 0.0,
                "realized_pnl_availability": "AVAILABLE",
                "source": "LAUNCHER_ACCOUNT_ARTIFACT",
            },
            "position_state": {
                "open_count": 2,
                "open_count_availability": "AVAILABLE",
                "positions": [{"symbol": "ETH-USD"}],
                "source": "LAUNCHER_POSITION_ARTIFACT",
            },
            "open_positions": {"total": 2, "total_availability": "AVAILABLE"},
        },
        selected_broker="COINBASE",
        canonical_mode="LIVE_READ_ONLY",
        coinbase_validation=_validation(),
        pnl_evidence=True,
        position_evidence=True,
        now=NOW,
    )
    assert raw["pnl_summary"]["realized_pnl"] == 0.0
    assert raw["pnl_summary"]["realized_pnl_availability"] == "UNAVAILABLE"
    assert raw["pnl_summary"]["source"] == SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY
    assert raw["position_state"]["open_count_availability"] == "UNAVAILABLE"
    assert raw["position_state"]["source"] == SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY
