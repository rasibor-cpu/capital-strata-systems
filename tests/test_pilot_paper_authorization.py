from datetime import datetime, timedelta, timezone
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from backend.runtime.pilot_paper_authorization import (
    canonical_paper_intent_digest, verify_paper_intent_signature,
)


def sample():
    now = datetime.now(timezone.utc)
    payload = {
        "mode":"PAPER", "candidate_sha":"a"*40, "broker":"IBKR_PAPER",
        "account":"A", "instrument":"FUT-TEST", "parent_id":"P", "child_id":"C",
        "side":"BUY", "quantity":"1", "limit_price":"5", "quote_currency":"USD",
        "risk_currency":"CAD", "risk_amount":"6.25",
        "issued_at":(now-timedelta(seconds=1)).isoformat(),
        "expires_at":(now+timedelta(seconds=30)).isoformat(),
        "nonce":"unique-test", "r7":True, "antibleed":True,
        "risk_governor":True, "kill_switch_clear":True
    }
    key = Ed25519PrivateKey.generate()
    signature = key.sign(canonical_paper_intent_digest(payload))
    pub = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    fields = dict(expected_candidate_sha="a"*40, expected_broker="IBKR_PAPER",
                  expected_account="A", expected_instrument="FUT-TEST",
                  expected_child_id="C", now=now)
    return payload, signature, pub, fields


def test_valid_signature_is_only_a_verification_not_execution_authority():
    p, sig, pub, fields = sample()
    d = verify_paper_intent_signature(p, sig, pub, **fields)
    assert d.valid and d.reason == "SIGNATURE_AND_BINDING_VERIFIED_ONLY"


def test_unsigned_and_mismatched_intents_fail():
    p, sig, pub, fields = sample()
    assert not verify_paper_intent_signature(p, b"", pub, **fields).valid
    for key, bad in (("expected_child_id", "OTHER"), ("expected_broker", "LIVE"),
                     ("expected_account", "WRONG"), ("expected_candidate_sha", "b"*40)):
        opts = dict(fields)
        opts[key] = bad
        assert not verify_paper_intent_signature(p, sig, pub, **opts).valid


def test_tampered_risk_gate_live_mode_and_price_fail():
    for key, bad in (("r7", False), ("antibleed", False), ("kill_switch_clear", False),
                     ("mode", "LIVE"), ("limit_price", "5.01"), ("risk_amount","999")):
        p, sig, pub, fields = sample()
        p[key] = bad
        assert not verify_paper_intent_signature(p, sig, pub, **fields).valid


def test_expired_and_unknown_field_fail():
    p, sig, pub, fields = sample()
    fields["now"] += timedelta(seconds=500)
    assert not verify_paper_intent_signature(p, sig, pub, **fields).valid
    p, sig, pub, fields = sample()
    p["unexpected"] = True
    assert not verify_paper_intent_signature(p, sig, pub, **fields).valid
