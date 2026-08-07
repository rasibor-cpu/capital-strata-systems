from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import socket
import threading

import pytest

from backend.app.live_authorization_ttl import (
    LIVE_ENVIRONMENT,
    TTL_SECONDS,
    LiveAuthorizationScope,
    LiveAuthorizationTTLGate,
)


def _scope(**overrides: object) -> LiveAuthorizationScope:
    payload = {
        "order_identity": "order-001",
        "environment": LIVE_ENVIRONMENT,
        "broker": "COINBASE",
        "account": "ACC-1",
        "symbol": "BTC-USD",
        "side": "BUY",
        "authoritative_exposure_amount": "10.00",
        "authoritative_exposure_currency": "CAD",
        "quantity": "1",
        "order_type": "MARKET",
        "limit_price": "",
    }
    payload.update(overrides)
    return LiveAuthorizationScope.from_mapping(payload)


def test_valid_authorization_at_issuance() -> None:
    gate = LiveAuthorizationTTLGate()
    issued_at = datetime(2026, 8, 7, 12, 0, 0, tzinfo=timezone.utc)
    scope = _scope()
    auth = gate.issue_authorization(scope, authorization_id="auth-1", issuance_time=issued_at)

    decision = gate.validate_and_consume("auth-1", scope, evaluation_time=issued_at)

    assert auth["ttl_seconds"] == TTL_SECONDS
    assert decision.approved is True
    assert decision.reason == "approved"


def test_valid_immediately_before_expiry() -> None:
    gate = LiveAuthorizationTTLGate()
    issued_at = datetime(2026, 8, 7, 12, 0, 0, tzinfo=timezone.utc)
    scope = _scope()
    gate.issue_authorization(scope, authorization_id="auth-2", issuance_time=issued_at)

    decision = gate.validate_and_consume(
        "auth-2",
        scope,
        evaluation_time=issued_at + timedelta(seconds=59, milliseconds=999),
    )

    assert decision.approved is True


def test_expired_exactly_at_60_seconds() -> None:
    gate = LiveAuthorizationTTLGate()
    issued_at = datetime(2026, 8, 7, 12, 0, 0, tzinfo=timezone.utc)
    scope = _scope()
    gate.issue_authorization(scope, authorization_id="auth-3", issuance_time=issued_at)

    decision = gate.validate_and_consume(
        "auth-3",
        scope,
        evaluation_time=issued_at + timedelta(seconds=60),
    )

    assert decision.approved is False
    assert decision.reason == "authorization_expired"


def test_expired_after_60_seconds() -> None:
    gate = LiveAuthorizationTTLGate()
    issued_at = datetime(2026, 8, 7, 12, 0, 0, tzinfo=timezone.utc)
    scope = _scope()
    gate.issue_authorization(scope, authorization_id="auth-4", issuance_time=issued_at)

    decision = gate.validate_and_consume(
        "auth-4",
        scope,
        evaluation_time=issued_at + timedelta(seconds=61),
    )

    assert decision.approved is False
    assert decision.reason == "authorization_expired"


def test_future_issued_authorization_fails_closed() -> None:
    gate = LiveAuthorizationTTLGate()
    issued_at = datetime(2026, 8, 7, 12, 0, 30, tzinfo=timezone.utc)
    scope = _scope()
    gate.issue_authorization(scope, authorization_id="auth-5", issuance_time=issued_at)

    decision = gate.validate_and_consume(
        "auth-5",
        scope,
        evaluation_time=issued_at - timedelta(seconds=1),
    )

    assert decision.approved is False
    assert decision.reason == "future_issued_at"


@pytest.mark.parametrize(
    ("mutator", "reason"),
    [
        (lambda record: setattr(record, "issued_at", ""), "missing_issued_at"),
        (lambda record: setattr(record, "issued_at", "not-a-time"), "malformed_issued_at"),
        (lambda record: setattr(record, "issued_at", "2026-08-07T12:00:00"), "malformed_issued_at"),
        (lambda record: setattr(record, "expires_at", ""), "missing_expires_at"),
        (lambda record: setattr(record, "expires_at", "not-a-time"), "invalid_expiry"),
    ],
)
def test_timestamp_failure_modes(mutator, reason) -> None:
    gate = LiveAuthorizationTTLGate()
    issued_at = datetime(2026, 8, 7, 12, 0, 0, tzinfo=timezone.utc)
    scope = _scope()
    gate.issue_authorization(scope, authorization_id="auth-time", issuance_time=issued_at)
    record = gate._records["auth-time"]
    mutator(record)

    decision = gate.validate_and_consume("auth-time", scope, evaluation_time=issued_at)

    assert decision.approved is False
    assert decision.reason == reason


