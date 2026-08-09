from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

import pytest

from backend.runtime.live_authority_lease import (
    LIVE_AUTHORITY_ACTION,
    LIVE_AUTHORITY_SCOPE,
    LiveAuthorityLeaseRegistry,
    evaluate_live_authority_lease_evidence,
)
from backend.runtime.live_execution_authority import (
    AUTHORITY_CONDITIONS,
    evaluate_live_execution_authority,
)


BASE = datetime(2026, 8, 9, 10, 0, tzinfo=timezone.utc)


def clock_at(value: datetime):
    return lambda: value


def ready_evidence(lease):
    return {
        "operator_requested_live": True,
        "broker_readiness": {
            "broker_name": "OANDA",
            "mode": "LIVE",
            "credentials_present": True,
            "authenticated": True,
            "connected": True,
            "account_loaded": True,
            "market_data_ready": True,
            "execution_enabled": True,
        },
        "broker_mode": "LIVE",
        "live_micro_pilot_state": "ARMED",
        "capital_governor": "PASS",
        "unified_trade_gate": "PASS",
        "margin_gate": "PASS",
        "anti_bleed_guard": "PASS",
        "rbac": "PASS",
        "kill_switch": "CLEAR",
        "go_no_go": "GO",
        "live_authority_lease": lease,
    }


def issue_public(tmp_path=None, *, now=BASE, ttl=60):
    durable = tmp_path / "leases.json" if tmp_path else None
    registry = LiveAuthorityLeaseRegistry(
        durable_path=durable,
        now=clock_at(now),
    )
    token, lease = registry.issue(
        broker="OANDA",
        environment="LIVE",
        ttl_seconds=ttl,
    )
    return registry, token, lease.public_dict()


def test_live_authority_requires_dedicated_lease_condition():
    assert any(k == "live_authority_lease_valid" for k, _ in AUTHORITY_CONDITIONS)


def test_missing_live_authority_lease_fails_closed():
    evidence = ready_evidence(None)
    decision = evaluate_live_execution_authority(evidence)
    assert decision.execution_authority is False
    assert "live_authority_lease_valid" in decision.failed_conditions


def test_valid_live_authority_lease_evidence():
    _registry, _token, lease = issue_public()
    status = evaluate_live_authority_lease_evidence(
        lease,
        broker="OANDA",
        environment="LIVE",
        now=BASE + timedelta(seconds=1),
    )
    assert status.valid is True


def test_expired_live_authority_lease_is_blocked():
    _registry, _token, lease = issue_public(ttl=30)
    status = evaluate_live_authority_lease_evidence(
        lease,
        broker="OANDA",
        environment="LIVE",
        now=BASE + timedelta(seconds=31),
    )
    assert status.valid is False
    assert status.reason == "LIVE_AUTHORITY_LEASE_EXPIRED"


@pytest.mark.parametrize("ttl", [0, -1, 301])
def test_invalid_ttl_rejected(ttl):
    registry = LiveAuthorityLeaseRegistry(now=clock_at(BASE))
    with pytest.raises(ValueError):
        registry.issue(
            broker="OANDA",
            environment="LIVE",
            ttl_seconds=ttl,
        )


def test_wrong_broker_blocked():
    _registry, _token, lease = issue_public()
    status = evaluate_live_authority_lease_evidence(
        lease,
        broker="COINBASE",
        environment="LIVE",
        now=BASE + timedelta(seconds=1),
    )
    assert status.valid is False
    assert status.reason == "LIVE_AUTHORITY_BROKER_MISMATCH"


def test_wrong_environment_blocked():
    _registry, _token, lease = issue_public()
    status = evaluate_live_authority_lease_evidence(
        lease,
        broker="OANDA",
        environment="PRACTICE",
        now=BASE + timedelta(seconds=1),
    )
    assert status.valid is False
    assert status.reason == "LIVE_AUTHORITY_ENVIRONMENT_MISMATCH"


def test_wrong_action_blocked():
    _registry, _token, lease = issue_public()
    lease["action"] = "READ_ONLY"
    status = evaluate_live_authority_lease_evidence(
        lease,
        broker="OANDA",
        environment="LIVE",
        now=BASE + timedelta(seconds=1),
    )
    assert status.valid is False


