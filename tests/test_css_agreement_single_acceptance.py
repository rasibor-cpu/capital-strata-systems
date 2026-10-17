"""Operating agreement: Next/Previous navigation and ONE final acceptance (no per-page confirmation).

Covers navigation, acceptance, rejection (incomplete, declined, stale, altered content, mismatched
settings), restart without re-presentation, re-presentation on version / settings change, the
terminal UX (unrecognised input never aborts) and audit integrity. Simulation only; nothing here
can reach a broker.
"""
from __future__ import annotations

import importlib.util
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agreement_support import accept_agreement
from css118_support import KEY
from backend.signals.research import DEFAULT_COSTS
from backend.simulation import cad146
from backend.simulation.cad146 import SIM_SESSION, SIM_USER, Cad146Simulation, SimulationError
from backend.trading_profiles.agreement_review import ACCEPTED, DECLINED, AgreementReview
from backend.trading_profiles.consent import ConsentError
from backend.trading_profiles.copy_engine import CopyTradeEngine
from backend.trading_profiles.manual import ACKNOWLEDGEMENT_SHA256

REPO = Path(__file__).resolve().parents[1]
T0 = datetime(2026, 10, 16, 21, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _no_ambient_switches(monkeypatch):
    from backend.trading_profiles.manual import current_manual
    for name in ("CSS_LIVE_ORDER_KILL_SWITCH", "REA_KILL_SWITCH", "CSS_SIM_ENTRY_HALT"):
        monkeypatch.delenv(name, raising=False)
    yield
    current_manual.cache_clear()  # a test may have loaded a bumped manual; reload the real one next time


class Clock:
    def __init__(self, t=T0):
        self.t = t

    def __call__(self):
        return self.t


def _engine(path):
    return CopyTradeEngine(path, key_provider=lambda: KEY)


def _status(track_root):
    """consent_status for a track of an existing simulation run (run_id read from its run.json)."""
    return cad146.consent_status(_engine(track_root), run_id=cad146.read_run_id(Path(track_root).parent))


def _review(tmp_path, n=1, clock=None, **kw):
    engines = [_engine(tmp_path / f"e{i}") for i in range(n)]
    review = AgreementReview([e.consent for e in engines], user_id=SIM_USER, auth_session_hash=SIM_SESSION,
                             operator_id=kw.pop("operator_id", "robert"), operating_mode="Simulated Trading",
                             risk_personality="Balanced", clock=clock or Clock(), **kw)
    return review, engines


def _records(engine, kind):
    return [r for r in engine.consent.ledger.records() if r["record_type"] == kind]


def _tool():
    spec = importlib.util.spec_from_file_location("css_sim_cad146_ux", REPO / "tools" / "css_sim_cad146.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    return tool


# ------------------------------------------------------------------ navigation
def test_next_and_previous_navigation_without_per_page_confirmation(tmp_path):
    review, _ = _review(tmp_path)
    assert review.total == 12
    first = review.page()
    review.previous()  # cannot go before page 1
    assert review.position == 0 and review.page()["page_id"] == first["page_id"]
    review.next()
    review.page()
    review.previous()
    assert review.page()["page_id"] == first["page_id"] and review.page()["reviewed"] is True
    for _ in range(review.total):
        review.page()
        review.next()
    assert review.at_final_screen and review.complete
    review.previous()
    assert review.page()["index"] == 12 and not review.at_final_screen


def test_a_page_counts_as_reviewed_only_after_it_was_displayed(tmp_path):
    review, _ = _review(tmp_path)
    with pytest.raises(ConsentError, match="page_not_presented"):
        review.next()


# ------------------------------------------------------------------ acceptance and recording
def test_single_acceptance_records_version_hash_time_operator_and_settings_in_every_ledger(tmp_path):
    clock = Clock()
    review, engines = _review(tmp_path, n=2, clock=clock)
    accept_agreement(review)
    assert review.status == ACCEPTED and len(review.receipts) == 2
    summary = review.summary()
    for engine in engines:
        (rec,) = _records(engine, "ACCEPTED")
        assert rec["manual_version"] == summary["agreement_version"] and rec["manual_sha256"] == summary["agreement_sha256"]
        assert rec["accepted_at_utc"] == T0.isoformat() and rec["operator_id"] == "robert"
        assert rec["operating_mode"] == "Simulated Trading" and rec["risk_personality"] == "Balanced"
        assert rec["limits"] == summary["limits"] and rec["policy_hash"] == summary["policy_hash"]
        assert rec["agreement_session_id"] == summary["agreement_session_id"]
        assert len(rec["pages_reviewed"]) == 12 and rec["acknowledgement_checked"] is True
        assert engine.consent.verify_active(SIM_USER) == (True, "consent_valid")
    assert all(r["live_trading_authorized"] is False for r in review.receipts)


# ------------------------------------------------------------------ rejection
def test_incomplete_review_cannot_be_accepted(tmp_path):
    review, engines = _review(tmp_path)
    for _ in range(11):
        review.page()
        review.next()
    with pytest.raises(ConsentError, match="pages_not_reviewed"):
        review.accept(acknowledged=True, policy_hash_shown=review.summary()["policy_hash"])
    assert _records(engines[0], "ACCEPTED") == [] and engines[0].preferences.get(SIM_USER).active is None


def test_acknowledgement_must_be_given(tmp_path):
    review, _ = _review(tmp_path)
    while not review.at_final_screen:
        review.page()
        review.next()
    with pytest.raises(ConsentError, match="acknowledgement_not_checked"):
        review.accept(acknowledged=False, policy_hash_shown=review.summary()["policy_hash"])


def test_decline_is_recorded_and_the_review_can_never_be_accepted(tmp_path):
    review, engines = _review(tmp_path)
    review.page()
    review.next()
    review.decline("declined_by_operator")
    assert review.status == DECLINED
    (rec,) = _records(engines[0], "DECLINED")
    assert rec["operator_id"] == "robert" and rec["pages_reviewed"] == 1 and rec["reason"] == "declined_by_operator"
    with pytest.raises(ConsentError, match="agreement_review_closed"):
        review.accept(acknowledged=True, policy_hash_shown=review.summary()["policy_hash"])
    consent = engines[0].consent
    with pytest.raises(ConsentError, match="review_closed"):
        consent.accept(SIM_USER, auth_session_hash=SIM_SESSION, review_id=review.reviews[0].review_id,
                       acknowledgement_checked=True, acknowledgement_sha256=ACKNOWLEDGEMENT_SHA256,
                       manual_version=review.manual.version,
                       manual_sha256=review.manual.sha256, policy_hash_shown=review.summary()["policy_hash"],
                       now=T0)
    assert engines[0].preferences.get(SIM_USER).active is None


def test_stale_acceptance_is_rejected(tmp_path):
    clock = Clock()
    review, engines = _review(tmp_path, clock=clock)
    while not review.at_final_screen:
        review.page()
        review.next()
    clock.t = T0 + timedelta(minutes=31)  # pending settings expire after 30 minutes
    with pytest.raises(ConsentError, match="change_expired"):
        review.accept(acknowledged=True, policy_hash_shown=review.summary()["policy_hash"])
    assert engines[0].preferences.get(SIM_USER).active is None


def test_altered_agreement_content_is_rejected(tmp_path, monkeypatch):
    review, engines = _review(tmp_path)
    while not review.at_final_screen:
        review.page()
        review.next()
    consent = engines[0].consent
    original = consent.manual_provider()
    monkeypatch.setattr(consent, "manual_provider", lambda: replace(original, sha256="0" * 64))
    with pytest.raises(ConsentError, match="manual_version_mismatch"):
        review.accept(acknowledged=True, policy_hash_shown=review.summary()["policy_hash"])
    assert engines[0].preferences.get(SIM_USER).active is None


def test_mismatched_or_tampered_settings_are_rejected(tmp_path):
    review, engines = _review(tmp_path)
    while not review.at_final_screen:
        review.page()
        review.next()
    with pytest.raises(ConsentError, match="policy_hash_mismatch"):
        review.accept(acknowledged=True, policy_hash_shown="f" * 64)
    consent = engines[0].consent
    state = consent._read_state()
    state["changes"][review.changes[0].change_id]["risk_personality"] = "Aggressive"
    consent._write_state(state)
    with pytest.raises(ConsentError, match="pending_change_tampered"):
        review.accept(acknowledged=True, policy_hash_shown=review.summary()["policy_hash"])


def test_ledgers_with_different_agreement_content_refuse_a_shared_review(tmp_path, monkeypatch):
    engines = [_engine(tmp_path / "a"), _engine(tmp_path / "b")]
    original = engines[1].consent.manual_provider()
    monkeypatch.setattr(engines[1].consent, "manual_provider", lambda: replace(original, version="9.9"))
    with pytest.raises(ConsentError):
        AgreementReview([e.consent for e in engines], user_id=SIM_USER, auth_session_hash=SIM_SESSION,
                        operator_id="robert", operating_mode="Simulated Trading", risk_personality="Balanced",
                        clock=Clock())


# ------------------------------------------------------------------ terminal UX
def _script(*answers):
    it = iter(answers)

    def read(prompt):
        try:
            return next(it)
        except StopIteration:
            raise EOFError from None
    return read


def test_terminal_one_acceptance_and_unrecognised_input_never_aborts(tmp_path):
    tool = _tool()
    review, engines = _review(tmp_path, n=2)
    out = []
    # 12 x Enter (with a typo and a step back on the way), then 'y' and 'yes' at the final screen
    # (the inputs that used to terminate activation) are explained, not fatal; then ACCEPT.
    answers = ["", "", "zz", "p", "", ""] + [""] * 9 + ["y", "yes", "ACCEPT"]
    tool.terminal_agreement(review, read=_script(*answers), write=out.append)
    assert review.status == ACCEPTED
    text = "\n".join(map(str, out))
    assert text.count("Not recognised") == 3 and "Final acceptance" in text and "NOT authorized" in text
    assert all(len(_records(e, "ACCEPTED")) == 1 for e in engines)


def test_terminal_quit_decline_and_closed_input_record_a_decline(tmp_path):
    tool = _tool()
    for i, answers in enumerate([("", "q"), [""] * 12 + ["d"], ("",)]):
        review, engines = _review(tmp_path / str(i))
        tool.terminal_agreement(review, read=_script(*answers), write=lambda *_: None)
        assert review.status == DECLINED and len(_records(engines[0], "DECLINED")) == 1
        assert engines[0].preferences.get(SIM_USER).active is None


# ------------------------------------------------------------------ simulation: restart and changes
def _sim(root, presenter, now=T0):
    return Cad146Simulation(root, artifacts=[], costs=DEFAULT_COSTS, operational_approvals_root=root.parent / "ops",
                            operator="robert", starting_equity=14_600.0, presenter=presenter, now=now)


def _must_not_present(review):
    raise AssertionError("agreement presented again although the acceptance is current")


def test_one_presentation_covers_both_tracks_and_restart_does_not_present_again(tmp_path):
    calls = []

    def counted(review):
        calls.append(review.agreement_session_id)
        accept_agreement(review)

    root = tmp_path / "run"
    sim = _sim(root, counted)
    assert len(calls) == 1 and len(sim.agreement.receipts) == 2  # one review for track A and track B
    started = json.loads((root / "run.json").read_text())["started_utc"]
    journal = [json.loads(x) for x in (root / "journal.jsonl").read_text().splitlines()]
    assert any(r["type"] == "AGREEMENT_ACCEPTED" and r["operator"] == "robert" for r in journal)
    again = _sim(root, _must_not_present, now=T0 + timedelta(hours=3))  # restart / resume
    assert again.agreement is None and json.loads((root / "run.json").read_text())["started_utc"] == started


def test_agreement_version_change_requires_reacceptance_but_keeps_the_trial_clock(tmp_path, monkeypatch):
    root = tmp_path / "run"
    _sim(root, accept_agreement)
    started = json.loads((root / "run.json").read_text())["started_utc"]
    from backend.trading_profiles import manual as manual_mod
    original = manual_mod.current_manual()
    bumped = replace(original, version="9.0.0", sha256="9" * 64,
                     history=original.history + ({"version": "9.0.0", "sha256": "9" * 64, "material": True},))
    manual_mod.current_manual.cache_clear()
    monkeypatch.setattr(manual_mod, "load_manual", lambda: bumped)
    with pytest.raises(SimulationError, match="consent_activation_required"):
        Cad146Simulation(root, artifacts=[], costs=DEFAULT_COSTS, operational_approvals_root=tmp_path / "ops",
                         operator="robert", now=T0 + timedelta(hours=1))
    report = Cad146Simulation(root, artifacts=[], costs=DEFAULT_COSTS, operational_approvals_root=tmp_path / "ops",
                              operator="report-reader", require_current_agreement=False).report()
    assert report["run"]["started_utc"] == started  # read-only report still works, nothing presented
    calls = []
    _sim(root, lambda r: calls.append(1) or accept_agreement(r), now=T0 + timedelta(hours=1))
    assert calls == [1] and json.loads((root / "run.json").read_text())["started_utc"] == started


def test_changed_accepted_settings_require_reacceptance(tmp_path, monkeypatch):
    root = tmp_path / "run"
    _sim(root, accept_agreement)
    monkeypatch.setattr(cad146, "_desired_policy_hash", lambda: "0" * 64)
    ok, why = _status(root / "track_a")
    assert (ok, why) == (False, "accepted_settings_differ")


def test_declined_activation_never_starts_the_clock(tmp_path):
    root = tmp_path / "run"
    with pytest.raises(SimulationError, match="agreement_not_accepted:declined_by_operator"):
        _sim(root, lambda review: review.decline("declined_by_operator"))
    assert not (root / "run.json").exists()


def test_run_interrupted_before_acceptance_restarts_its_clock_with_a_recorded_reason(tmp_path):
    root = tmp_path / "run"
    root.mkdir()
    (root / "run.json").write_text(json.dumps({"starting_equity_cad": 14_600.0, "started_utc": "2026-10-16T20:00:00+00:00",
                                               "operator": "robert"}))  # left by the old flow's aborted start
    _sim(root, accept_agreement)
    meta = json.loads((root / "run.json").read_text())
    assert meta["started_utc"] == T0.isoformat() and meta["clock_restarted_reason"] == "activation_never_completed"
    assert meta["aborted_started_utc"] == "2026-10-16T20:00:00+00:00" and meta["starting_equity_cad"] == 14_600.0


def test_started_trial_is_never_reset_even_when_reacceptance_is_needed(tmp_path, monkeypatch):
    root = tmp_path / "run"
    _sim(root, accept_agreement)
    with (root / "journal.jsonl").open("a", encoding="utf-8") as fh:  # the trial has cycled
        fh.write(json.dumps({"type": "HEARTBEAT", "at_utc": T0.isoformat()}) + "\n")
    before = (root / "run.json").read_text()
    monkeypatch.setattr(cad146, "_desired_policy_hash", lambda: "0" * 64)  # force a re-presentation
    with pytest.raises(SimulationError):
        _sim(root, lambda review: review.decline("declined_by_operator"), now=T0 + timedelta(hours=5))
    assert (root / "run.json").read_text() == before  # clock, capital and start untouched


# ------------------------------------------------------------------ audit integrity
def test_tampered_acceptance_record_breaks_the_chain_and_blocks_trading(tmp_path):
    root = tmp_path / "run"
    _sim(root, accept_agreement)
    engine = _engine(root / "track_a")
    path = engine.consent.ledger.path
    lines = path.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[-1])
    rec["operator_id"] = "someone-else"
    lines[-1] = json.dumps(rec, sort_keys=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ok, why = engine.consent.verify_active(SIM_USER)
    assert ok is False and "chain_broken" in why
    with pytest.raises(SimulationError, match="consent_activation_required"):
        Cad146Simulation(root, artifacts=[], costs=DEFAULT_COSTS, operational_approvals_root=tmp_path / "ops",
                         operator="robert", now=T0)


# ------------------------------------------------------------------ one acceptance per run root (Grok audit A-M3)
def test_copied_run_directory_needs_its_own_acceptance(tmp_path):
    import shutil
    run_a = tmp_path / "runA"
    _sim(run_a, accept_agreement)
    run_c = tmp_path / "runC"
    shutil.copytree(run_a, run_c)  # the copy carries run A's ledgers, preferences and signing key
    ok, why = _status(run_c / "track_a")
    assert ok is False and why == "acceptance_from_another_run"
    with pytest.raises(SimulationError, match="consent_activation_required"):
        Cad146Simulation(run_c, artifacts=[], costs=DEFAULT_COSTS, operational_approvals_root=tmp_path / "ops",
                         operator="robert", now=T0)
    calls = []
    _sim(run_c, lambda r: calls.append(1) or accept_agreement(r), now=T0 + timedelta(minutes=1))
    assert calls == [1]  # one fresh acceptance, recorded for run C's own root
    assert _status(run_c / "track_a") == (True, "consent_valid")
    assert _status(run_a / "track_a") == (True, "consent_valid")  # run A unaffected


def test_moved_run_directory_needs_a_fresh_acceptance(tmp_path):
    run_a = tmp_path / "runA"
    _sim(run_a, accept_agreement)
    moved = tmp_path / "moved"
    run_a.rename(moved)
    assert _status(moved / "track_b") == (False, "acceptance_from_another_run")


def test_acceptance_without_a_run_binding_is_not_current(tmp_path):
    review, engines = _review(tmp_path)  # a review given outside a simulation run records no binding
    accept_agreement(review)
    assert engines[0].consent.active_record(SIM_USER).get("run_binding") is None
    assert cad146.consent_status(engines[0], run_id=None) == (False, "acceptance_not_bound_to_run")


def test_run_binding_is_recorded_in_every_acceptance_record(tmp_path):
    root = tmp_path / "run"
    sim = _sim(root, accept_agreement)
    for track, receipt in zip(("track_a", "track_b"), sim.agreement.receipts):
        assert receipt["run_binding"] == cad146.run_binding(root / track, cad146.read_run_id(root))
    run_id = cad146.read_run_id(root)
    assert run_id and run_id.startswith("run-")
    assert cad146.run_binding(root / "track_a", run_id) != cad146.run_binding(root / "track_b", run_id)


# ------------------------------------------------------------------ Grok final audit F-1, F-2
def test_new_run_at_the_same_path_with_restored_tracks_needs_a_fresh_acceptance(tmp_path):
    """F-1: the binding includes the run's random run_id, not only its location."""
    import shutil
    root = tmp_path / "run"
    _sim(root, accept_agreement)
    saved = tmp_path / "saved"
    shutil.copytree(root, saved)
    shutil.rmtree(root)
    root.mkdir()
    for track in ("track_a", "track_b"):  # old track state restored into a brand-new run at the same path
        shutil.copytree(saved / track, root / track)
    calls = []
    sim = _sim(root, lambda r: calls.append(1) or accept_agreement(r), now=T0 + timedelta(hours=1))
    assert calls == [1]
    assert cad146.read_run_id(root) != cad146.read_run_id(saved)
    assert sim.track_a.router is not None and _status(root / "track_a") == (True, "consent_valid")


def test_read_only_simulation_never_cycles(tmp_path):
    """F-2: read-only use (reports) cannot produce decisions."""
    root = tmp_path / "run"
    _sim(root, accept_agreement)
    report_only = Cad146Simulation(root, artifacts=[], costs=DEFAULT_COSTS, operational_approvals_root=tmp_path / "ops",
                                   operator="robert", now=T0, require_current_agreement=False)
    with pytest.raises(SimulationError, match="read_only_simulation_cannot_cycle"):
        report_only.cycle(lambda instrument, gran: None, [("BTC-USD", 3600)], now=T0)


def test_router_consent_check_refuses_an_acceptance_from_another_run(tmp_path):
    """F-2: every decision's verify_active also checks the run binding, not only start-up."""
    import shutil
    run_a = tmp_path / "runA"
    _sim(run_a, accept_agreement)
    run_c = tmp_path / "runC"
    shutil.copytree(run_a, run_c)
    copied = Cad146Simulation(run_c, artifacts=[], costs=DEFAULT_COSTS, operational_approvals_root=tmp_path / "ops",
                              operator="robert", now=T0, require_current_agreement=False)
    for track in (copied.track_a, copied.track_b):
        ok, why = track.router.engine.consent.verify_active(SIM_USER)
        assert ok is False and why == "consent_run_binding_mismatch"
    original = Cad146Simulation(run_a, artifacts=[], costs=DEFAULT_COSTS, operational_approvals_root=tmp_path / "ops",
                                operator="robert", now=T0, require_current_agreement=False)
    assert original.track_a.router.engine.consent.verify_active(SIM_USER) == (True, "consent_valid")
