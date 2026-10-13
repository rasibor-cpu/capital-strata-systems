"""Trusted governed paper-route simulation tests (CSS-062 Workstream A+B integration).

Tests the trusted simulation entry point end-to-end:
- Mandatory trusted mode (raw PaperGateEvaluators rejected).
- Kill-switch / AntiBleed denial fails the simulation.
- Atomic nonce+reservation commit.
- Unknown broker outcome PRESERVES the reservation.
- Confirmed no-fill releases capacity but the nonce stays consumed.
- Confirmed fill commits the reservation.
- Signature forgery (tampered payload) rejected.
- SHA mismatch rejected.
- Replay rejected.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend.runtime.pilot_coordination_ledger import PilotCoordinationLedger
from backend.runtime.paper_authority_issuer import PaperGateEvaluators
from backend.runtime.trusted_governed_paper_route import (
    TrustedSimulationBlocked,
    simulate_trusted_governed_paper_order,
)
from backend.runtime.trusted_paper_authority import (
    TrustedPaperAuthority,
    TrustedPaperAuthorityError,
)
from backend.runtime.trusted_risk_evaluators import TrustedRiskEvaluators

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
def ledger(tmp_path: Path) -> PilotCoordinationLedger:
    return PilotCoordinationLedger(tmp_path / "coordination.db")


@pytest.fixture
def good_order_context() -> dict:
    """An order context that all four gates should approve.

    NOTE: the symbol includes a unique suffix (uuid) so each test gets a
    fresh AntiBleedGuard cooldown state (the guard tracks per-symbol
    cooldown after a successful evaluate).
    """
    import uuid

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
            "role": "TRADER",  # R7 _check_role reads session["role"] (ADMIN/SUPER_USER/TRADER)
            "created": __import__("time").time() - 60,  # 60s ago (within 3600s timeout)
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
    }


def _sim(
    ledger: PilotCoordinationLedger,
    authority: TrustedPaperAuthority,
    *,
    approval_id: str,
    nonce: str,
    child_id: str,
    parent_id: str,
    proposed: str = "10.00",
    outcome: str = "unknown",
    order_context: dict | None = None,
) -> dict:
    # The AntiBleedGuard applies a per-symbol cooldown after each successful
    # evaluate, so each _sim call uses a unique symbol to get a clean state.
    import copy
    import uuid

    if order_context is None:
        order_context = {}
    ctx = copy.deepcopy(dict(order_context))
    unique_symbol = f"CAD/JPY-{uuid.uuid4().hex[:8]}"
    ctx["symbol"] = unique_symbol
    if isinstance(ctx.get("candidate"), dict):
        ctx["candidate"] = {**ctx["candidate"], "symbol": unique_symbol}
    ctx["instrument"] = unique_symbol
    return simulate_trusted_governed_paper_order(
        ledger=ledger,
        trusted_authority=authority,
        approval_id=approval_id,
        nonce=nonce,
        order_context=ctx,
        paper_route_audience=PAPER_ROUTE_AUDIENCE,
        actual_candidate_sha=CANDIDATE_SHA,
        child_id=child_id,
        parent_id=parent_id,
        proposed_child_cad=proposed,
        estimated_fees_cad="0.00",
        broker_outcome=outcome,
        max_parent_cad=Decimal("20.00"),
        max_total_cad=Decimal("40.00"),
        max_concurrent_parents=2,
    )


# ------------------------------------------------------- mandatory trusted mode
def test_raw_paper_gate_evaluators_rejected(ledger, trusted_authority):
    """The trusted simulation must REJECT raw PaperGateEvaluators callables."""
    raw = PaperGateEvaluators(
        r7=lambda req: {"approved": True, "reason": "forged"},
        antibleed=lambda req: {"approved": True, "reason": "forged"},
        risk_governor=lambda req: {"approved": True, "reason": "forged"},
        kill_switch=lambda req: {"approved": True, "reason": "forged"},
    )
    with pytest.raises(TrustedSimulationBlocked, match="PAPER_SIMULATION_TRUSTED_MODE_REQUIRED"):
        simulate_trusted_governed_paper_order(
            ledger=ledger,
            trusted_authority=raw,  # type: ignore[arg-type]
            approval_id="A1",
            nonce="n1",
            order_context={},
            paper_route_audience=PAPER_ROUTE_AUDIENCE,
            actual_candidate_sha=CANDIDATE_SHA,
            child_id="c1",
            parent_id="p1",
            proposed_child_cad="10.00",
            estimated_fees_cad="0.00",
            max_parent_cad=Decimal("20.00"),
            max_total_cad=Decimal("40.00"),
            max_concurrent_parents=2,
        )


# ------------------------------------------------------- gate denial → blocked
def test_kill_switch_engaged_blocks_simulation(ledger, trusted_authority, good_order_context):
    ctx = {**good_order_context, "env": {"CSS_LIVE_ORDER_KILL_SWITCH": "true"}}
    with pytest.raises(TrustedSimulationBlocked, match="live_order_kill_switch"):
        _sim(ledger, trusted_authority, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", order_context=ctx)


def test_antibleed_guard_blocks_simulation(ledger, trusted_authority, good_order_context):
    """A size below the AntiBleedGuard minimum must deny the simulation."""
    ctx = {**good_order_context, "trade_size": 5.0}
    with pytest.raises(TrustedSimulationBlocked, match="antibleed_guard"):
        _sim(ledger, trusted_authority, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", order_context=ctx)


def test_sha_mismatch_blocks_simulation(ledger, trusted_authority, good_order_context):
    with pytest.raises(TrustedSimulationBlocked, match="CANDIDATE_SHA_MISMATCH"):
        simulate_trusted_governed_paper_order(
            ledger=ledger,
            trusted_authority=trusted_authority,
            approval_id="A1",
            nonce="n1",
            order_context=good_order_context,
            paper_route_audience=PAPER_ROUTE_AUDIENCE,
            actual_candidate_sha="b" * 40,
            child_id="c1",
            parent_id="p1",
            proposed_child_cad="10.00",
            estimated_fees_cad="0.00",
            max_parent_cad=Decimal("20.00"),
            max_total_cad=Decimal("40.00"),
            max_concurrent_parents=2,
        )


# ---------------------------------------------------------- success + outcomes
def test_unknown_outcome_preserves_reservation(ledger, trusted_authority, good_order_context):
    result = _sim(
        ledger, trusted_authority,
        approval_id="A1", nonce="n1", child_id="c1", parent_id="p1",
        outcome="unknown", order_context=good_order_context,
    )
    assert result["status"] == "UNKNOWN_OUTCOME_PRESERVED"
    assert ledger.reservation_state(child_id="c1") == "OPEN"


def test_confirmed_no_fill_releases_capacity(ledger, trusted_authority, good_order_context):
    result = _sim(
        ledger, trusted_authority,
        approval_id="A1", nonce="n1", child_id="c1", parent_id="p1",
        outcome="no_fill", order_context=good_order_context,
    )
    assert result["status"] == "NO_FILL_RELEASED"
    assert ledger.reservation_state(child_id="c1") == "RELEASED"
    # The nonce is still consumed.
    assert ledger.nonce_is_consumed(issuer_id=ISSUER_ID, nonce="n1") is True


def test_confirmed_fill_commits_reservation(ledger, trusted_authority, good_order_context):
    result = _sim(
        ledger, trusted_authority,
        approval_id="A1", nonce="n1", child_id="c1", parent_id="p1",
        outcome="fill", order_context=good_order_context,
    )
    assert result["status"] == "FILLED_COMMITTED"
    assert ledger.reservation_state(child_id="c1") == "COMMITTED"


# ------------------------------------------------------------------- replay
def test_replay_rejected(ledger, trusted_authority, good_order_context):
    _sim(ledger, trusted_authority, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", order_context=good_order_context)
    with pytest.raises(TrustedSimulationBlocked, match="COORDINATION_REPLAY_REJECTED"):
        _sim(ledger, trusted_authority, approval_id="A2", nonce="n1", child_id="c2", parent_id="p1", order_context=good_order_context)


# ------------------------------------------------------ CAD 20/40 ceilings
def test_parent_cad_20_ceiling_blocks_simulation(ledger, trusted_authority, good_order_context):
    _sim(ledger, trusted_authority, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", proposed="15.00", order_context=good_order_context)
    with pytest.raises(TrustedSimulationBlocked, match="COORDINATION_PARENT_EXPOSURE_CEILING"):
        _sim(ledger, trusted_authority, approval_id="A2", nonce="n2", child_id="c2", parent_id="p1", proposed="6.00", order_context=good_order_context)


def test_total_cad_ceiling_blocks_simulation(ledger, trusted_authority, good_order_context):
    """Isolate the TOTAL ceiling (CAD 30, lower than parent×parents)."""
    # Two parents at 15 each (30 total).
    _sim(ledger, trusted_authority, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", proposed="15.00", order_context=good_order_context)
    _sim(ledger, trusted_authority, approval_id="A2", nonce="n2", child_id="c2", parent_id="p2", proposed="15.00", order_context=good_order_context)
    # Third child under parent 1: 15+1=16 < 20 (parent OK) but 30+1=31 > 30 (TOTAL).
    with pytest.raises(TrustedSimulationBlocked, match="COORDINATION_TOTAL_EXPOSURE_CEILING"):
        simulate_trusted_governed_paper_order(
            ledger=ledger,
            trusted_authority=trusted_authority,
            approval_id="A3",
            nonce="n3",
            order_context=good_order_context,
            paper_route_audience=PAPER_ROUTE_AUDIENCE,
            actual_candidate_sha=CANDIDATE_SHA,
            child_id="c3",
            parent_id="p1",
            proposed_child_cad="1.00",
            estimated_fees_cad="0.00",
            max_parent_cad=Decimal("20.00"),
            max_total_cad=Decimal("30.00"),
            max_concurrent_parents=2,
        )


# --------------------------------------------------- signature-forgery test
def test_tampered_intent_signature_forgery(signing_key, trusted_evaluators, good_order_context, ledger):
    """A tampered payload must fail verification (signature does not match)."""
    authority = TrustedPaperAuthority(
        signing_key=signing_key,
        issuer_id=ISSUER_ID,
        candidate_sha=CANDIDATE_SHA,
        evaluators=trusted_evaluators,
    )
    intent = authority.issue_trusted_paper_intent(
        nonce="n-forgery",
        order_context=good_order_context,
        paper_route_audience=PAPER_ROUTE_AUDIENCE,
        actual_candidate_sha=CANDIDATE_SHA,
    )
    # Tamper: change the nonce after signing.
    tampered_payload = {**intent["payload"], "nonce": "tampered"}
    tampered = {"payload": tampered_payload, "signature": intent["signature"]}
    with pytest.raises(TrustedPaperAuthorityError):
        TrustedPaperAuthority.verify_trusted_intent(
            tampered,
            public_key=signing_key.public_key(),
            expected_issuer_id=ISSUER_ID,
            expected_candidate_sha=CANDIDATE_SHA,
            expected_paper_route_audience=PAPER_ROUTE_AUDIENCE,
        )


def test_wrong_public_key_forgery(signing_key, trusted_evaluators, good_order_context):
    """A signature verified with the WRONG public key must fail."""
    authority = TrustedPaperAuthority(
        signing_key=signing_key,
        issuer_id=ISSUER_ID,
        candidate_sha=CANDIDATE_SHA,
        evaluators=trusted_evaluators,
    )
    intent = authority.issue_trusted_paper_intent(
        nonce="n-wrong-key",
        order_context=good_order_context,
        paper_route_audience=PAPER_ROUTE_AUDIENCE,
        actual_candidate_sha=CANDIDATE_SHA,
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
