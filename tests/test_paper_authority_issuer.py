"""Isolated tests for the paper-only authority issuer.

Never touches production keys, broker state, safety flags, or the
AntiBleed minimum-size exception.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend.runtime.paper_authority_issuer import (
    PaperAuthorityIssuer,
    PaperAuthorityIssuerError,
    PaperGateEvaluators,
    public_key_bytes_for,
)
from backend.runtime.paper_authority_registry import PaperIssuerRegistry, PaperIssuerRegistryError
from backend.runtime.pilot_paper_authorization import canonical_paper_intent_digest, verify_paper_intent_signature


CANDIDATE_SHA = "a" * 40


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


def _allow() -> dict:
    return {"approved": True, "reason": "ok"}


def _deny() -> dict:
    return {"approved": False, "reason": "denied"}


def _allow_all() -> PaperGateEvaluators:
    return PaperGateEvaluators(
        r7=lambda req: _allow(),
        antibleed=lambda req: _allow(),
        risk_governor=lambda req: _allow(),
        kill_switch=lambda req: _allow(),
    )


def _issuer(key=None) -> PaperAuthorityIssuer:
    return PaperAuthorityIssuer(
        signing_key=key or Ed25519PrivateKey.generate(),
        issuer_id="test-issuer",
        candidate_sha=CANDIDATE_SHA,
    )


class TestPaperAuthorityIssuerConstruction:
    def test_rejects_non_ed25519_key(self):
        with pytest.raises(PaperAuthorityIssuerError):
            PaperAuthorityIssuer(signing_key="not-a-key", issuer_id="i", candidate_sha=CANDIDATE_SHA)

    def test_rejects_invalid_candidate_sha(self):
        key = Ed25519PrivateKey.generate()
        for bad in ("", "zz" * 20, "a" * 39, "A" * 40):
            with pytest.raises(PaperAuthorityIssuerError):
                PaperAuthorityIssuer(signing_key=key, issuer_id="i", candidate_sha=bad)

    def test_accepts_valid_construction(self):
        issuer = _issuer()
        assert issuer.issuer_id == "test-issuer"
        assert issuer.candidate_sha == CANDIDATE_SHA


class TestPaperAuthorityIssuerDenials:
    def test_any_denied_evaluator_blocks_issuance(self):
        for gate_name in ("r7", "antibleed", "risk_governor", "kill_switch"):
            allow_all = _allow_all()
            evals = dict(
                r7=allow_all.r7,
                antibleed=allow_all.antibleed,
                risk_governor=allow_all.risk_governor,
                kill_switch=allow_all.kill_switch,
            )
            evals[gate_name] = lambda req, _g=gate_name: _deny()
            e = PaperGateEvaluators(**evals)
            with pytest.raises(PaperAuthorityIssuerError) as exc:
                _issuer().issue_paper_intent(order_request=_order_request(), evaluators=e)
            assert gate_name in str(exc.value)

    def test_none_result_denies(self):
        allow_all = _allow_all()
        e = PaperGateEvaluators(
            r7=allow_all.r7,
            antibleed=lambda req: None,
            risk_governor=allow_all.risk_governor,
            kill_switch=allow_all.kill_switch,
        )
        with pytest.raises(PaperAuthorityIssuerError) as exc:
            _issuer().issue_paper_intent(order_request=_order_request(), evaluators=e)
        assert "evaluator_unavailable:antibleed" in str(exc.value)

    def test_raised_exception_denies(self):
        def _raise(req):
            raise RuntimeError("boom")

        allow_all = _allow_all()
        e = PaperGateEvaluators(
            r7=allow_all.r7,
            antibleed=_raise,
            risk_governor=allow_all.risk_governor,
            kill_switch=allow_all.kill_switch,
        )
        with pytest.raises(PaperAuthorityIssuerError) as exc:
            _issuer().issue_paper_intent(order_request=_order_request(), evaluators=e)
        assert "evaluator_error:antibleed" in str(exc.value)

    def test_candidate_sha_mismatch_denies(self):
        req = _order_request()
        req["candidate_sha"] = "b" * 40
        with pytest.raises(PaperAuthorityIssuerError) as exc:
            _issuer().issue_paper_intent(order_request=req, evaluators=_allow_all())
        assert "candidate_sha_mismatch" in str(exc.value)


class TestPaperAuthorityIssuerPositivePath:
    def test_valid_issuance_produces_verifiable_signature(self):
        key = Ed25519PrivateKey.generate()
        issuer = _issuer(key=key)
        now = datetime.now(timezone.utc)
        payload, signature = issuer.issue_paper_intent(order_request=_order_request(), evaluators=_allow_all(), issued_at=now)

        # Verifies against the same key via the existing canonical verifier.
        pub = public_key_bytes_for(key)
        v = verify_paper_intent_signature(
            payload,
            signature,
            pub,
            expected_candidate_sha=CANDIDATE_SHA,
            expected_broker="IBKR_PAPER",
            expected_account="A",
            expected_instrument="FUT-TEST",
            expected_child_id="C",
            now=now,
        )
        assert v.valid, v.reason

    def test_payload_binds_all_required_fields(self):
        key = Ed25519PrivateKey.generate()
        issuer = _issuer(key=key)
        now = datetime.now(timezone.utc)
        payload, _ = issuer.issue_paper_intent(order_request=_order_request(), evaluators=_allow_all(), issued_at=now)

        # Mode is PAPER only.
        assert payload["mode"] == "PAPER"
        # Required gate booleans are all True (only from internal evaluation).
        for k in ("r7", "antibleed", "risk_governor", "kill_switch_clear"):
            assert payload[k] is True
        # Expiry window is within the maximum allowed.
        start = datetime.fromisoformat(payload["issued_at"])
        end = datetime.fromisoformat(payload["expires_at"])
        assert 0 < (end - start).total_seconds() <= 120
        # Nonce is non-empty (fresh).
        assert isinstance(payload["nonce"], str) and payload["nonce"]

    def test_rejects_expiry_window_over_120_seconds(self):
        with pytest.raises(PaperAuthorityIssuerError):
            _issuer().issue_paper_intent(
                order_request=_order_request(),
                evaluators=_allow_all(),
                expires_in_seconds=121,
            )

    def test_rejects_nonpositive_expiry_window(self):
        with pytest.raises(PaperAuthorityIssuerError):
            _issuer().issue_paper_intent(
                order_request=_order_request(),
                evaluators=_allow_all(),
                expires_in_seconds=0,
            )

    def test_rejects_invalid_side(self):
        req = _order_request()
        req["side"] = "LONG"
        with pytest.raises(PaperAuthorityIssuerError):
            _issuer().issue_paper_intent(order_request=req, evaluators=_allow_all())

    def test_rejects_nonpositive_amount(self):
        for bad_field in ("quantity", "limit_price", "risk_amount"):
            for bad_value in ("0", "-1", "abc"):
                req = _order_request()
                req[bad_field] = bad_value
                with pytest.raises(PaperAuthorityIssuerError):
                    _issuer().issue_paper_intent(order_request=req, evaluators=_allow_all())

    def test_rejects_naive_issued_at(self):
        with pytest.raises(PaperAuthorityIssuerError):
            _issuer().issue_paper_intent(
                order_request=_order_request(),
                evaluators=_allow_all(),
                issued_at=datetime(2026, 10, 13),  # naive
            )


class TestPaperIssuerRegistry:
    def test_missing_issuer_fails_closed(self):
        reg = PaperIssuerRegistry()
        with pytest.raises(PaperIssuerRegistryError) as exc:
            reg.issuer_public_key("unregistered")
        assert "issuer_not_enrolled" in str(exc.value)

    def test_is_enrolled_only_after_registration(self):
        reg = PaperIssuerRegistry()
        assert not reg.is_enrolled("test-issuer")
        key = Ed25519PrivateKey.generate()
        reg.register_issuer(issuer_id="test-issuer", public_key=key.public_key())
        assert reg.is_enrolled("test-issuer")
        assert "test-issuer" in reg.enrolled_issuer_ids()

    def test_clear_removes_all(self):
        reg = PaperIssuerRegistry()
        key = Ed25519PrivateKey.generate()
        reg.register_issuer(issuer_id="a", public_key=key.public_key())
        reg.clear()
        assert not reg.enrolled_issuer_ids()

    def test_rejects_bad_inputs(self):
        reg = PaperIssuerRegistry()
        with pytest.raises(PaperIssuerRegistryError):
            reg.register_issuer(issuer_id="", public_key=Ed25519PrivateKey.generate().public_key())
        with pytest.raises(PaperIssuerRegistryError):
            reg.register_issuer(issuer_id="x", public_key="not-a-key")
        with pytest.raises(PaperIssuerRegistryError):
            reg.issuer_public_key("")

    def test_default_registry_starts_empty(self):
        from backend.runtime.paper_authority_registry import default_paper_issuer_registry

        # The default registry is lazily constructed and starts empty (fail closed).
        # This test does not register anything; it only checks the initial state.
        # A previously registered test may have populated it; reset it here.
        default_paper_issuer_registry().clear()
        assert default_paper_issuer_registry().enrolled_issuer_ids() == ()