def test_expiry_must_equal_issued_plus_60_seconds() -> None:
    gate = LiveAuthorizationTTLGate()
    issued_at = datetime(2026, 8, 7, 12, 0, 0, tzinfo=timezone.utc)
    scope = _scope()
    gate.issue_authorization(scope, authorization_id="auth-6", issuance_time=issued_at)
    gate._records["auth-6"].expires_at = (issued_at + timedelta(seconds=30)).isoformat()

    decision = gate.validate_and_consume("auth-6", scope, evaluation_time=issued_at)

    assert decision.approved is False
    assert decision.reason == "invalid_expiry"


def test_single_use_and_replay_rejection() -> None:
    gate = LiveAuthorizationTTLGate()
    issued_at = datetime(2026, 8, 7, 12, 0, 0, tzinfo=timezone.utc)
    scope = _scope()
    gate.issue_authorization(scope, authorization_id="auth-7", issuance_time=issued_at)

    first = gate.validate_and_consume("auth-7", scope, evaluation_time=issued_at)
    replay = gate.validate_and_consume("auth-7", scope, evaluation_time=issued_at + timedelta(seconds=1))

    assert first.approved is True
    assert replay.approved is False
    assert replay.reason == "authorization_already_consumed"


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        ({"environment": "PAPER"}, "environment_mismatch"),
        ({"broker": "OANDA"}, "broker_mismatch"),
        ({"account": "ACC-2"}, "account_mismatch"),
        ({"symbol": "ETH-USD"}, "instrument_mismatch"),
        ({"side": "SELL"}, "order_mismatch"),
        ({"authoritative_exposure_amount": "11.00"}, "order_mismatch"),
        ({"authoritative_exposure_currency": "USD"}, "order_mismatch"),
        ({"quantity": "2"}, "order_mismatch"),
        ({"order_type": "LIMIT"}, "order_mismatch"),
        ({"limit_price": "65000.00"}, "order_mismatch"),
        ({"order_identity": "order-002"}, "order_mismatch"),
    ],
)
def test_scope_mismatch_paths(override, reason) -> None:
    gate = LiveAuthorizationTTLGate()
    issued_at = datetime(2026, 8, 7, 12, 0, 0, tzinfo=timezone.utc)
    scope = _scope()
    gate.issue_authorization(scope, authorization_id="auth-scope", issuance_time=issued_at)

    decision = gate.validate_and_consume(
        "auth-scope",
        _scope(**override),
        evaluation_time=issued_at,
    )

    assert decision.approved is False
    assert decision.reason == reason


def test_revocation_precedence() -> None:
    gate = LiveAuthorizationTTLGate()
    issued_at = datetime(2026, 8, 7, 12, 0, 0, tzinfo=timezone.utc)
    scope = _scope()
    gate.issue_authorization(scope, authorization_id="auth-8", issuance_time=issued_at)
    assert gate.revoke_authorization("auth-8", evaluation_time=issued_at) is True

    decision = gate.validate_and_consume("auth-8", scope, evaluation_time=issued_at)

    assert decision.approved is False
    assert decision.reason == "authorization_revoked"


def test_kill_switch_precedence_and_no_resurrection_after_clear() -> None:
    gate = LiveAuthorizationTTLGate()
    issued_at = datetime(2026, 8, 7, 12, 0, 0, tzinfo=timezone.utc)
    scope = _scope()
    gate.issue_authorization(scope, authorization_id="auth-9", issuance_time=issued_at)

    blocked = gate.validate_and_consume(
        "auth-9",
        scope,
        evaluation_time=issued_at,
        kill_switch_active=True,
    )
    after_clear = gate.validate_and_consume(
        "auth-9",
        scope,
        evaluation_time=issued_at + timedelta(seconds=1),
        kill_switch_active=False,
    )

    assert blocked.approved is False
    assert blocked.reason == "kill_switch_active"
    assert blocked.evidence["consumed"] is False
    assert blocked.evidence["revoked"] is True
    assert after_clear.approved is False
    assert after_clear.reason == "authorization_revoked"