def test_single_use_replay_blocked():
    registry, token, lease = issue_public()
    first = registry.consume(
        lease["lease_id"],
        token,
        broker="OANDA",
        environment="LIVE",
        now=BASE + timedelta(seconds=1),
    )
    second = registry.consume(
        lease["lease_id"],
        token,
        broker="OANDA",
        environment="LIVE",
        now=BASE + timedelta(seconds=2),
    )
    assert first.valid is True
    assert second.valid is False
    assert second.reason == "LIVE_AUTHORITY_LEASE_CONSUMED"


def test_revocation_blocks_authority():
    registry, token, lease = issue_public()
    registry.revoke(lease["lease_id"])
    status = registry.validate(
        lease["lease_id"],
        token,
        broker="OANDA",
        environment="LIVE",
        now=BASE + timedelta(seconds=1),
    )
    assert status.valid is False
    assert status.reason == "LIVE_AUTHORITY_LEASE_REVOKED"


def test_restart_does_not_extend_original_expiry(tmp_path):
    durable = tmp_path / "lease.json"
    registry = LiveAuthorityLeaseRegistry(
        durable_path=durable,
        now=clock_at(BASE),
    )
    token, lease = registry.issue(
        broker="OANDA",
        environment="LIVE",
        ttl_seconds=20,
    )

    reloaded = LiveAuthorityLeaseRegistry(
        durable_path=durable,
        now=clock_at(BASE + timedelta(seconds=21)),
    )

    status = reloaded.validate(
        lease.lease_id,
        token,
        broker="OANDA",
        environment="LIVE",
    )
    assert status.valid is False
    assert status.reason == "LIVE_AUTHORITY_LEASE_EXPIRED"


def test_ambiguous_persistence_fails_closed(tmp_path):
    durable = tmp_path / "lease.json"
    durable.write_text("{not-json", encoding="utf-8")

    registry = LiveAuthorityLeaseRegistry(
        durable_path=durable,
        now=clock_at(BASE),
    )

    status = registry.validate(
        "missing",
        "token",
        broker="OANDA",
        environment="LIVE",
    )
    assert status.valid is False


def test_read_only_phase189_shape_cannot_satisfy_live_lease():
    readonly = {
        "ttl_id": "ttl-demo",
        "scope": "READ_ONLY_OPERATIONAL",
        "broker_type": "OANDA",
        "issued_at": "2026-08-09T10:00:00Z",
        "expires_at": "2026-08-09T10:01:00Z",
        "trading_authorization": False,
    }
    status = evaluate_live_authority_lease_evidence(
        readonly,
        broker="OANDA",
        environment="LIVE",
        now=BASE + timedelta(seconds=1),
    )
    assert status.valid is False


def test_credentials_and_authentication_alone_do_not_create_authority():
    decision = evaluate_live_execution_authority(
        {
            "operator_requested_live": True,
            "broker_readiness": {
                "broker_name": "OANDA",
                "mode": "LIVE",
                "credentials_present": True,
                "authenticated": True,
                "connected": True,
                "account_loaded": True,
                "market_data_ready": True,
                "execution_enabled": True,
            },
            "broker_mode": "LIVE",
            "live_micro_pilot_state": "ARMED",
            "capital_governor": "PASS",
            "unified_trade_gate": "PASS",
            "margin_gate": "PASS",
            "anti_bleed_guard": "PASS",
            "rbac": "PASS",
            "kill_switch": "CLEAR",
            "go_no_go": "GO",
        }
    )
    assert decision.execution_authority is False
    assert "live_authority_lease_valid" in decision.failed_conditions


def test_lease_cannot_bypass_antibleed_or_other_existing_conditions():
    _registry, _token, lease = issue_public()
    evidence = ready_evidence(lease)
    evidence["anti_bleed_guard"] = "FAIL"

    decision = evaluate_live_execution_authority(evidence)

    assert decision.execution_authority is False
    assert "anti_bleed_guard_pass" in decision.failed_conditions


def test_static_contract_has_no_network_or_order_capability():
    from pathlib import Path

    source = Path("backend/runtime/live_authority_lease.py").read_text(
        encoding="utf-8"
    ).lower()

    for forbidden in (
        "requests.",
        "urllib.",
        "socket.",
        "place_order(",
        "submit_order(",
        "broker_secret",
        "credential_loader",
    ):
        assert forbidden not in source