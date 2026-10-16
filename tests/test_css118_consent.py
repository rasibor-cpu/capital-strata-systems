"""Issue #118 consent gate, controlled manual, user limits, CSS-Assisted mode and migration.

Security focus: direct API/service bypass, acknowledgement forgery, replay, session
isolation, tampering (manual, pending change, ledger, active settings), material
document updates, atomic activation, restart persistence and the emergency exception.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from css118_support import KEY, NOW, SESSION, activate, follower, mandate_request, review_all_pages, signal, system
from backend.trading_profiles.consent import ConsentError
from backend.trading_profiles.copy_engine import AUTONOMOUS_SOURCE_ID, CopyTradeEngine, ProposalError
from backend.trading_profiles.exits import evaluate_exit
from backend.trading_profiles.manual import (
    ACKNOWLEDGEMENT_SHA256,
    ACKNOWLEDGEMENT_TEXT,
    MANIFEST_PATH,
    MANUAL_PATH,
    ManualIntegrityError,
    current_manual,
    load_manual,
)
from backend.trading_profiles.operating_modes import OperatingMode
from backend.trading_profiles.preferences import LEGACY_SCHEMA_V1, PreferencesError, PreferencesStore
from backend.trading_profiles.risk_personalities import RiskPersonality, policy_for
from backend.trading_profiles.service import TradingProfileService

OWNER_ACK = ("I confirm that I have read and understood the CSS User Operating Manual, Trading Assumptions and Risk "
             "Disclosure Agreement. I understand that trading involves the risk of losing some or all of my invested "
             "capital, that profits are not guaranteed, and that I bear the investment risks associated with my trading "
             "decisions and authorized CSS trading activities.")


@pytest.fixture(autouse=True)
def _no_ambient_kill_switch(monkeypatch):
    for name in ("CSS_LIVE_ORDER_KILL_SWITCH", "REA_KILL_SWITCH"):
        monkeypatch.delenv(name, raising=False)


def _engine(tmp_path, manual_provider=current_manual) -> CopyTradeEngine:
    return CopyTradeEngine(tmp_path / "tp", key_provider=lambda: KEY, manual_provider=manual_provider)


def _prepared(engine, user="u1", mode="CSS Autonomous Trading", personality="Balanced", **kw):
    change = engine.consent.propose_change(user, operating_mode=mode, risk_personality=personality, now=NOW, **kw)
    review = engine.consent.open_review(user, auth_session_hash=SESSION, change_id=change.change_id, now=NOW)
    return change, review


def _accept(engine, change, review, user="u1", session=SESSION, **overrides):
    manual = engine.consent.manual_provider()
    kwargs = dict(auth_session_hash=session, review_id=review.review_id, acknowledgement_checked=True,
                  acknowledgement_sha256=ACKNOWLEDGEMENT_SHA256, manual_version=manual.version,
                  manual_sha256=manual.sha256, policy_hash_shown=change.policy_hash, now=NOW)
    kwargs.update(overrides)
    return engine.consent.accept(user, **kwargs)


def _copy_manual(tmp_path: Path) -> tuple[Path, Path]:
    d = tmp_path / "manual"
    d.mkdir()
    shutil.copy(MANUAL_PATH, d / MANUAL_PATH.name)
    shutil.copy(MANIFEST_PATH, d / MANIFEST_PATH.name)
    return d / MANUAL_PATH.name, d / MANIFEST_PATH.name


def _reissue(manual_path: Path, manifest_path: Path, *, version: str, material: bool, append: str) -> None:
    """Simulate the controlled re-issue tool on a copy of the manual."""
    import hashlib

    from backend.trading_profiles.manual import sha256_text, split_pages

    manual_path.write_text(manual_path.read_text(encoding="utf-8").replace(
        "<!-- css-manual-page: glossary", append + "\n<!-- css-manual-page: glossary"), encoding="utf-8")
    raw = manual_path.read_bytes()
    manifest = json.loads(manifest_path.read_text())
    manifest["pages"] = [{"page_id": p, "title": t, "sha256": sha256_text(b)} for p, t, b in split_pages(raw.decode())]
    manifest["sha256"] = hashlib.sha256(raw).hexdigest()
    manifest["version"] = version
    manifest["history"].append({"version": version, "effective_date": "2026-11-01", "sha256": manifest["sha256"],
                                "summary": "test update", "material": material})
    manifest_path.write_text(json.dumps(manifest))


# ---------------------------------------------------------------- controlled manual
def test_manual_is_controlled_complete_and_uses_owner_acknowledgement():
    manual = load_manual()
    assert ACKNOWLEDGEMENT_TEXT == OWNER_ACK
    assert manual.version == "1.1.0" and manual.history[-1]["material"] is True
    assert [h["version"] for h in manual.history] == ["1.0.0", "1.1.0"]
    assert len(manual.pages) == 12
    text = manual.text
    for required in ("Simulated Trading", "CSS-Assisted Trading", "Copy a CSS Trader", "CSS Autonomous Trading",
                     "Ultra Aggressive", "can only tighten", "gap", "slippage", "Crypto-assets", "Futures", "Options",
                     "Platform outages", "kill switch", "Tax", "Glossary", "Support", "not guarantee",
                     "non-waivable", "copied trader", "reauthoriz"):
        assert required.lower() in text.lower(), required


def test_manual_tampering_fails_closed(tmp_path):
    manual_path, manifest_path = _copy_manual(tmp_path)
    assert load_manual(manual_path, manifest_path).sha256 == current_manual().sha256
    manual_path.write_text(manual_path.read_text().replace("CSS does **not** guarantee profits", "CSS guarantees profits"))
    with pytest.raises(ManualIntegrityError):
        load_manual(manual_path, manifest_path)


# ---------------------------------------------------------------- acceptance gate
def test_cannot_accept_without_reviewing_every_page(tmp_path):
    engine = _engine(tmp_path)
    change, review = _prepared(engine)
    with pytest.raises(ConsentError, match="pages_not_reviewed"):
        _accept(engine, change, review)
    # Reviewing all but the last page is still not enough.
    for page_id in list(review.pages)[:-1]:
        page = engine.consent.present_page("u1", auth_session_hash=SESSION, review_id=review.review_id, page_id=page_id, now=NOW)
        engine.consent.mark_reviewed("u1", auth_session_hash=SESSION, review_id=review.review_id, page_id=page_id,
                                     method="scroll_bottom", page_sha256=page["sha256"], now=NOW)
    with pytest.raises(ConsentError, match="pages_not_reviewed:support"):
        _accept(engine, change, review)
    assert engine.preferences.get("u1").active is None


def test_page_must_be_presented_before_review_and_match_version(tmp_path):
    engine = _engine(tmp_path)
    _, review = _prepared(engine)
    with pytest.raises(ConsentError, match="page_not_presented"):
        engine.consent.mark_reviewed("u1", auth_session_hash=SESSION, review_id=review.review_id, page_id="about",
                                     method="scroll_bottom", page_sha256="x", now=NOW)
    engine.consent.present_page("u1", auth_session_hash=SESSION, review_id=review.review_id, page_id="about", now=NOW)
    with pytest.raises(ConsentError, match="page_version_mismatch"):
        engine.consent.mark_reviewed("u1", auth_session_hash=SESSION, review_id=review.review_id, page_id="about",
                                     method="scroll_bottom", page_sha256="0" * 64, now=NOW)
    with pytest.raises(ConsentError, match="review_method_invalid"):
        engine.consent.mark_reviewed("u1", auth_session_hash=SESSION, review_id=review.review_id, page_id="about",
                                     method="skipped", page_sha256="0" * 64, now=NOW)


@pytest.mark.parametrize("checked", [False, None, "true", 1, "yes"])
def test_acknowledgement_must_be_explicit_boolean_true(tmp_path, checked):
    engine = _engine(tmp_path)
    change, review = _prepared(engine)
    review_all_pages(engine.consent, "u1", review)
    with pytest.raises(ConsentError, match="acknowledgement_not_checked"):
        _accept(engine, change, review, acknowledgement_checked=checked)


@pytest.mark.parametrize("override,reason", [
    ({"acknowledgement_sha256": "0" * 64}, "acknowledgement_text_mismatch"),
    ({"manual_version": "0.9.0"}, "manual_version_mismatch"),
    ({"manual_sha256": "0" * 64}, "manual_version_mismatch"),
    ({"policy_hash_shown": "0" * 64}, "policy_hash_mismatch"),
])
def test_acceptance_is_bound_to_document_ack_and_policy(tmp_path, override, reason):
    engine = _engine(tmp_path)
    change, review = _prepared(engine)
    review_all_pages(engine.consent, "u1", review)
    with pytest.raises(ConsentError, match=reason):
        _accept(engine, change, review, **override)
    assert engine.preferences.get("u1").active is None


def test_replay_and_session_isolation(tmp_path):
    engine = _engine(tmp_path)
    change, review = _prepared(engine)
    review_all_pages(engine.consent, "u1", review)
    with pytest.raises(ConsentError, match="review_not_found"):
        _accept(engine, change, review, session="another-session")  # same user, different session
    with pytest.raises(ConsentError, match="review_not_found"):
        _accept(engine, change, review, user="intruder")  # different user
    receipt = _accept(engine, change, review)
    assert receipt["live_trading_authorized"] is False
    with pytest.raises(ConsentError, match="review_closed"):
        _accept(engine, change, review)  # replay of the same acceptance
    with pytest.raises(ConsentError, match="change_not_pending"):
        engine.consent.open_review("u1", auth_session_hash=SESSION, change_id=change.change_id, now=NOW)


def test_expired_change_and_review(tmp_path):
    engine = _engine(tmp_path)
    change, review = _prepared(engine)
    review_all_pages(engine.consent, "u1", review)
    with pytest.raises(ConsentError, match="review_expired"):
        _accept(engine, change, review, now=NOW + timedelta(hours=3))
    change2 = engine.consent.propose_change("u1", operating_mode="Simulated Trading", now=NOW)
    with pytest.raises(ConsentError, match="change_expired"):
        engine.consent.open_review("u1", auth_session_hash=SESSION, change_id=change2.change_id, now=NOW + timedelta(hours=1))


def test_tampered_pending_change_is_rejected(tmp_path):
    engine = _engine(tmp_path)
    change, review = _prepared(engine, personality="Safe")
    review_all_pages(engine.consent, "u1", review)
    state = json.loads(engine.consent.state_path.read_text())
    state["changes"][change.change_id]["risk_personality"] = "Ultra Aggressive"
    engine.consent.state_path.write_text(json.dumps(state))
    with pytest.raises(ConsentError, match="pending_change_tampered"):
        _accept(engine, change, review)


def test_activation_is_transactional(tmp_path, monkeypatch):
    engine = _engine(tmp_path)
    change, review = _prepared(engine)
    review_all_pages(engine.consent, "u1", review)

    def boom(*a, **k):
        raise RuntimeError("disk full")

    monkeypatch.setattr(engine.preferences, "activate", boom)
    with pytest.raises(RuntimeError):
        _accept(engine, change, review)
    # Evidence recorded first, but nothing is active and trading stays blocked.
    assert engine.consent.ledger.records()[-1]["record_type"] == "ACCEPTED"
    assert engine.preferences.get("u1").active is None
    assert engine.evaluate(signal(trader_id=AUTONOMOUS_SOURCE_ID), follower("u1"), system(), now=NOW).reason == "consent_missing"


def test_restart_persistence_receipts_and_history(tmp_path):
    engine = _engine(tmp_path)
    receipt = activate(engine.consent, "u1", "CSS Autonomous Trading", "Conservative")
    restarted = TradingProfileService(tmp_path / "tp", key_provider=lambda: KEY)
    assert restarted.consent.verify_active("u1") == (True, "consent_valid")
    receipts = restarted.consent.receipts("u1")
    assert [r["receipt_id"] for r in receipts] == [receipt["receipt_id"]]
    assert receipts[0]["document"]["version"] == "1.1.0" and receipts[0]["pages_reviewed"] == 12
    assert restarted.consent.receipts("someone-else") == []


def test_tampered_ledger_or_active_settings_block_trading(tmp_path):
    engine = _engine(tmp_path)
    activate(engine.consent, "u1", "CSS Autonomous Trading", "Balanced")
    sig = signal(trader_id=AUTONOMOUS_SOURCE_ID)
    assert engine.evaluate(sig, follower("u1"), system(), now=NOW).outcome == "COPIED"

    prefs = json.loads(engine.preferences.path.read_text())
    prefs["users"]["u1"]["active"]["risk_personality"] = "Ultra Aggressive"
    engine.preferences.path.write_text(json.dumps(prefs))
    d = engine.evaluate(replace(sig, signal_id="s2", symbol="GBP/USD"), follower("u1"), system(), now=NOW)
    assert (d.stage, d.reason) == ("consent", "active_settings_tampered")

    prefs["users"]["u1"]["active"]["risk_personality"] = "Balanced"
    engine.preferences.path.write_text(json.dumps(prefs))
    lines = engine.consent.ledger.path.read_text().splitlines()
    record = json.loads(lines[0])
    record["operating_mode"] = "Copy a CSS Trader"
    engine.consent.ledger.path.write_text(json.dumps(record) + "\n")
    d = engine.evaluate(replace(sig, signal_id="s3", symbol="AUD/USD"), follower("u1"), system(), now=NOW)
    assert d.stage == "consent" and d.reason.startswith("consent_unverifiable")


# ---------------------------------------------------------------- document updates
def test_material_update_requires_renewal_but_never_blocks_risk_reduction(tmp_path):
    manual_path, manifest_path = _copy_manual(tmp_path)
    provider = {"fn": lambda: load_manual(manual_path, manifest_path)}
    engine = _engine(tmp_path, manual_provider=lambda: provider["fn"]())
    activate(engine.consent, "u1", "CSS Autonomous Trading", "Balanced")
    sig = signal(trader_id=AUTONOMOUS_SOURCE_ID)
    d = engine.evaluate(sig, follower("u1"), system(), now=NOW)
    position = engine.position_from_decision(d, sig, opened_at=NOW)

    _reissue(manual_path, manifest_path, version="9.0.0", material=True, append="Material addition.")
    blocked = engine.evaluate(replace(sig, signal_id="s2", symbol="GBP/USD"), follower("u1"), system(), now=NOW)
    assert (blocked.stage, blocked.reason) == ("consent", "consent_renewal_required")
    service = TradingProfileService(tmp_path / "tp", key_provider=lambda: KEY, manual_provider=provider["fn"])
    assert "renewed_acceptance" in service.startup_state("u1", session_id=SESSION)["needs"]
    # Emergency risk reduction still works without renewed consent.
    assert service.pause("u1")["paused"] is True
    assert evaluate_exit(position, policy_for(RiskPersonality.BALANCED), mark_price=position.entry_price * 0.97,
                         now=NOW).reason == "STOP_LOSS"
    with pytest.raises(ConsentError, match="consent_renewal_required"):
        service.resume("u1")
    # Renewal of the same settings under the new version restores trading.
    receipt = activate(engine.consent, "u1", "CSS Autonomous Trading", "Balanced")
    assert receipt["kind"] == "RENEWAL" and receipt["document"]["version"] == "9.0.0"
    service.resume("u1")
    assert engine.evaluate(replace(sig, signal_id="s3", symbol="AUD/USD"), follower("u1"), system(), now=NOW).outcome == "COPIED"


def test_non_material_update_does_not_require_renewal(tmp_path):
    manual_path, manifest_path = _copy_manual(tmp_path)
    engine = _engine(tmp_path, manual_provider=lambda: load_manual(manual_path, manifest_path))
    activate(engine.consent, "u1", "CSS Autonomous Trading", "Balanced")
    _reissue(manual_path, manifest_path, version="1.0.1", material=False, append="Typo fix.")
    assert engine.consent.verify_active("u1") == (True, "consent_valid")


def test_review_restarts_if_manual_changes_mid_review(tmp_path):
    manual_path, manifest_path = _copy_manual(tmp_path)
    engine = _engine(tmp_path, manual_provider=lambda: load_manual(manual_path, manifest_path))
    change, review = _prepared(engine)
    review_all_pages(engine.consent, "u1", review)
    _reissue(manual_path, manifest_path, version="9.0.0", material=True, append="Changed.")
    with pytest.raises(ConsentError, match="manual_version_mismatch|manual_changed_restart_review"):
        _accept(engine, change, review, manual_version="1.1.0")
    manual = engine.consent.manual_provider()
    with pytest.raises(ConsentError, match="manual_changed_restart_review"):
        _accept(engine, change, review, manual_version=manual.version, manual_sha256=manual.sha256)


# ---------------------------------------------------------------- changes and emergency
def test_every_change_needs_new_consent_and_applies_prospectively(tmp_path):
    engine = _engine(tmp_path)
    activate(engine.consent, "u1", "CSS Autonomous Trading", "Conservative")
    old_hash = engine.preferences.get("u1").active.policy_hash
    change = engine.consent.propose_change("u1", operating_mode="CSS Autonomous Trading", risk_personality="Aggressive", now=NOW)
    assert change.kind == "CHANGE"
    # Proposing is not activating.
    assert engine.preferences.get("u1").active.policy_hash == old_hash
    assert engine.preferences.get("u1").active.risk_personality is RiskPersonality.CONSERVATIVE


def test_emergency_pause_and_revoke_need_no_consent(tmp_path):
    service = TradingProfileService(tmp_path / "tp", key_provider=lambda: KEY)
    assert service.pause("never-onboarded")["paused"] is True
    engine = _engine(tmp_path)
    activate(engine.consent, "c", "Copy a CSS Trader", "Balanced",
             mandate=mandate_request(asset_classes=["FX", "CRYPTO", "FUTURES"]))
    mandate_id = engine.preferences.get("c").active.mandate_id
    # Break consent on purpose: revocation must still work.
    engine.consent.ledger.path.write_text("")
    assert service.revoke_mandate("c", mandate_id, "emergency")["revoked_at_utc"]
    service.pause("c")
    assert engine.evaluate(signal(), follower("c"), system(), now=NOW).reason in {"trading_paused_by_user", "consent_record_missing"}


def test_paused_user_cannot_trade_until_resumed_with_valid_consent(tmp_path):
    engine = _engine(tmp_path)
    service = TradingProfileService(tmp_path / "tp", key_provider=lambda: KEY)
    activate(engine.consent, "u1", "CSS Autonomous Trading", "Balanced")
    service.pause("u1")
    sig = signal(trader_id=AUTONOMOUS_SOURCE_ID)
    assert engine.evaluate(sig, follower("u1"), system(), now=NOW).reason == "trading_paused_by_user"
    service.resume("u1")
    assert engine.evaluate(sig, follower("u1"), system(), now=NOW).outcome == "COPIED"


# ---------------------------------------------------------------- user limits
def test_user_limits_only_tighten(tmp_path):
    engine = _engine(tmp_path)
    for loose in ({"max_position_pct_of_equity": 7.0}, {"min_probability": 0.5}, {"max_open_copied_positions": 6},
                  {"allowed_asset_classes": ["OPTIONS"]}, {"max_position_pct_of_equity": -1}, {"unknown": 1}):
        with pytest.raises(ConsentError):
            engine.consent.propose_change("u1", operating_mode="CSS Autonomous Trading", risk_personality="Balanced",
                                          limits=loose, now=NOW)
    activate(engine.consent, "u1", "CSS Autonomous Trading", "Balanced", limits={"max_position_pct_of_equity": 3.0})
    d = engine.evaluate(signal(trader_id=AUTONOMOUS_SOURCE_ID), follower("u1"), system(), now=NOW)
    assert d.outcome == "COPIED" and d.notional == 300.0  # Balanced alone would size 600


def test_mandate_scope_must_fit_personality(tmp_path):
    engine = _engine(tmp_path)
    with pytest.raises(ConsentError, match="mandate_scope_outside_policy"):
        engine.consent.propose_change("u1", operating_mode="Copy a CSS Trader", risk_personality="Safe",
                                      mandate_request=mandate_request(asset_classes=["FX", "CRYPTO"]), now=NOW)
    with pytest.raises(ConsentError, match="mandate_request_required"):
        engine.consent.propose_change("u1", operating_mode="Copy a CSS Trader", risk_personality="Safe", now=NOW)
    with pytest.raises(ConsentError, match="mandate_request_not_allowed_for_mode"):
        engine.consent.propose_change("u1", operating_mode="CSS Autonomous Trading", risk_personality="Safe",
                                      mandate_request=mandate_request(), now=NOW)


# ---------------------------------------------------------------- migration
def test_saved_three_mode_preferences_migrate_without_activation(tmp_path):
    root = tmp_path / "tp"
    root.mkdir()
    (root / "trading_profile_preferences.json").write_text(json.dumps({"schema": LEGACY_SCHEMA_V1, "users": {
        "old": {"user_id": "old", "operating_mode": "Copy a CSS Trader", "risk_personality": "Balanced",
                "disclosure_version_acknowledged": "CSS-TP-DISCLOSURE-2026-10-16.1", "updated_at_utc": NOW.isoformat()}}}))
    state = PreferencesStore(root).get("old")
    assert state.active is None
    assert state.previous_selection["operating_mode"] == "Copy a CSS Trader"
    engine = CopyTradeEngine(root, key_provider=lambda: KEY)
    assert engine.evaluate(signal(), follower("old"), system(), now=NOW).reason == "consent_missing"
    activate(engine.consent, "old", "Simulated Trading")
    assert PreferencesStore(root).get("old").active.operating_mode is OperatingMode.SIMULATED_TRADING
    raw = json.loads((root / "trading_profile_preferences.json").read_text())
    assert raw["schema"] == "css.trading_profiles.preferences.v2"


def test_preferences_tampering_fails_closed(tmp_path):
    engine = _engine(tmp_path)
    activate(engine.consent, "u1", "Simulated Trading")
    document = json.loads(engine.preferences.path.read_text())
    document["users"]["u1"]["active"]["operating_mode"] = "Live Trading"
    engine.preferences.path.write_text(json.dumps(document))
    with pytest.raises(PreferencesError):
        engine.preferences.get("u1")
    assert engine.evaluate(signal(), follower("u1"), system(), now=NOW).reason == "preferences_unreadable"


# ---------------------------------------------------------------- CSS-Assisted
def test_assisted_mode_requires_individual_approval_and_regates(tmp_path):
    engine = _engine(tmp_path)
    activate(engine.consent, "a", "CSS-Assisted Trading", "Balanced")
    sig = signal(trader_id=AUTONOMOUS_SOURCE_ID)
    proposed = engine.evaluate(sig, follower("a"), system(), now=NOW)
    assert (proposed.outcome, proposed.stage) == ("PROPOSED", "awaiting_user_approval") and proposed.fill is None
    assert not (tmp_path / "tp" / "followers" / "a" / "anti_bleed_state.json").exists()  # no gate side effects yet

    with pytest.raises(ProposalError, match="proposal_not_found"):
        engine.decide_proposal(proposed.proposal_id, follower("a", session_id="other"), system(), approve=True, now=NOW)
    with pytest.raises(ProposalError, match="proposal_not_found"):
        engine.decide_proposal(proposed.proposal_id, follower("b"), system(), approve=True, now=NOW)
    approved = engine.decide_proposal(proposed.proposal_id, follower("a"), system(), approve=True, now=NOW)
    assert approved.outcome == "COPIED" and approved.gate_results["execution_gate"] == "approved"
    assert approved.notional <= proposed.notional
    with pytest.raises(ProposalError, match="proposal_already_decided"):
        engine.decide_proposal(proposed.proposal_id, follower("a"), system(), approve=True, now=NOW)


def test_assisted_rejection_expiry_and_regate_at_approval(tmp_path):
    engine = _engine(tmp_path)
    activate(engine.consent, "a", "CSS-Assisted Trading", "Balanced")
    p1 = engine.evaluate(signal(signal_id="p1", trader_id=AUTONOMOUS_SOURCE_ID), follower("a"), system(), now=NOW)
    rejected = engine.decide_proposal(p1.proposal_id, follower("a"), system(), approve=False, now=NOW)
    assert (rejected.outcome, rejected.reason) == ("REJECTED", "rejected_by_user")
    p2 = engine.evaluate(signal(signal_id="p2", symbol="GBP/USD", trader_id=AUTONOMOUS_SOURCE_ID), follower("a"), system(), now=NOW)
    with pytest.raises(ProposalError, match="proposal_expired"):
        engine.decide_proposal(p2.proposal_id, follower("a"), system(), approve=True, now=NOW + timedelta(minutes=6))
    p3 = engine.evaluate(signal(signal_id="p3", symbol="AUD/USD", trader_id=AUTONOMOUS_SOURCE_ID), follower("a"), system(), now=NOW)
    # Conditions changed before approval: the kill switch is engaged -> approval cannot execute.
    blocked = engine.decide_proposal(p3.proposal_id, follower("a"), system(mobile_controls={"live_order_kill_switch": True}),
                                     approve=True, now=NOW)
    assert blocked.outcome == "REJECTED" and blocked.reason.startswith("kill_switch")


def test_assisted_manual_orders_and_source_restrictions(tmp_path):
    engine = _engine(tmp_path)
    activate(engine.consent, "a", "CSS-Assisted Trading", "Balanced")
    own = engine.evaluate(signal(signal_id="m1", trader_id="USER_MANUAL:a"), follower("a"), system(), now=NOW)
    assert own.outcome == "PROPOSED"  # manual orders still need explicit confirmation and every gate
    other = engine.evaluate(signal(signal_id="m2", trader_id="USER_MANUAL:b"), follower("a"), system(), now=NOW)
    assert other.reason == "assisted_mode_accepts_css_proposals_or_own_manual_orders"
    trader = engine.evaluate(signal(signal_id="m3"), follower("a"), system(), now=NOW)
    assert trader.reason == "assisted_mode_accepts_css_proposals_or_own_manual_orders"
    tiny = engine.evaluate(signal(signal_id="m4", trader_id="USER_MANUAL:a"),
                           follower("a", equity=600.0, equity_peak=600.0, day_start_equity=600.0, buying_power=600.0),
                           system(), now=NOW)
    approved = engine.decide_proposal(tiny.proposal_id, follower("a", equity=600.0, equity_peak=600.0,
                                                                 day_start_equity=600.0, buying_power=600.0),
                                      system(), approve=True, now=NOW)
    assert approved.reason == "anti_bleed_guard:trade_size_too_small"  # 36 < 50; manual entry is not unrestricted


def test_assisted_proposal_tampering_is_detected(tmp_path):
    engine = _engine(tmp_path)
    activate(engine.consent, "a", "CSS-Assisted Trading", "Balanced")
    p = engine.evaluate(signal(trader_id=AUTONOMOUS_SOURCE_ID), follower("a"), system(), now=NOW)
    document = json.loads(engine.proposals_path.read_text())
    document["proposals"][p.proposal_id]["notional"] = 1_000_000
    engine.proposals_path.write_text(json.dumps(document))
    with pytest.raises(ProposalError, match="proposal_tampered"):
        engine.decide_proposal(p.proposal_id, follower("a"), system(), approve=True, now=NOW)