def test_atomic_single_use_under_contention() -> None:
    workers = 12
    rounds = 20
    issued_at = datetime(2026, 8, 7, 12, 0, 0, tzinfo=timezone.utc)

    for round_index in range(rounds):
        gate = LiveAuthorizationTTLGate()
        scope = _scope(order_identity=f"order-concurrency-{round_index}")
        auth_id = f"auth-concurrency-{round_index}"
        gate.issue_authorization(scope, authorization_id=auth_id, issuance_time=issued_at)

        barrier = threading.Barrier(workers)
        results: list[str] = []
        results_lock = threading.Lock()

        def worker() -> None:
            barrier.wait()
            decision = gate.validate_and_consume(auth_id, scope, evaluation_time=issued_at)
            with results_lock:
                results.append(decision.reason)

        threads = [threading.Thread(target=worker) for _ in range(workers)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert results.count("approved") == 1
        assert results.count("authorization_already_consumed") == workers - 1
        assert len(results) == workers
        assert gate._records[auth_id].consumed is True


def test_restart_non_persistence_semantics() -> None:
    gate_a = LiveAuthorizationTTLGate()
    gate_b = LiveAuthorizationTTLGate()
    issued_at = datetime(2026, 8, 7, 12, 0, 0, tzinfo=timezone.utc)
    scope = _scope()
    gate_a.issue_authorization(scope, authorization_id="auth-restart", issuance_time=issued_at)

    decision = gate_b.validate_and_consume("auth-restart", scope, evaluation_time=issued_at)

    assert decision.approved is False
    assert decision.reason == "missing_authorization"


def test_no_automatic_renewal() -> None:
    gate = LiveAuthorizationTTLGate()
    issued_at = datetime(2026, 8, 7, 12, 0, 0, tzinfo=timezone.utc)
    scope = _scope()
    gate.issue_authorization(scope, authorization_id="auth-10", issuance_time=issued_at)

    expired = gate.validate_and_consume(
        "auth-10",
        scope,
        evaluation_time=issued_at + timedelta(seconds=TTL_SECONDS + 1),
    )

    assert expired.approved is False
    assert expired.reason == "authorization_expired"


def test_paper_authority_cannot_authorize_live() -> None:
    gate = LiveAuthorizationTTLGate()
    issued_at = datetime(2026, 8, 7, 12, 0, 0, tzinfo=timezone.utc)
    paper_scope = _scope(environment="PAPER")
    live_scope = _scope(environment="LIVE")
    gate.issue_authorization(paper_scope, authorization_id="auth-11", issuance_time=issued_at)

    decision = gate.validate_and_consume("auth-11", live_scope, evaluation_time=issued_at)

    assert decision.approved is False
    assert decision.reason == "environment_mismatch"


def test_malformed_authorization_record_fails_closed() -> None:
    gate = LiveAuthorizationTTLGate()
    issued_at = datetime(2026, 8, 7, 12, 0, 0, tzinfo=timezone.utc)
    scope = _scope()
    gate.issue_authorization(scope, authorization_id="auth-12", issuance_time=issued_at)
    gate._records["auth-12"].scope = None  # type: ignore[assignment]

    decision = gate.validate_and_consume("auth-12", scope, evaluation_time=issued_at)

    assert decision.approved is False
    assert decision.reason == "malformed_authorization"


def test_deterministic_evidence_contract() -> None:
    gate = LiveAuthorizationTTLGate()
    issued_at = datetime(2026, 8, 7, 12, 0, 0, tzinfo=timezone.utc)
    scope = _scope()
    gate.issue_authorization(scope, authorization_id="auth-evidence", issuance_time=issued_at)

    decision = gate.validate_and_consume("auth-evidence", scope, evaluation_time=issued_at)

    assert decision.approved is True
    assert decision.evidence["authorization_id"] == "auth-evidence"
    assert decision.evidence["issued_at"] == issued_at.isoformat()
    assert decision.evidence["expires_at"] == (issued_at + timedelta(seconds=TTL_SECONDS)).isoformat()
    assert decision.evidence["evaluation_time"] == issued_at.isoformat()
    assert decision.evidence["ttl_seconds"] == TTL_SECONDS
    assert len(decision.evidence["scope_fingerprint"]) == 64
    assert decision.evidence["freshness_result"] == "VALID"
    assert decision.evidence["consumed"] is True
    assert decision.evidence["revoked"] is False
    assert decision.evidence["kill_switch_active"] is False
    assert decision.evidence["decision"] == "AUTHORIZED"
    assert decision.evidence["rejection_reason"] == ""


def test_no_network_or_broker_call_during_validation(monkeypatch) -> None:
    gate = LiveAuthorizationTTLGate()
    issued_at = datetime(2026, 8, 7, 12, 0, 0, tzinfo=timezone.utc)
    scope = _scope()
    gate.issue_authorization(scope, authorization_id="auth-network", issuance_time=issued_at)

    monkeypatch.setattr(
        socket,
        "create_connection",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network call not allowed")),
    )

    decision = gate.validate_and_consume("auth-network", scope, evaluation_time=issued_at)

    assert decision.approved is True


def test_scope_amount_is_decimal_safe() -> None:
    scope = _scope(authoritative_exposure_amount="10.005")

    assert scope.authoritative_exposure_amount == Decimal("10.00")
