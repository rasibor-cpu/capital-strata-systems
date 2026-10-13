"""Isolated integration tests for the paper-only simulation route.

These tests exercise the trusted-issuer wiring (issuer + registry + verifier
+ one-time ledger + reservation ledger + fake broker). They never touch
production keys, never contact a real broker, and never grant execution
authority. The production `submit_governed_paper_order` remains unconditionally
fail-closed (`PAPER_AUTHORITY_PROVENANCE_UNVERIFIED`) — verified separately.

An authentic AntiBleed denial (sub-threshold trade_size) is a valid
acceptance result and is not mocked.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import pytest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend.runtime.governed_paper_route import (
    GovernedPaperRouteBlocked,
    simulate_governed_paper_order,
    submit_governed_paper_order,
)
from backend.runtime.pilot_authorization_ledger import PilotAuthorizationLedger
from backend.runtime.pilot_broker_evidence import BrokerInstrumentEvidence
from backend.runtime.pilot_currency_conversion import VerifiedRateInput
from backend.runtime.pilot_exposure_reservation import PilotExposureReservationLedger
from backend.runtime.paper_authority_issuer import PaperAuthorityIssuer, PaperGateEvaluators
from backend.runtime.paper_authority_registry import PaperIssuerRegistry


CANDIDATE_SHA = "a" * 40
NOW = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


def _order_request() -> dict:
    return {
        "candidate_sha": CANDIDATE_SHA,
        "broker": "IBKR_PAPER",
        "account": "A",
        "instrument": "FUT-TEST",
        "parent_id": "P",
        "child_id": "C",
        "side": "BUY",
        "quantity": "1",
        "limit_price": "5",
        "quote_currency": "USD",
        "risk_currency": "CAD",
        "risk_amount": "6.25",
    }


def _allow_all() -> PaperGateEvaluators:
    return PaperGateEvaluators(
        r7=lambda req: {"approved": True, "reason": "ok"},
        antibleed=lambda req: {"approved": True, "reason": "ok"},
        risk_governor=lambda req: {"approved": True, "reason": "ok"},
        kill_switch=lambda req: {"approved": True, "reason": "ok"},
    )


def _issuer_and_registry():
    key = Ed25519PrivateKey.generate()
    issuer = PaperAuthorityIssuer(
        signing_key=key, issuer_id="test-issuer", candidate_sha=CANDIDATE_SHA
    )
    registry = PaperIssuerRegistry()
    registry.register_issuer(
        issuer_id="test-issuer", public_key=key.public_key()
    )
    return issuer, registry


def _instrument() -> BrokerInstrumentEvidence:
    return BrokerInstrumentEvidence(
        broker_id="IBKR_PAPER",
        account_id="A",
        instrument_id="FUT-TEST",
        asset_class="FUTURES",
        quote_currency="USD",
        contract_multiplier=Decimal("1"),
        observed_at=NOW - timedelta(seconds=5),
        evidence_id="test-evidence-1",
    )


def _rate() -> VerifiedRateInput:
    return VerifiedRateInput(
        base_currency="USD",
        quote_currency="CAD",
        quote_per_base=Decimal("1.38"),
        observed_at=NOW - timedelta(seconds=5),
        source_id="test-evidence-1",
    )


class FakeBroker:
    """Fake broker; never contacts any real broker."""

    def __init__(self, fail: bool = False):
        self.fail = fail
        self.submitted = []

    def submit_order(self, **kwargs):
        if self.fail:
            raise RuntimeError("fake broker failure")
        self.submitted.append(kwargs)
        return {"status": "FILLED", "fill_price": kwargs.get("price"), **kwargs}


def _base_kwargs(ledger, authorization_ledger, issuer, registry, fake_broker):
    return dict(
        paper_broker="IBKR_PAPER",
        ledger=ledger,
        authorization_ledger=authorization_ledger,
        issuer=issuer,
        issuer_registry=registry,
        issuer_id="test-issuer",
        order_request=_order_request(),
        evaluators=_allow_all(),
        instrument=_instrument(),
        quote_rate=_rate(),
        trusted_evidence_ids=frozenset({"test-evidence-1"}),
        risk_gross_quote="5.00",
        risk_cash_quote="5.00",
        risk_max_loss_quote="0.50",
        fee_quote="0.05",
        quantity=1.0,
        side="BUY",
        limit_price=5.0,
        decision_envelope={"final_decision": "ALLOW"},
        now=NOW,
        fake_broker=fake_broker,
        issued_at=NOW,
    )


# ---------------------------------------------------------------------------
# Production route must remain unconditionally fail-closed
# ---------------------------------------------------------------------------


class TestProductionRouteUnchanged:
    def test_production_paper_route_still_blocks_unconditionally(self, tmp_path: Path):
        """The real production `submit_governed_paper_order` must still raise
        PAPER_AUTHORITY_PROVENANCE_UNVERIFIED even with a valid-looking
        envelope — the trust gap is not silently closed by this branch.
        """
        ledger = PilotExposureReservationLedger(tmp_path / "res.db")
        with pytest.raises(GovernedPaperRouteBlocked) as exc:
            submit_governed_paper_order(
                paper_broker="IBKR_PAPER",
                ledger=ledger,
                parent_id="P",
                child_id="C",
                instrument=_instrument(),
                quote_rate=_rate(),
                trusted_evidence_ids=frozenset({"test-evidence-1"}),
                risk_gross_quote="5.00",
                risk_cash_quote="5.00",
                risk_max_loss_quote="0.50",
                fee_quote="0.05",
                quantity=1.0,
                side="BUY",
                limit_price=5.0,
                decision_envelope={"final_decision": "ALLOW"},
                now=NOW,
            )
        assert "PAPER_AUTHORITY_PROVENANCE_UNVERIFIED" in str(exc.value)


# ---------------------------------------------------------------------------
# Simulation route: positive path
# ---------------------------------------------------------------------------


class TestSimulationPositivePath:
    def test_valid_issued_intent_proceeds_to_simulation(self, tmp_path: Path):
        ledger = PilotExposureReservationLedger(tmp_path / "res.db")
        auth_ledger = PilotAuthorizationLedger(tmp_path / "auth")
        issuer, registry = _issuer_and_registry()
        fake = FakeBroker()

        result = simulate_governed_paper_order(
            **_base_kwargs(ledger, auth_ledger, issuer, registry, fake)
        )
        assert result["status"] == "FILLED"
        assert len(fake.submitted) == 1

        # The reservation ledger must have transitioned to COMMITTED.
        snapshot = ledger.snapshot()
        assert len(snapshot) == 1
        assert snapshot[0]["state"] == "COMMITTED"

    def test_replay_is_rejected(self, tmp_path: Path):
        ledger = PilotExposureReservationLedger(tmp_path / "res.db")
        auth_ledger = PilotAuthorizationLedger(tmp_path / "auth")
        issuer, registry = _issuer_and_registry()
        fake = FakeBroker()

        kwargs = _base_kwargs(ledger, auth_ledger, issuer, registry, fake)
        # First submission succeeds.
        result = simulate_governed_paper_order(**kwargs)
        assert result["status"] == "FILLED"
        # Replay the same child_id: must be rejected (the child reservation is
        # already COMMITTED, so the reconcile path surfaces an ambiguous state
        # rather than silently allowing a duplicate fill).
        with pytest.raises(GovernedPaperRouteBlocked) as exc:
            simulate_governed_paper_order(**kwargs)
        assert any(
            frag in str(exc.value)
            for frag in ("PAPER_SIMULATION_INTENT_REPLAYED", "DUPLICATE_CHILD", "PAPER_SIMULATION_AMBIGUOUS_STATE")
        ), str(exc.value)


# ---------------------------------------------------------------------------
# Simulation route: fail-closed denials
# ---------------------------------------------------------------------------


class TestSimulationFailClosed:
    def _expect_blocked(self, tmp_path, mutate, expected_reason_fragment):
        ledger = PilotExposureReservationLedger(tmp_path / "res.db")
        auth_ledger = PilotAuthorizationLedger(tmp_path / "auth")
        issuer, registry = _issuer_and_registry()
        fake = FakeBroker()
        kwargs = _base_kwargs(ledger, auth_ledger, issuer, registry, fake)
        kwargs = mutate(kwargs) if mutate else kwargs

        with pytest.raises(GovernedPaperRouteBlocked) as exc:
            simulate_governed_paper_order(**kwargs)
        assert expected_reason_fragment in str(exc.value), str(exc.value)

    def test_missing_fake_broker_rejected(self, tmp_path: Path):
        def mutate(kwargs):
            kwargs["fake_broker"] = None
            return kwargs
        self._expect_blocked(tmp_path, mutate, "PAPER_SIMULATION_FAKE_BROKER_REQUIRED")

    def test_unenrolled_issuer_rejected(self, tmp_path: Path):
        def mutate(kwargs):
            kwargs["issuer_id"] = "unregistered-issuer"
            return kwargs
        self._expect_blocked(tmp_path, mutate, "PAPER_SIMULATION_ISSUER_NOT_ENROLLED")

    def test_denied_evaluator_blocks_simulation(self, tmp_path: Path):
        ledger = PilotExposureReservationLedger(tmp_path / "res.db")
        auth_ledger = PilotAuthorizationLedger(tmp_path / "auth")
        issuer, registry = _issuer_and_registry()
        fake = FakeBroker()

        # Override one evaluator to deny.
        allow_all = _allow_all()
        bad_evals = PaperGateEvaluators(
            r7=allow_all.r7,
            antibleed=lambda req: {"approved": False, "reason": "insufficient_edge"},
            risk_governor=allow_all.risk_governor,
            kill_switch=allow_all.kill_switch,
        )
        kwargs = _base_kwargs(ledger, auth_ledger, issuer, registry, fake)
        kwargs["evaluators"] = bad_evals

        with pytest.raises(GovernedPaperRouteBlocked) as exc:
            simulate_governed_paper_order(**kwargs)
        assert "PAPER_SIMULATION_ISSUER_DENIED" in str(exc.value)
        # No reservation, no fill.
        assert ledger.snapshot() == []
        assert fake.submitted == []

    def test_order_substitution_blocked(self, tmp_path: Path):
        """A different side in the envelope vs the order_request must be
        rejected (binding mismatch / invalid order).
        """
        ledger = PilotExposureReservationLedger(tmp_path / "res.db")
        auth_ledger = PilotAuthorizationLedger(tmp_path / "auth")
        issuer, registry = _issuer_and_registry()
        fake = FakeBroker()

        # Envelope says SELL; order_request says BUY.
        kwargs = _base_kwargs(ledger, auth_ledger, issuer, registry, fake)
        kwargs["side"] = "SELL"

        with pytest.raises(GovernedPaperRouteBlocked) as exc:
            simulate_governed_paper_order(**kwargs)
        assert any(
            frag in str(exc.value)
            for frag in ("PAPER_SIMULATION_INTENT_BINDING_MISMATCH", "PAPER_SIMULATION_INVALID_ORDER")
        ), str(exc.value)
        assert ledger.snapshot() == []
        assert fake.submitted == []

    def test_expired_intent_rejected(self, tmp_path: Path):
        ledger = PilotExposureReservationLedger(tmp_path / "res.db")
        auth_ledger = PilotAuthorizationLedger(tmp_path / "auth")
        issuer, registry = _issuer_and_registry()
        fake = FakeBroker()

        # Issue the intent far in the past; the issuer will still sign it but
        # the verifier will reject it as expired.
        kwargs = _base_kwargs(ledger, auth_ledger, issuer, registry, fake)
        kwargs["issued_at"] = NOW - timedelta(seconds=500)

        with pytest.raises(GovernedPaperRouteBlocked) as exc:
            simulate_governed_paper_order(**kwargs)
        assert "PAPER_SIMULATION_INTENT_INVALID" in str(exc.value)
        assert ledger.snapshot() == []
        assert fake.submitted == []

    def test_fake_broker_failure_reconciles(self, tmp_path: Path):
        """A failing fake broker must not leave an unresolvable reservation.
        The reservation is released (or reconciled) and no fill occurs.
        """
        ledger = PilotExposureReservationLedger(tmp_path / "res.db")
        auth_ledger = PilotAuthorizationLedger(tmp_path / "auth")
        issuer, registry = _issuer_and_registry()
        fake = FakeBroker(fail=True)

        kwargs = _base_kwargs(ledger, auth_ledger, issuer, registry, fake)
        with pytest.raises(GovernedPaperRouteBlocked) as exc:
            simulate_governed_paper_order(**kwargs)
        assert "PAPER_SUBMISSION_FAILED_RECONCILE" in str(exc.value) or "AMBIGUOUS" in str(exc.value)
        assert fake.submitted == []

    def test_denied_reservation_blocks_simulation(self, tmp_path: Path):
        """A reservation that exceeds the CAD 20 ceiling must be denied before
        the fake broker is called.
        """
        ledger = PilotExposureReservationLedger(tmp_path / "res.db")
        auth_ledger = PilotAuthorizationLedger(tmp_path / "auth")
        issuer, registry = _issuer_and_registry()
        fake = FakeBroker()

        # Pre-fill the parent budget so the new reservation is denied.
        d = ledger.reserve(parent_id="P", child_id="PRE", proposed_child_cad=Decimal("19.00"))
        assert d.approved

        kwargs = _base_kwargs(ledger, auth_ledger, issuer, registry, fake)
        with pytest.raises(GovernedPaperRouteBlocked) as exc:
            simulate_governed_paper_order(**kwargs)
        # Either reservation-denied or the reconcile path surfaces.
        assert any(
            frag in str(exc.value)
            for frag in ("PILOT_RESERVATION_DENIED", "PAPER_SIMULATION_AMBIGUOUS_STATE", "PARENT_EXPOSURE_CEILING")
        ), str(exc.value)
        assert fake.submitted == []
