"""Issue #118 P3: approved-trader registry (dual control) and governed, signed signal feed.

All traders here are synthetic. The registry ships empty; nothing is seeded or auto-approved.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from css118_support import (
    ADMIN_A,
    ADMIN_B,
    KEY,
    NOW,
    TRADER,
    activate,
    approve_trader,
    follower,
    mandate_request,
    public_key_b64,
    signal,
    system,
    trader_key,
)
from backend.trading_profiles.consent import ConsentError
from backend.trading_profiles.copy_engine import AUTONOMOUS_SOURCE_ID, CopyTradeEngine
from backend.trading_profiles.signal_feed import SignalFeed, SignalFeedError, sign_signal
from backend.trading_profiles.trader_registry import TraderRegistry, TraderRegistryError


@pytest.fixture(autouse=True)
def _no_ambient_kill_switch(monkeypatch):
    for name in ("CSS_LIVE_ORDER_KILL_SWITCH", "REA_KILL_SWITCH"):
        monkeypatch.delenv(name, raising=False)


def _registry(tmp_path) -> TraderRegistry:
    return TraderRegistry(tmp_path / "tp")


def _propose(reg, trader_id=TRADER, actor=ADMIN_A, assets=("FX", "CRYPTO")):
    return reg.propose(trader_id=trader_id, display_name="Synthetic", public_key_b64=public_key_b64(trader_id),
                       asset_classes=list(assets), actor_ctx=actor, now=NOW)


# ------------------------------------------------------------------ registry
def test_registry_ships_empty_and_no_trader_is_copyable(tmp_path):
    reg = _registry(tmp_path)
    assert reg.list() == []
    with pytest.raises(TraderRegistryError, match="trader_not_approved"):
        reg.require_active(TRADER)


def test_no_registry_or_feed_data_ships_in_the_repository():
    from pathlib import Path
    repo = Path(__file__).resolve().parents[1]
    shipped = [p for pattern in ("**/trader_registry.jsonl", "**/trader_registry.head.json", "**/signal_feed.jsonl")
               for p in repo.glob(pattern) if ".git" not in p.parts]
    assert shipped == []


def test_proposal_alone_does_not_activate(tmp_path):
    reg = _registry(tmp_path)
    assert _propose(reg).status == "PENDING"
    with pytest.raises(TraderRegistryError, match="trader_not_active:PENDING"):
        reg.require_active(TRADER)


def test_dual_control_same_admin_cannot_approve(tmp_path):
    reg = _registry(tmp_path)
    _propose(reg)
    with pytest.raises(TraderRegistryError, match="dual_control_requires_different_approver"):
        reg.approve(TRADER, actor_ctx=ADMIN_A, now=NOW)
    assert reg.approve(TRADER, actor_ctx=ADMIN_B, now=NOW).status == "ACTIVE"


@pytest.mark.parametrize("actor", [None, {}, {"user_id": "t1", "role": "TRADER"}, {"user_id": "a", "role": "ADMIN"},
                                   {"role": "SUPER_USER"}])
def test_only_super_users_can_govern(tmp_path, actor):
    reg = _registry(tmp_path)
    with pytest.raises(TraderRegistryError, match="super_user_required"):
        _propose(reg, actor=actor)


@pytest.mark.parametrize("field,value,reason", [
    ("trader_id", "X", "trader_id_invalid"),
    ("trader_id", "../etc", "trader_id_invalid"),
    ("asset_classes", ["STOCKS"], "asset_scope_invalid"),
    ("asset_classes", [], "asset_scope_invalid"),
    ("public_key_b64", "not-base64!", "public_key_invalid"),
    ("public_key_b64", "AAAA", "public_key_invalid"),
    ("display_name", "  ", "display_name_required"),
])
def test_proposal_validation(tmp_path, field, value, reason):
    kwargs = dict(trader_id=TRADER, display_name="Synthetic", public_key_b64=public_key_b64(), asset_classes=["FX"],
                  actor_ctx=ADMIN_A, now=NOW)
    kwargs[field] = value
    with pytest.raises(TraderRegistryError, match=reason):
        _registry(tmp_path).propose(**kwargs)


def test_scope_enforced(tmp_path):
    reg = _registry(tmp_path)
    approve_trader(reg, assets=("FX",))
    reg.require_active(TRADER, ("FX",))
    with pytest.raises(TraderRegistryError, match="trader_scope_excludes"):
        reg.require_active(TRADER, ("CRYPTO",))


def test_suspend_is_single_control_and_reinstate_needs_another_admin(tmp_path):
    reg = _registry(tmp_path)
    approve_trader(reg)
    assert reg.suspend(TRADER, actor_ctx=ADMIN_A, reason="review", now=NOW).status == "SUSPENDED"
    with pytest.raises(TraderRegistryError, match="dual_control"):
        reg.reinstate(TRADER, actor_ctx=ADMIN_A, reason="ok", now=NOW)
    assert reg.reinstate(TRADER, actor_ctx=ADMIN_B, reason="ok", now=NOW).status == "ACTIVE"


def test_revoked_trader_cannot_be_reinstated_only_reproposed(tmp_path):
    reg = _registry(tmp_path)
    approve_trader(reg)
    reg.revoke(TRADER, actor_ctx=ADMIN_A, reason="terminated", now=NOW)
    with pytest.raises(TraderRegistryError, match="trader_transition_not_allowed"):
        reg.reinstate(TRADER, actor_ctx=ADMIN_B, reason="x", now=NOW)
    assert _propose(reg).status == "PENDING"  # a full new dual-control cycle is required


def test_registry_tampering_fails_closed(tmp_path):
    reg = _registry(tmp_path)
    approve_trader(reg, assets=("FX",))
    lines = reg.path.read_text().splitlines()
    first = json.loads(lines[0])
    first["asset_classes"] = ["CRYPTO", "FX", "FUTURES", "OPTIONS"]  # widen scope by editing the log
    reg.path.write_text("\n".join([json.dumps(first)] + lines[1:]) + "\n")
    with pytest.raises(TraderRegistryError, match="trader_registry_chain_broken"):
        reg.require_active(TRADER, ("FX",))


def test_registry_truncation_of_suspension_detected(tmp_path):
    reg = _registry(tmp_path)
    approve_trader(reg)
    reg.suspend(TRADER, actor_ctx=ADMIN_A, reason="r", now=NOW)
    lines = reg.path.read_text().splitlines()
    reg.path.write_text("\n".join(lines[:-1]) + "\n")  # drop the trailing suspension: chain alone stays valid
    with pytest.raises(TraderRegistryError, match="trader_registry_chain_broken"):  # head anchor catches it
        reg.require_active(TRADER)


def test_registry_missing_head_anchor_fails_closed(tmp_path):
    reg = _registry(tmp_path)
    approve_trader(reg)
    reg.log.head_path.unlink()
    with pytest.raises(TraderRegistryError, match="trader_registry_chain_broken"):
        reg.list()


# ------------------------------------------------------------------ consent + engine integration
def test_copy_mandate_requires_approved_trader(tmp_path):
    engine = CopyTradeEngine(tmp_path / "tp", key_provider=lambda: KEY)
    with pytest.raises(ConsentError, match="trader_not_copyable:trader_not_approved"):
        activate(engine.consent, "f1", "Copy a CSS Trader", "Balanced", mandate=mandate_request(asset_classes=["FX"]),
                 register_trader=False)


def test_copy_proposal_itself_rejected_for_unapproved_trader(tmp_path):
    engine = CopyTradeEngine(tmp_path / "tp", key_provider=lambda: KEY)
    with pytest.raises(ConsentError, match="trader_not_copyable:trader_not_approved"):
        engine.consent.propose_change("f1", operating_mode="Copy a CSS Trader", risk_personality="Balanced",
                                      mandate_request=mandate_request(asset_classes=["FX"]), now=NOW)


def test_copy_mandate_scope_must_fit_trader_scope(tmp_path):
    engine = CopyTradeEngine(tmp_path / "tp", key_provider=lambda: KEY)
    approve_trader(engine.trader_registry, assets=("FX",))
    with pytest.raises(ConsentError, match="trader_scope_excludes"):
        activate(engine.consent, "f1", "Copy a CSS Trader", "Balanced",
                 mandate=mandate_request(asset_classes=["FX", "CRYPTO"]), register_trader=False)


def test_trader_suspended_during_review_blocks_acceptance(tmp_path):
    from css118_support import SESSION, review_all_pages
    from backend.trading_profiles.manual import ACKNOWLEDGEMENT_SHA256
    engine = CopyTradeEngine(tmp_path / "tp", key_provider=lambda: KEY)
    approve_trader(engine.trader_registry)
    change = engine.consent.propose_change("f1", operating_mode="Copy a CSS Trader", risk_personality="Balanced",
                                           mandate_request=mandate_request(asset_classes=["FX"]), now=NOW)
    review = engine.consent.open_review("f1", auth_session_hash=SESSION, change_id=change.change_id, now=NOW)
    review_all_pages(engine.consent, "f1", review)
    engine.trader_registry.suspend(TRADER, actor_ctx=ADMIN_A, reason="incident", now=NOW)
    m = engine.consent.manual_provider()
    with pytest.raises(ConsentError, match="trader_not_copyable"):
        engine.consent.accept("f1", auth_session_hash=SESSION, review_id=review.review_id, acknowledgement_checked=True,
                              acknowledgement_sha256=ACKNOWLEDGEMENT_SHA256, manual_version=m.version,
                              manual_sha256=m.sha256, policy_hash_shown=change.policy_hash, now=NOW)
    assert engine.preferences.get("f1").active is None


def test_suspending_trader_stops_new_copies_immediately(tmp_path):
    engine = CopyTradeEngine(tmp_path / "tp", key_provider=lambda: KEY)
    activate(engine.consent, "f1", "Copy a CSS Trader", "Balanced", mandate=mandate_request(asset_classes=["FX"]))
    assert engine.evaluate(signal(), follower("f1"), system(), now=NOW).outcome == "COPIED"
    engine.trader_registry.suspend(TRADER, actor_ctx=ADMIN_A, reason="incident", now=NOW)
    d = engine.evaluate(signal(signal_id="sig-2"), follower("f1"), system(), now=NOW)
    assert (d.outcome, d.stage, d.reason) == ("REJECTED", "authority", "trader_not_copyable:trader_not_active:SUSPENDED")


# ------------------------------------------------------------------ signal feed
def _payload(**overrides):
    body = {k: v for k, v in asdict(signal()).items()}
    body["issued_at_utc"] = NOW.isoformat()
    body.update(overrides)
    return body


def _feed(tmp_path, assets=("FX", "CRYPTO")):
    reg = _registry(tmp_path)
    approve_trader(reg, assets=assets)
    return SignalFeed(tmp_path / "tp", reg)


def test_valid_signed_signal_accepted_and_logged(tmp_path):
    feed = _feed(tmp_path)
    s = feed.ingest(sign_signal(trader_key(), _payload()), now=NOW + timedelta(seconds=3))
    assert s.trader_id == TRADER and s.signal_id == "sig-1"
    assert [e["signal_id"] for e in feed.accepted()] == ["sig-1"]


def test_signal_from_unapproved_trader_rejected(tmp_path):
    feed = SignalFeed(tmp_path / "tp", _registry(tmp_path))  # empty registry
    with pytest.raises(SignalFeedError, match="trader_not_authorized:trader_not_approved"):
        feed.ingest(sign_signal(trader_key(), _payload()), now=NOW)


def test_signal_signed_by_wrong_key_rejected(tmp_path):
    feed = _feed(tmp_path)
    impostor = Ed25519PrivateKey.from_private_bytes(b"\x07" * 32)
    with pytest.raises(SignalFeedError, match="signature_invalid"):
        feed.ingest(sign_signal(impostor, _payload()), now=NOW)


def test_tampered_payload_rejected(tmp_path):
    feed = _feed(tmp_path)
    envelope = sign_signal(trader_key(), _payload())
    envelope["payload"]["reference_price"] = 1.5
    with pytest.raises(SignalFeedError, match="signature_invalid"):
        feed.ingest(envelope, now=NOW)


@pytest.mark.parametrize("delta,reason", [(timedelta(seconds=121), "signal_stale"), (timedelta(seconds=-6), "signal_from_future")])
def test_freshness_window(tmp_path, delta, reason):
    feed = _feed(tmp_path)
    with pytest.raises(SignalFeedError, match=reason):
        feed.ingest(sign_signal(trader_key(), _payload()), now=NOW + delta)


def test_replay_rejected(tmp_path):
    feed = _feed(tmp_path)
    envelope = sign_signal(trader_key(), _payload())
    feed.ingest(envelope, now=NOW)
    with pytest.raises(SignalFeedError, match="signal_replay"):
        feed.ingest(envelope, now=NOW + timedelta(seconds=1))


def test_out_of_scope_asset_rejected(tmp_path):
    feed = _feed(tmp_path, assets=("FX",))
    with pytest.raises(SignalFeedError, match="trader_scope_excludes"):
        feed.ingest(sign_signal(trader_key(), _payload(asset_class="CRYPTO", symbol="BTC/USD")), now=NOW)


@pytest.mark.parametrize("overrides,reason", [
    ({"trader_id": AUTONOMOUS_SOURCE_ID}, "reserved_source_id"),
    ({"trader_id": "USER_MANUAL:x"}, "payload_id_invalid|reserved_source_id"),
    ({"probability": float("nan")}, "payload_number_invalid|signature"),
    ({"probability": "0.9"}, "payload_number_invalid"),
    ({"side": "HOLD"}, "payload_side_or_asset_invalid"),
    ({"leverage": 50}, "payload_unknown_fields"),
    ({"issued_at_utc": "2026-10-16T12:00:00"}, "issued_at_invalid"),
    ({"signal_id": "../../x"}, "payload_id_invalid"),
])
def test_malformed_payloads_rejected(tmp_path, overrides, reason):
    feed = _feed(tmp_path)
    payload = _payload(**overrides)
    try:
        envelope = sign_signal(trader_key(), payload)
    except ValueError:  # NaN cannot even be canonically signed
        envelope = {"payload": payload, "signature_b64": ""}
    with pytest.raises(SignalFeedError, match=reason):
        feed.ingest(envelope, now=NOW)


def test_authenticated_rejections_logged_without_consuming_the_signal_id(tmp_path):
    feed = _feed(tmp_path)
    with pytest.raises(SignalFeedError, match="signal_stale"):
        feed.ingest(sign_signal(trader_key(), _payload(issued_at_utc=(NOW - timedelta(minutes=5)).isoformat())), now=NOW)
    feed.ingest(sign_signal(trader_key(), _payload()), now=NOW)  # a fresh signal with the same id is accepted
    events = [json.loads(line)["event"] for line in feed.path.read_text().splitlines()]
    assert events == ["REJECTED", "ACCEPTED"]


def test_unauthenticated_submissions_are_not_written(tmp_path):
    feed = _feed(tmp_path)
    for envelope in ({"payload": _payload(), "signature_b64": "AAAA"},
                     sign_signal(Ed25519PrivateKey.from_private_bytes(b"\x07" * 32), _payload()),
                     sign_signal(trader_key("trader-unknown"), _payload(trader_id="trader-unknown")),
                     {"payload": "junk"}):
        with pytest.raises(SignalFeedError):
            feed.ingest(envelope, now=NOW)
    assert not feed.path.exists()


def test_feed_ledger_tampering_fails_closed(tmp_path):
    feed = _feed(tmp_path)
    feed.ingest(sign_signal(trader_key(), _payload()), now=NOW)
    feed.path.write_text(feed.path.read_text().replace("ACCEPTED", "REJECTED"))  # try to re-open a replay window
    with pytest.raises(SignalFeedError, match="signal_feed_chain_broken"):
        feed.ingest(sign_signal(trader_key(), _payload()), now=NOW)


def test_feed_truncation_cannot_reopen_replay_window(tmp_path):
    feed = _feed(tmp_path)
    envelope = sign_signal(trader_key(), _payload())
    feed.ingest(envelope, now=NOW)
    feed.path.write_text("")
    with pytest.raises(SignalFeedError, match="signal_feed_chain_broken"):
        feed.ingest(envelope, now=NOW)
