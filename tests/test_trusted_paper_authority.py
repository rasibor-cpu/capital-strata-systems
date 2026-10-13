"""Trusted paper authority tests (CSS-062 Blocker 2).

Blocker 2 — Trusted authority:
- Remove caller-controlled trust establishment (key, issuer, SHA, evaluator).
- Pin candidate SHA, issuer identity, evaluator implementations, key identity.
- Reject forged identities, mismatched checkout/candidate SHAs,
  subclass-based evaluator substitution, arbitrary evaluator injection,
  missing/stale registry state.
- Verify trusted signed intent before capacity reservation.
- Kill-switch state from the AUTHORITATIVE environment (Blocker 4).
- Explicit boolean ALLOW required (Blocker 4).
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend.runtime.trusted_paper_authority import (
    AuthenticatedTrustRegistry,
    TrustedPaperAuthority,
    TrustedPaperAuthorityError,
    TRUSTED_AUTHORITY_MAX_TTL_SECONDS,
)
from backend.runtime.trusted_risk_evaluators import (
    TrustedEvaluatorError,
    TrustedRiskEvaluators,
)

CANDIDATE_SHA = "a" * 40
ISSUER_ID = "css-agent-trusted-issuer-001"
PAPER_ROUTE_AUDIENCE = "css.governed.paper-route.simulation.local"


@pytest.fixture
def signing_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


@pytest.fixture
def registry(signing_key) -> AuthenticatedTrustRegistry:
    return AuthenticatedTrustRegistry(
        issuer_id=ISSUER_ID,
        candidate_sha=CANDIDATE_SHA,
        public_key_hex=signing_key.public_key().public_bytes_raw().hex(),
        private_key=signing_key,
        created_at="2026-10-13T00:00:00Z",
    )


@pytest.fixture
def trusted_evaluators() -> TrustedRiskEvaluators:
    return TrustedRiskEvaluators()


def _good_order_context() -> dict:
    unique_symbol = f"CAD/JPY-{uuid.uuid4().hex[:8]}"
    return {
        "candidate": {
            "symbol": unique_symbol,
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
            "role": "TRADER",
            "created": time.time() - 60,
        },
        "portfolio_state": {"equity": 100_000.0, "open_positions": 0},
        "engine_mode": "paper",
        "symbol": unique_symbol,
        "trade_size": 50.0,
        "expected_move_bps": 100.0,
        "fee_bps": 2.0,
        "spread_bps": 1.0,
        "slippage_bps": 1.0,
        "side": "buy",
        "instrument": unique_symbol,
        "requested_notional": 1000.0,
        "stop_distance_pct": 0.5,
        "equity": 100_000.0,
        "risk_pct": 0.5,
        "controls": {"live_order_kill_switch": False, "global_live_order_kill_switch": False},
        "env": {},
        # Binding fields (Blocker 3).
        "parent_id": "p1",
        "child_id": "c1",
        "proposed_child_cad": "10.00",
        "estimated_fees_cad": "0.00",
    }


# ============================================ BLOCKER 2: trusted authority
def test_registry_rejects_mismatched_private_key():
    """The private key must match the pinned public key."""
    key1 = Ed25519PrivateKey.generate()
    key2 = Ed25519PrivateKey.generate()
    with pytest.raises(TrustedPaperAuthorityError, match="private key does not match"):
        AuthenticatedTrustRegistry(
            issuer_id=ISSUER_ID,
            candidate_sha=CANDIDATE_SHA,
            public_key_hex=key1.public_key().public_bytes_raw().hex(),
            private_key=key2,
        )


def test_registry_rejects_invalid_sha():
    key = Ed25519PrivateKey.generate()
    with pytest.raises(TrustedPaperAuthorityError, match="candidate_sha"):
        AuthenticatedTrustRegistry(
            issuer_id=ISSUER_ID,
            candidate_sha="not-a-sha",
            public_key_hex=key.public_key().public_bytes_raw().hex(),
            private_key=key,
        )


def test_registry_rejects_empty_issuer():
    key = Ed25519PrivateKey.generate()
    with pytest.raises(TrustedPaperAuthorityError, match="issuer_id"):
        AuthenticatedTrustRegistry(
            issuer_id="",
            candidate_sha=CANDIDATE_SHA,
            public_key_hex=key.public_key().public_bytes_raw().hex(),
            private_key=key,
        )


def test_registry_rejects_invalid_public_key_hex():
    key = Ed25519PrivateKey.generate()
    with pytest.raises(TrustedPaperAuthorityError, match="public_key_hex"):
        AuthenticatedTrustRegistry(
            issuer_id=ISSUER_ID,
            candidate_sha=CANDIDATE_SHA,
            public_key_hex="too-short",
            private_key=key,
        )


def test_subclass_substitution_rejected(signing_key, registry):
    """A subclass of TrustedRiskEvaluators must be REJECTED (Blocker 2)."""

    # Subclassing must raise at class definition (final class).
    with pytest.raises(TrustedEvaluatorError):
        class ForgedEvaluators(TrustedRiskEvaluators):
            pass

    # A duck-typed evaluators object must also be rejected by the authority.
    class DuckTypedEvaluators:
        def evaluate_all(self, ctx):
            return {k: {"approved": True, "reason": "forged"} for k in (
                "r7_unified_trade_gate", "antibleed_guard", "risk_governor", "live_order_kill_switch"
            )}

    with pytest.raises(TrustedPaperAuthorityError, match="TrustedRiskEvaluators"):
        TrustedPaperAuthority(
            registry=registry,
            evaluators=DuckTypedEvaluators(),  # type: ignore[arg-type]
        )


def test_trusted_risk_evaluators_is_final():
    """Subclassing TrustedRiskEvaluators must raise (no subclass substitution)."""
    with pytest.raises(TrustedEvaluatorError):
        class Forged(TrustedRiskEvaluators):
            pass


def test_duck_typed_authority_rejected():
    """A duck-typed authority object must be rejected BEFORE any DB write."""

    class ForgedAuthority:
        issuer_id = ISSUER_ID
        candidate_sha = CANDIDATE_SHA
        registry = None

        def issue_trusted_paper_intent(self, **kwargs):
            return {"payload": {"nonce": "forged"}, "signature": "00"}

    # The trusted route checks isinstance — a duck-typed object fails.
    from backend.runtime.trusted_governed_paper_route import (
        TrustedSimulationBlocked,
        simulate_trusted_governed_paper_order,
    )
    from backend.runtime.pilot_coordination_ledger import AuthoritativePilotCoordinationLedger
    from backend.config.order_limit_config import DEFAULT_ORDER_LIMIT_CONFIG

    ledger = AuthoritativePilotCoordinationLedger(
        Path("/tmp/test-duck-typed.db"), config=DEFAULT_ORDER_LIMIT_CONFIG
    )
    with pytest.raises(TrustedSimulationBlocked, match="TRUSTED_MODE_REQUIRED"):
        simulate_trusted_governed_paper_order(
            ledger=ledger,
            trusted_authority=ForgedAuthority(),  # type: ignore[arg-type]
            approval_id="A1",
            nonce="n1",
            order_context=_good_order_context(),
            paper_route_audience=PAPER_ROUTE_AUDIENCE,
        )
    # No DB write happened.
    assert ledger.approval_exists("A1") is False


def test_checkout_sha_mismatch_rejected(registry, trusted_evaluators, monkeypatch, tmp_path):
    """A running checkout that differs from the pinned SHA must be rejected."""
    from backend.runtime import trusted_paper_authority as tpa

    # Patch compute_current_checkout_sha to return a DIFFERENT SHA.
    monkeypatch.setattr(tpa, "compute_current_checkout_sha", lambda root: "b" * 40)
    authority = TrustedPaperAuthority(
        registry=registry,
        evaluators=trusted_evaluators,
        repo_root=tmp_path,
    )
    with pytest.raises(TrustedPaperAuthorityError, match="CANDIDATE_SHA_MISMATCH"):
        authority.issue_trusted_paper_intent(
            nonce="n1",
            order_context=_good_order_context(),
            paper_route_audience=PAPER_ROUTE_AUDIENCE,
        )


def test_checkout_sha_unverifiable_rejected(registry, trusted_evaluators, monkeypatch, tmp_path):
    """If the checkout SHA cannot be determined, the trusted path stays BLOCKED."""
    from backend.runtime import trusted_paper_authority as tpa

    monkeypatch.setattr(tpa, "compute_current_checkout_sha", lambda root: None)
    authority = TrustedPaperAuthority(
        registry=registry,
        evaluators=trusted_evaluators,
        repo_root=tmp_path,
    )
    with pytest.raises(TrustedPaperAuthorityError, match="CHECKOUT_SHA_UNVERIFIABLE"):
        authority.issue_trusted_paper_intent(
            nonce="n1",
            order_context=_good_order_context(),
            paper_route_audience=PAPER_ROUTE_AUDIENCE,
        )


def test_expiry_rejects_out_of_range(registry, trusted_evaluators, tmp_path):
    """The expiry must be capped at TRUSTED_AUTHORITY_MAX_TTL_SECONDS."""
    # Use the ACTUAL checkout SHA so the authority can issue.
    from backend.runtime.trusted_paper_authority import compute_current_checkout_sha

    actual_sha = compute_current_checkout_sha()
    if actual_sha is None:
        pytest.skip("checkout SHA unverifiable in this environment")
    from backend.config.order_limit_config import CanonicalOrderLimitConfig
    from backend.runtime.pilot_coordination_ledger import AuthoritativePilotCoordinationLedger

    key = Ed25519PrivateKey.generate()
    actual_registry = AuthenticatedTrustRegistry(
        issuer_id=ISSUER_ID,
        candidate_sha=actual_sha,
        public_key_hex=key.public_key().public_bytes_raw().hex(),
        private_key=key,
    )
    authority = TrustedPaperAuthority(
        registry=actual_registry,
        evaluators=trusted_evaluators,
    )
    with pytest.raises(TrustedPaperAuthorityError, match="expiry_seconds"):
        authority.issue_trusted_paper_intent(
            nonce="n1",
            expiry_seconds=TRUSTED_AUTHORITY_MAX_TTL_SECONDS + 1,
            order_context=_good_order_context(),
            paper_route_audience=PAPER_ROUTE_AUDIENCE,
        )


# ============================================ BLOCKER 4: fail-closed gates
def test_truthy_string_not_accepted():
    """A truthy non-boolean (e.g. 'false') must be a DENIAL (Blocker 4)."""
    evaluators = TrustedRiskEvaluators()
    # Directly test the gate logic with a truthy string.
    ctx = _good_order_context()
    # The kill-switch adapter reads os.environ (authoritative). Patch it to
    # return a truthy non-boolean.
    import backend.runtime.trusted_risk_evaluators as tre
    original = tre.TrustedRiskEvaluators.evaluate_kill_switch

    def fake_kill_switch(self, order_context):
        # Return a truthy non-boolean 'blocked' value.
        return {"approved": True, "reason": "kill_switch_clear"}

    # Instead of patching, test the core logic: the authority must reject
    # a truthy non-boolean in gate_decisions.
    # We test via verify_trusted_intent with a forged payload.
    key = Ed25519PrivateKey.generate()
    from datetime import datetime, timedelta, timezone

    # Build a forged intent with a truthy string 'approved'.
    payload = {
        "v": 1,
        "kind": "trusted_paper_intent",
        "issuer_id": ISSUER_ID,
        "candidate_sha": CANDIDATE_SHA,
        "paper_route_audience": PAPER_ROUTE_AUDIENCE,
        "nonce": "n-truthy",
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat(),
        "order_context": {},
        "gate_decisions": {
            "r7_unified_trade_gate": {"approved": "true", "reason": "forged"},  # truthy string!
            "antibleed_guard": {"approved": True, "reason": "ok"},
            "risk_governor": {"approved": True, "reason": "ok"},
            "live_order_kill_switch": {"approved": True, "reason": "ok"},
        },
    }
    # Sign with the real key so only the truthy-string check fails.
    payload_bytes = TrustedPaperAuthority._canonical_json(payload).encode("utf-8")
    signature = key.sign(payload_bytes)
    intent = {"payload": payload, "signature": signature.hex()}

    with pytest.raises(TrustedPaperAuthorityError, match="gate not approved"):
        TrustedPaperAuthority.verify_trusted_intent(
            intent,
            public_key=key.public_key(),
            expected_issuer_id=ISSUER_ID,
            expected_candidate_sha=CANDIDATE_SHA,
            expected_paper_route_audience=PAPER_ROUTE_AUDIENCE,
        )


def test_kill_switch_reads_authoritative_environment(monkeypatch):
    """The kill switch must read os.environ, NOT a request-supplied env.

    Test: engage the REAL environment kill switch (CSS_LIVE_ORDER_KILL_SWITCH)
    and supply an ATTACKER-controlled nonempty env mapping in the order
    context. The kill switch must STILL deny.
    """
    monkeypatch.setenv("CSS_LIVE_ORDER_KILL_SWITCH", "true")
    evaluators = TrustedRiskEvaluators()
    ctx = _good_order_context()
    # Attacker supplies a nonempty env in the order context (trying to hide
    # the engaged real kill switch).
    ctx = {**ctx, "env": {"ATTACKER_KEY": "ATTACKER_VALUE"}}

    result = evaluators.evaluate_kill_switch(ctx)
    assert result["approved"] is False
    assert "kill_switch" in result["reason"].lower() or result["reason"] == "env_kill_switch_engaged"
    monkeypatch.undo()


def test_engaged_environment_kill_switch_denies(monkeypatch):
    """An engaged REAL environment kill switch must deny the entire chain."""
    monkeypatch.setenv("CSS_LIVE_ORDER_KILL_SWITCH", "true")
    evaluators = TrustedRiskEvaluators()
    ctx = _good_order_context()
    result = evaluators.evaluate_all(ctx)
    assert result["live_order_kill_switch"]["approved"] is False
    monkeypatch.undo()


def test_missing_gate_result_denies():
    """A missing evaluator result must deny (fail closed)."""
    evaluators = TrustedRiskEvaluators()
    # Unknown identifier = hard deny.
    result = evaluators.evaluate_gate("totally_unknown", {})
    assert result["approved"] is False
    assert "UNKNOWN_TRUSTED_EVALUATOR" in result["reason"]


def test_non_finite_input_denied():
    """Non-finite (NaN/inf) inputs must be denied (Blocker 4)."""
    evaluators = TrustedRiskEvaluators()
    ctx = _good_order_context()
    ctx = {**ctx, "trade_size": float("nan")}
    result = evaluators.evaluate_antibleed(ctx)
    assert result["approved"] is False
    assert "NON_FINITE" in result["reason"] or "INCOMPLETE" in result["reason"]


def test_antibleed_size_below_minimum_denies():
    """A trade size below the AntiBleedGuard minimum must deny (exception disabled)."""
    evaluators = TrustedRiskEvaluators()
    ctx = _good_order_context()
    ctx = {**ctx, "trade_size": 5.0}
    result = evaluators.evaluate_antibleed(ctx)
    assert result["approved"] is False


# ============================================== signature forgery
def test_tampered_payload_rejected(registry, trusted_evaluators, tmp_path, monkeypatch):
    """A tampered payload must fail verification (signature forgery)."""
    from backend.runtime.trusted_paper_authority import compute_current_checkout_sha

    monkeypatch.setattr(
        "backend.runtime.trusted_paper_authority.compute_current_checkout_sha",
        lambda root: CANDIDATE_SHA,
    )
    authority = TrustedPaperAuthority(
        registry=registry,
        evaluators=trusted_evaluators,
        repo_root=tmp_path,
    )
    intent = authority.issue_trusted_paper_intent(
        nonce="n-forgery",
        order_context=_good_order_context(),
        paper_route_audience=PAPER_ROUTE_AUDIENCE,
    )
    # Tamper: change the nonce after signing.
    tampered_payload = {**intent["payload"], "nonce": "tampered"}
    tampered = {"payload": tampered_payload, "signature": intent["signature"]}
    with pytest.raises(TrustedPaperAuthorityError):
        TrustedPaperAuthority.verify_trusted_intent(
            tampered,
            public_key=registry.private_key.public_key(),
            expected_issuer_id=ISSUER_ID,
            expected_candidate_sha=CANDIDATE_SHA,
            expected_paper_route_audience=PAPER_ROUTE_AUDIENCE,
        )


def test_wrong_public_key_rejected(registry, trusted_evaluators, tmp_path, monkeypatch):
    """A signature verified with the WRONG public key must fail."""
    monkeypatch.setattr(
        "backend.runtime.trusted_paper_authority.compute_current_checkout_sha",
        lambda root: CANDIDATE_SHA,
    )
    authority = TrustedPaperAuthority(
        registry=registry,
        evaluators=trusted_evaluators,
        repo_root=tmp_path,
    )
    intent = authority.issue_trusted_paper_intent(
        nonce="n-wrong-key",
        order_context=_good_order_context(),
        paper_route_audience=PAPER_ROUTE_AUDIENCE,
    )
    wrong_key = Ed25519PrivateKey.generate()
    with pytest.raises(TrustedPaperAuthorityError):
        TrustedPaperAuthority.verify_trusted_intent(
            intent,
            public_key=wrong_key.public_key(),
            expected_issuer_id=ISSUER_ID,
            expected_candidate_sha=CANDIDATE_SHA,
            expected_paper_route_audience=PAPER_ROUTE_AUDIENCE,
        )


def test_expired_intent_rejected(registry, trusted_evaluators, tmp_path, monkeypatch):
    """An expired intent must fail verification."""
    from datetime import datetime, timedelta, timezone

    monkeypatch.setattr(
        "backend.runtime.trusted_paper_authority.compute_current_checkout_sha",
        lambda root: CANDIDATE_SHA,
    )
    authority = TrustedPaperAuthority(
        registry=registry,
        evaluators=trusted_evaluators,
        repo_root=tmp_path,
    )
    intent = authority.issue_trusted_paper_intent(
        nonce="n-expired",
        expiry_seconds=1,
        order_context=_good_order_context(),
        paper_route_audience=PAPER_ROUTE_AUDIENCE,
    )
    # Wait past the 1-second expiry, then verify.
    import time as _time
    _time.sleep(1.5)
    with pytest.raises(TrustedPaperAuthorityError, match="expired"):
        TrustedPaperAuthority.verify_trusted_intent(
            intent,
            public_key=registry.private_key.public_key(),
            expected_issuer_id=ISSUER_ID,
            expected_candidate_sha=CANDIDATE_SHA,
            expected_paper_route_audience=PAPER_ROUTE_AUDIENCE,
        )


def test_wrong_audience_rejected(registry, trusted_evaluators, tmp_path, monkeypatch):
    """A wrong paper_route_audience must fail verification."""
    monkeypatch.setattr(
        "backend.runtime.trusted_paper_authority.compute_current_checkout_sha",
        lambda root: CANDIDATE_SHA,
    )
    authority = TrustedPaperAuthority(
        registry=registry,
        evaluators=trusted_evaluators,
        repo_root=tmp_path,
    )
    intent = authority.issue_trusted_paper_intent(
        nonce="n-wrong-audience",
        order_context=_good_order_context(),
        paper_route_audience="wrong.audience",
    )
    with pytest.raises(TrustedPaperAuthorityError, match="paper_route_audience"):
        TrustedPaperAuthority.verify_trusted_intent(
            intent,
            public_key=registry.private_key.public_key(),
            expected_issuer_id=ISSUER_ID,
            expected_candidate_sha=CANDIDATE_SHA,
            expected_paper_route_audience=PAPER_ROUTE_AUDIENCE,
        )


# ============================================== Blocker 3: signed binding
def test_order_context_is_source_of_truth_for_binding():
    """The order_context must contain parent_id/child_id/proposed_cad/fees (Blocker 3)."""
    from backend.runtime.trusted_governed_paper_route import _extract_binding

    ctx = _good_order_context()
    binding = _extract_binding(ctx)
    assert binding is not None
    assert binding.parent_id == "p1"
    assert binding.child_id == "c1"
    assert binding.proposed_child_cad == "10.00"
    assert binding.estimated_fees_cad == "0.00"


def test_missing_binding_fields_rejected():
    """Missing parent_id/child_id/proposed_cad in order_context → rejected."""
    from backend.runtime.trusted_governed_paper_route import _extract_binding

    ctx = _good_order_context()
    del ctx["parent_id"]
    assert _extract_binding(ctx) is None


def test_capacity_limits_not_caller_supplied():
    """Capacity limits come from CanonicalOrderLimitConfig, NOT caller input (Blocker 3).

    The simulate_trusted_governed_paper_order signature does NOT accept
    max_parent_cad/max_total_cad/max_concurrent_parents. Verify by inspecting
    the signature.
    """
    import inspect
    from backend.runtime.trusted_governed_paper_route import simulate_trusted_governed_paper_order

    params = inspect.signature(simulate_trusted_governed_paper_order).parameters
    assert "max_parent_cad" not in params
    assert "max_total_cad" not in params
    assert "max_concurrent_parents" not in params
