"""Trusted paper authority tests (CSS-062 Workstream A).

Negative tests for: forged authority, missing evaluators, invalid registry,
SHA mismatch, and replay. Positive tests verify trusted issuance works when
all four allow-list gates approve.

All tests use isolated temporary paths and fresh Ed25519 keys.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend.runtime.paper_authority_issuer import PaperGateEvaluators
from backend.runtime.trusted_paper_authority import (
    TrustedPaperAuthority,
    TrustedPaperAuthorityError,
    TRUSTED_AUTHORITY_MAX_TTL_SECONDS,
)
from backend.runtime.trusted_risk_evaluators import (
    TRUSTED_EVALUATOR_IDENTIFIERS,
    TrustedRiskEvaluators,
)

CANDIDATE_SHA = "a" * 40
ISSUER_ID = "css-agent-trusted-issuer-001"
PAPER_ROUTE_AUDIENCE = "css.governed.paper-route.simulation.local"


@pytest.fixture
def signing_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


@pytest.fixture
def trusted_evaluators(tmp_path) -> TrustedRiskEvaluators:
    """Isolated AntiBleedGuard state per test (avoids shared cooldown)."""
    evaluators = TrustedRiskEvaluators()
    return evaluators.with_isolated_antibleed_state(
        str(tmp_path / "antibleed_state.json")
    )


@pytest.fixture
def trusted_authority(signing_key, trusted_evaluators) -> TrustedPaperAuthority:
    return TrustedPaperAuthority(
        signing_key=signing_key,
        issuer_id=ISSUER_ID,
        candidate_sha=CANDIDATE_SHA,
        evaluators=trusted_evaluators,
    )


@pytest.fixture
def good_order_context() -> dict:
    """An order context that all four gates should approve."""
    return {
        # R7 (requires asset_class, expected_value, cost, probability)
        "candidate": {
            "symbol": "CAD/JPY",
            "asset_class": "fx",
            "side": "buy",
            "size": 50.0,
            "entry_price": 112.50,
            "stop_price": 112.00,
            "expected_value": 150.0,
            "cost": 50.0,
            "probability": 0.6,
        },
        "session": {
            "session_id": "test-session-001",
            "role": "TRADER",  # R7 _check_role reads session["role"] (ADMIN/SUPER_USER/TRADER)
            "created": __import__("time").time() - 60,  # 60s ago (within 3600s timeout)
        },
        "portfolio_state": {"equity": 100_000.0, "open_positions": 0},
        "engine_mode": "paper",
        # AntiBleedGuard
        "symbol": "CAD/JPY",
        "trade_size": 50.0,
        "expected_move_bps": 100.0,
        "fee_bps": 2.0,
        "spread_bps": 1.0,
        "slippage_bps": 1.0,
        "side": "buy",
        # RiskGovernor
        "instrument": "CAD/JPY",
        "side": "buy",
        "requested_notional": 1000.0,
        "stop_distance_pct": 0.5,
        "equity": 100_000.0,
        "risk_pct": 0.5,
        # Kill switch
        "controls": {"live_order_kill_switch": False, "global_live_order_kill_switch": False},
        "env": {},
    }


# ------------------------------------------------------------- construction
def test_rejects_raw_paper_gate_evaluators(signing_key):
    """The trusted issuer must REFUSE raw PaperGateEvaluators callables."""
    raw = PaperGateEvaluators(
        r7=lambda req: {"approved": True, "reason": "forged"},
        antibleed=lambda req: {"approved": True, "reason": "forged"},
        risk_governor=lambda req: {"approved": True, "reason": "forged"},
        kill_switch=lambda req: {"approved": True, "reason": "forged"},
    )
    with pytest.raises(TrustedPaperAuthorityError, match="TrustedRiskEvaluators required"):
        TrustedPaperAuthority(
            signing_key=signing_key,
            issuer_id=ISSUER_ID,
            candidate_sha=CANDIDATE_SHA,
            evaluators=raw,  # type: ignore[arg-type]
        )


def test_rejects_invalid_candidate_sha(signing_key, trusted_evaluators):
    with pytest.raises(TrustedPaperAuthorityError, match="candidate_sha"):
        TrustedPaperAuthority(
            signing_key=signing_key,
            issuer_id=ISSUER_ID,
            candidate_sha="not-a-sha",
            evaluators=trusted_evaluators,
        )


def test_rejects_invalid_issuer_id(signing_key, trusted_evaluators):
    with pytest.raises(TrustedPaperAuthorityError, match="issuer_id"):
        TrustedPaperAuthority(
            signing_key=signing_key,
            issuer_id="",
            candidate_sha=CANDIDATE_SHA,
            evaluators=trusted_evaluators,
        )


# ---------------------------------------------------------- gate evaluation
def test_kill_switch_engaged_denies(trusted_authority, good_order_context):
    """An engaged kill switch must fail the entire chain."""
    ctx = {**good_order_context, "env": {"CSS_LIVE_ORDER_KILL_SWITCH": "true"}}
    with pytest.raises(TrustedPaperAuthorityError, match="live_order_kill_switch"):
        trusted_authority.issue_trusted_paper_intent(
            nonce="test-nonce-kill-switch-engaged",
            order_context=ctx,
            paper_route_audience=PAPER_ROUTE_AUDIENCE,
            actual_candidate_sha=CANDIDATE_SHA,
        )


def test_antibleed_guard_denies_when_size_below_minimum(trusted_authority, good_order_context):
    """A trade size below the AntiBleedGuard minimum must deny (exception disabled)."""
    ctx = {**good_order_context, "trade_size": 5.0}
    with pytest.raises(TrustedPaperAuthorityError, match="antibleed_guard"):
        trusted_authority.issue_trusted_paper_intent(
            nonce="test-nonce-antibleed-small",
            order_context=ctx,
            paper_route_audience=PAPER_ROUTE_AUDIENCE,
            actual_candidate_sha=CANDIDATE_SHA,
        )


def test_unknown_evaluator_identifier_denies(trusted_evaluators, good_order_context):
    """An unknown identifier is a hard deny, not a bypass."""
    result = trusted_evaluators.evaluate_gate("totally_unknown_gate", good_order_context)
    assert result["approved"] is False
    assert "UNKNOWN_TRUSTED_EVALUATOR" in result["reason"]


def test_all_evaluators_are_in_allow_list():
    assert TRUSTED_EVALUATOR_IDENTIFIERS == (
        "r7_unified_trade_gate",
        "antibleed_guard",
        "risk_governor",
        "live_order_kill_switch",
    )


# ------------------------------------------------------------------- forging
def test_forged_signature_rejected(signing_key, trusted_evaluators, good_order_context):
    """A signature from a DIFFERENT key must fail verification."""
    authority = TrustedPaperAuthority(
        signing_key=signing_key,
        issuer_id=ISSUER_ID,
        candidate_sha=CANDIDATE_SHA,
        evaluators=trusted_evaluators,
    )
    intent = authority.issue_trusted_paper_intent(
        nonce="test-nonce-forged",
        order_context=good_order_context,
        paper_route_audience=PAPER_ROUTE_AUDIENCE,
        actual_candidate_sha=CANDIDATE_SHA,
    )
    # Tamper with the payload (e.g. change the nonce).
    tampered_payload = {**intent["payload"], "nonce": "tampered-nonce"}
    tampered = {"payload": tampered_payload, "signature": intent["signature"]}
    wrong_key = Ed25519PrivateKey.generate()
    with pytest.raises(TrustedPaperAuthorityError):
        TrustedPaperAuthority.verify_trusted_intent(
            tampered,
            public_key=wrong_key.public_key(),  # wrong key
            expected_issuer_id=ISSUER_ID,
            expected_candidate_sha=CANDIDATE_SHA,
            expected_paper_route_audience=PAPER_ROUTE_AUDIENCE,
        )


def test_expired_intent_rejected(signing_key, trusted_evaluators, good_order_context):
    """An expired intent must fail verification."""
    from datetime import datetime, timedelta, timezone
    authority = TrustedPaperAuthority(
        signing_key=signing_key,
        issuer_id=ISSUER_ID,
        candidate_sha=CANDIDATE_SHA,
        evaluators=trusted_evaluators,
    )
    now = datetime.now(timezone.utc)
    intent = authority.issue_trusted_paper_intent(
        nonce="test-nonce-expired",
        order_context=good_order_context,
        paper_route_audience=PAPER_ROUTE_AUDIENCE,
        actual_candidate_sha=CANDIDATE_SHA,
        now=now - timedelta(seconds=TRUSTED_AUTHORITY_MAX_TTL_SECONDS + 10),
    )
    with pytest.raises(TrustedPaperAuthorityError, match="expired"):
        TrustedPaperAuthority.verify_trusted_intent(
            intent,
            public_key=signing_key.public_key(),
            expected_issuer_id=ISSUER_ID,
            expected_candidate_sha=CANDIDATE_SHA,
            expected_paper_route_audience=PAPER_ROUTE_AUDIENCE,
        )


def test_candidate_sha_mismatch_rejected(trusted_authority, good_order_context):
    """A drifted checkout (different SHA) must be rejected at issue time."""
    with pytest.raises(TrustedPaperAuthorityError, match="CANDIDATE_SHA_MISMATCH"):
        trusted_authority.issue_trusted_paper_intent(
            nonce="test-nonce-sha-mismatch",
            order_context=good_order_context,
            paper_route_audience=PAPER_ROUTE_AUDIENCE,
            actual_candidate_sha="b" * 40,
        )


def test_wrong_audience_rejected(signing_key, trusted_evaluators, good_order_context):
    """A wrong paper_route_audience must fail verification."""
    authority = TrustedPaperAuthority(
        signing_key=signing_key,
        issuer_id=ISSUER_ID,
        candidate_sha=CANDIDATE_SHA,
        evaluators=trusted_evaluators,
    )
    intent = authority.issue_trusted_paper_intent(
        nonce="test-nonce-wrong-audience",
        order_context=good_order_context,
        paper_route_audience="wrong.audience",
        actual_candidate_sha=CANDIDATE_SHA,
    )
    with pytest.raises(TrustedPaperAuthorityError, match="paper_route_audience"):
        TrustedPaperAuthority.verify_trusted_intent(
            intent,
            public_key=signing_key.public_key(),
            expected_issuer_id=ISSUER_ID,
            expected_candidate_sha=CANDIDATE_SHA,
            expected_paper_route_audience=PAPER_ROUTE_AUDIENCE,
        )


def test_expiry_rejects_out_of_range(trusted_authority, good_order_context):
    with pytest.raises(TrustedPaperAuthorityError, match="expiry_seconds"):
        trusted_authority.issue_trusted_paper_intent(
            nonce="test-nonce-bad-expiry",
            expiry_seconds=TRUSTED_AUTHORITY_MAX_TTL_SECONDS + 1,
            order_context=good_order_context,
            paper_route_audience=PAPER_ROUTE_AUDIENCE,
            actual_candidate_sha=CANDIDATE_SHA,
        )
