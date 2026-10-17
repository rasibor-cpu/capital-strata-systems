"""Simulation lifecycle and recovery (FINANCE 48h run 2026-10-16 follow-up). No network.

Covers: start/stop/interruption records, write-ahead in-flight recovery (never re-decide a bar),
bar settle delay and post-decision revisions, missed bars, R7 sign-on expiry surfacing (R7 itself
unchanged: it still refuses), run lock, supervisor exit codes, signal stops, attest beside run.
"""
from __future__ import annotations

import importlib.util
import json
import os
import signal
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from agreement_support import accept_agreement

from test_css_rc1_signals import H, _artifact, _now_for, synthetic
from backend.runtime.interprocess_lock import exclusive_file_lock
from backend.signals.research import DEFAULT_COSTS
from backend.simulation import cad146
from backend.simulation.cad146 import TRACK_A, TRACK_B, Cad146Simulation, Track

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("css_sim_cad146_tool_lifecycle", REPO / "tools" / "css_sim_cad146.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


@pytest.fixture(autouse=True)
def _no_ambient_switches(monkeypatch):
    for name in ("CSS_LIVE_ORDER_KILL_SWITCH", "REA_KILL_SWITCH", "CSS_SIM_ENTRY_HALT", *cad146.LIVE_ARM_ENVS):
        monkeypatch.delenv(name, raising=False)


def live(series):
    return replace(series, classification="LIVE")


def make(tmp_path, *, settle=None, equity=10_000.0, art=None, presenter=accept_agreement):
    art = art or _artifact()
    kw = {} if settle is None else {"bar_settle_seconds": settle}
    sim = Cad146Simulation(tmp_path / "sim", artifacts=[art], costs=DEFAULT_COSTS,
                           operational_approvals_root=tmp_path / "ops", operator="operator-1",
                           starting_equity=equity, presenter=presenter, **kw)
    return sim, art


def events(root_or_sim, kind=None):
    journal = root_or_sim.journal if isinstance(root_or_sim, Cad146Simulation) else Path(root_or_sim) / "journal.jsonl"
    rows = [json.loads(x) for x in journal.read_text().splitlines()]
    return [r for r in rows if kind is None or r["type"] == kind]


FEED = [("BTC-USD", H)]


# ------------------------------------------------------------------ bar settling
def test_default_settle_delay_defers_a_fresh_bar_without_marking_it_processed(tmp_path):
    assert cad146.DEFAULT_BAR_SETTLE_SECONDS == 600.0
    sim, _ = make(tmp_path)
    s = live(synthetic())
    early = sim.cycle(lambda i, g: s, FEED, now=_now_for(s))  # close + 60 s: Coinbase may still revise it
    assert early["unsettled"] == 1 and early["decisions"] == {TRACK_A: 0, TRACK_B: 0}
    assert not events(sim, "PRODUCED") and events(sim, "OBSERVATION")[-1]["settled"] is False
    later = sim.cycle(lambda i, g: s, FEED, now=_now_for(s) + timedelta(minutes=10))
    assert later["unsettled"] == 0 and later["decisions"][TRACK_B] == 1
    assert len(events(sim, "PRODUCED")) == 2  # one per track, exactly once


def test_a_bar_revised_after_its_decision_is_journalled_and_not_redecided(tmp_path):
    sim, _ = make(tmp_path, settle=0)
    s = live(synthetic())
    sim.cycle(lambda i, g: s, FEED, now=_now_for(s))
    last = s.candles[-1]
    revised = replace(s, candles=s.candles[:-1] + (replace(last, close=last.close * 0.999),))
    again = sim.cycle(lambda i, g: revised, FEED, now=_now_for(s) + timedelta(minutes=5))
    assert again["decisions"] == {TRACK_A: 0, TRACK_B: 0}
    (rec,) = events(sim, "BAR_REVISED_AFTER_DECISION")
    assert rec["key"].endswith(str(last.ts))


# ------------------------------------------------------------------ write-ahead recovery
def test_crash_between_fill_and_commit_is_recovered_without_a_second_decision(tmp_path, monkeypatch):
    sim, art = make(tmp_path, settle=0)
    s = live(synthetic())
    real_commit = Track.commit

    def crash_on_b(self, key):
        if self.name == TRACK_B:
            raise RuntimeError("power lost after the paper fill")
        return real_commit(self, key)

    monkeypatch.setattr(Track, "commit", crash_on_b)
    with pytest.raises(RuntimeError):
        sim.cycle(lambda i, g: s, FEED, now=_now_for(s))
    monkeypatch.setattr(Track, "commit", real_commit)
    state = json.loads((tmp_path / "sim" / "track_b" / "sim_state.json").read_text())
    assert state["inflight"] and state["inflight"] not in state["processed"]

    resumed, _ = make(tmp_path, settle=0, art=art)
    (rec,) = events(resumed, "DECISION_INFLIGHT_RECOVERED")
    assert rec["track"] == TRACK_B and len(rec["positions_opened_on_bar"]) == 1
    out = resumed.cycle(lambda i, g: s, FEED, now=_now_for(s) + timedelta(minutes=5))
    assert out["decisions"] == {TRACK_A: 0, TRACK_B: 0}
    rep = resumed.report()
    assert rep["tracks"][TRACK_B]["fills"] == 1 and len(rep["tracks"][TRACK_B]["open_positions"]) == 1
    assert rep["lifecycle"]["DECISION_INFLIGHT_RECOVERED"] == 1


def test_read_only_report_never_recovers_or_rewrites_an_inflight_marker(tmp_path):
    sim, art = make(tmp_path, settle=0)
    path = tmp_path / "sim" / "track_a" / "sim_state.json"
    sim.track_a.begin("coinbase|BTC-USD|3600|1")
    before = path.read_text()
    Cad146Simulation(tmp_path / "sim", artifacts=[art], costs=DEFAULT_COSTS, operational_approvals_root=tmp_path / "ops",
                     operator="reader", require_current_agreement=False).report()
    assert path.read_text() == before


# ------------------------------------------------------------------ missed bars
def test_bars_that_closed_while_down_are_journalled_and_never_decided_late(tmp_path):
    full = live(synthetic())
    early = replace(full, candles=full.candles[:-4])
    sim, _ = make(tmp_path, settle=0)
    sim.cycle(lambda i, g: early, FEED, now=_now_for(early))
    out = sim.cycle(lambda i, g: full, FEED, now=_now_for(full))
    (rec,) = events(sim, "BARS_MISSED")
    assert rec["count"] == 3 and rec["policy"] == "not_decided_late"
    assert out["decisions"][TRACK_B] == 1  # only the current bar
    sim.cycle(lambda i, g: full, FEED, now=_now_for(full) + timedelta(minutes=5))
    assert len(events(sim, "BARS_MISSED")) == 1 and sim.report()["bars_missed"] == 3


# ------------------------------------------------------------------ R7 surfacing
def test_expired_sign_on_still_blocks_and_is_surfaced_once_with_an_alert(tmp_path, capsys):
    sim, _ = make(tmp_path, settle=0)
    s = live(synthetic())
    now = _now_for(s)
    sim.attest_operator("operator-1", now=now - timedelta(hours=2))
    first = sim.cycle(lambda i, g: s, FEED, now=now)
    assert first["operator_session_valid"] is False and "operator_session_expired:R7" in first["entries_blocked"]
    rep = sim.report()  # R7 unchanged: the router still refuses the entry (Track A: no approval anyway)
    assert all(t["fills"] == 0 for t in rep["tracks"].values())
    assert any("session" in k for k in rep["tracks"][TRACK_B]["reasons"]), rep["tracks"][TRACK_B]["reasons"]
    assert "ALERT" in capsys.readouterr().err
    sim.cycle(lambda i, g: s, FEED, now=now + timedelta(minutes=5))
    assert len(events(sim, "OPERATOR_SESSION_EXPIRED")) == 1
    assert events(sim, "HEARTBEAT")[-1]["entries_blocked"] == ["operator_session_expired:R7"]
    sim.attest_operator("operator-1", now=now + timedelta(minutes=9))
    sim.cycle(lambda i, g: s, FEED, now=now + timedelta(minutes=10))
    assert len(events(sim, "OPERATOR_SESSION_RESTORED")) == 1
    assert json.loads((tmp_path / "sim" / "status.json").read_text())["operator_session_valid"] is True


def test_session_timeout_is_still_the_r7_constant():
    from backend.governance.css_unified_trade_gate import SESSION_TIMEOUT_SECONDS
    assert SESSION_TIMEOUT_SECONDS == 3600 and cad146.SESSION_TIMEOUT_SECONDS is SESSION_TIMEOUT_SECONDS


# ------------------------------------------------------------------ lifecycle records
def test_start_interruption_and_clean_stop_are_all_journalled(tmp_path):
    sim, art = make(tmp_path, settle=0)
    s = live(synthetic())
    now = _now_for(s)
    assert sim.begin_session(now=now, hours=48, poll_seconds=300)["type"] == "RUN_STARTED"
    sim.cycle(lambda i, g: s, FEED, now=now, poll_seconds=300)
    # the process vanishes here: no RUN_STOPPED (console closed, reboot, kill)
    resumed, _ = make(tmp_path, settle=0, art=art)
    rec = resumed.begin_session(now=now + timedelta(hours=3), hours=48, poll_seconds=300)
    (gap,) = events(resumed, "RUN_INTERRUPTION_DETECTED")
    assert rec["type"] == "RUN_RESUMED" and gap["gap_s"] == pytest.approx(3 * 3600, abs=1)
    assert rec["processed"] == {TRACK_A: 1, TRACK_B: 1}
    assert rec["consent"] == {TRACK_A: "consent_valid", TRACK_B: "consent_valid"}  # re-verified on resume
    resumed.end_session("signal:SIGTERM", 143, now=now + timedelta(hours=4))
    assert json.loads((tmp_path / "sim" / "status.json").read_text())["state"] == "STOPPED"
    again, _ = make(tmp_path, settle=0, art=art)
    again.begin_session(now=now + timedelta(hours=5))
    assert len(events(again, "RUN_INTERRUPTION_DETECTED")) == 1  # a clean stop is not an interruption
    assert [e["type"] for e in events(again) if e["type"] in cad146.LIFECYCLE_TYPES] == \
        ["RUN_STARTED", "RUN_RESUMED", "RUN_STOPPED", "RUN_RESUMED"]


def test_in_process_wall_clock_jump_is_reported_as_suspension(tmp_path):
    sim, _ = make(tmp_path, settle=0)
    s = live(synthetic())
    now = _now_for(s)
    sim.cycle(lambda i, g: s, FEED, now=now, poll_seconds=300)
    sim.cycle(lambda i, g: s, FEED, now=now + timedelta(minutes=5), poll_seconds=300)
    assert not events(sim, "SUSPENSION_DETECTED")
    sim.cycle(lambda i, g: s, FEED, now=now + timedelta(minutes=50), poll_seconds=300)  # laptop lid closed
    (rec,) = events(sim, "SUSPENSION_DETECTED")
    assert rec["gap_s"] == pytest.approx(45 * 60, abs=1)


# ------------------------------------------------------------------ CLI: lock, exit codes, signals
def _args(tmp_path, **kw):
    base = dict(root=str(tmp_path / "run"), artifacts=str(tmp_path / "arts"), approvals_root=str(tmp_path / "ops"),
                operator="robert", capital_profile="engineering", custom_capital_cad=None, source="coinbase",
                hours=48.0, poll_seconds=300.0, bar_settle_seconds=0.0, on_session_expiry="continue", out=None)
    base.update(kw)
    (tmp_path / "arts").mkdir(exist_ok=True)
    return SimpleNamespace(**base)


@pytest.fixture()
def cli(monkeypatch):
    monkeypatch.setattr(tool, "_preflight", lambda args, now=None: {"verdict": "PASS", "checks": []})
    monkeypatch.setattr(tool, "CoinbaseQuotes", lambda http: None)
    monkeypatch.setattr(tool, "_code_revision", lambda: "test-rev")
    return tool


class _Clock:
    def __init__(self, start):
        self.t = start

    def __call__(self):
        return self.t


def test_cli_completed_run_exits_0_with_started_and_stopped_records(tmp_path, cli):
    args = _args(tmp_path, hours=0.0)
    assert cli.cmd_run(args, presenter=accept_agreement, sleep=lambda s: None) == cli.EXIT_COMPLETED
    life = [e for e in events(args.root) if e["type"] in cad146.LIFECYCLE_TYPES]
    assert [e["type"] for e in life] == ["RUN_STARTED", "RUN_STOPPED"]
    assert life[0]["code_revision"] == "test-rev" and life[1]["reason"] == "completed" and life[1]["exit_code"] == 0


@pytest.mark.skipif(os.name != "posix", reason="POSIX only: on Windows os.kill(pid, SIGTERM) is TerminateProcess "
                    "and would kill pytest itself; Windows is covered by the child-process tests below")
def test_cli_real_sigterm_in_process_is_journalled_and_resume_is_clean(tmp_path, cli):
    args = _args(tmp_path)
    clock = _Clock(datetime.now(timezone.utc))

    def sigterm(_seconds):
        os.kill(os.getpid(), signal.SIGTERM)

    original = signal.getsignal(signal.SIGTERM)
    code = cli.cmd_run(args, presenter=accept_agreement, sleep=sigterm, clock=clock, fetch=lambda i, g: None)
    assert code == 128 + signal.SIGTERM
    (stop,) = events(args.root, "RUN_STOPPED")
    assert stop["reason"] == "signal:SIGTERM" and stop["exit_code"] == code
    assert signal.getsignal(signal.SIGTERM) is original  # handlers are restored
    clock.t += timedelta(minutes=31)
    resume_args = _args(tmp_path, hours=0.5)  # the window (from started_utc) has now passed
    assert cli.cmd_run(resume_args, presenter=accept_agreement, clock=clock, sleep=lambda s: None) == cli.EXIT_COMPLETED
    types = [e["type"] for e in events(args.root) if e["type"] in (*cad146.LIFECYCLE_TYPES, "RUN_INTERRUPTION_DETECTED")]
    assert types == ["RUN_STARTED", "RUN_STOPPED", "RUN_RESUMED", "RUN_STOPPED"]


def _available_stop_signals():
    names = ["SIGINT", "SIGTERM", "SIGHUP", "SIGBREAK"]
    return [n for n in names if hasattr(signal, n)]


@pytest.mark.parametrize("name", _available_stop_signals())
def test_installed_stop_handler_invoked_directly_journals_and_is_restored(tmp_path, cli, name):
    """No real signal (safe on every OS): call the handler `run` installed, exactly as the
    interpreter would on delivery, then check the journal, the exit code and the restoration."""
    sig = getattr(signal, name)
    original = signal.getsignal(sig)
    seen = {}

    def deliver(_seconds):
        handler = signal.getsignal(sig)
        seen["installed"] = handler
        handler(int(sig), None)

    code = cli.cmd_run(_args(tmp_path), presenter=accept_agreement, sleep=deliver, fetch=lambda i, g: None)
    assert seen["installed"] is not original and callable(seen["installed"])
    assert code == 128 + int(sig)
    (stop,) = events(_args(tmp_path).root, "RUN_STOPPED")
    assert stop["reason"] == f"signal:{name}" and stop["exit_code"] == code
    assert signal.getsignal(sig) is original
    for other in _available_stop_signals():  # every handler restored, not just the one delivered
        assert getattr(signal.getsignal(getattr(signal, other)), "__qualname__", "") != "_install_stop_handlers.<locals>.handler"
    st = json.loads((Path(_args(tmp_path).root) / "status.json").read_text())
    assert st["state"] == "STOPPED" and st["exit_code"] == code


def test_sleep_is_sliced_so_a_windows_ctrl_break_is_handled_within_a_second():
    slices = []
    clock = {"t": 0.0}
    import time as _time

    real_monotonic = _time.monotonic
    try:
        _time.monotonic = lambda: clock["t"]

        def fake_sleep(s):
            slices.append(s)
            clock["t"] += s
        tool._sleep_in_slices(300.0, _sleep=fake_sleep)
    finally:
        _time.monotonic = real_monotonic
    assert max(slices) <= 1.0 and sum(slices) == pytest.approx(300.0) and len(slices) == 300


CHILD = REPO / "tests" / "css_sim_lifecycle_child.py"
WINDOWS = os.name == "nt"


def _spawn(tmp_path, *, hours, poll, log):
    import subprocess
    import sys

    env = {k: v for k, v in os.environ.items()
           if k not in ("CSS_LIVE_ORDER_KILL_SWITCH", "REA_KILL_SWITCH", "CSS_SIM_ENTRY_HALT", *cad146.LIVE_ARM_ENVS)}
    kw = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if WINDOWS else {}
    out = open(log, "ab")
    return subprocess.Popen([sys.executable, str(CHILD), str(tmp_path / "run"), str(tmp_path / "keys"), str(hours),
                             str(poll)], stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env,
                            cwd=str(REPO), **kw), out


def _wait_for_heartbeat(proc, root, log, timeout=90.0):
    import time as _time

    deadline = _time.monotonic() + timeout
    journal = Path(root) / "journal.jsonl"
    while _time.monotonic() < deadline:
        if proc.poll() is not None:
            pytest.fail(f"child exited early ({proc.returncode}): {Path(log).read_text(errors='replace')[-2000:]}")
        if journal.exists() and '"HEARTBEAT"' in journal.read_text():
            return
        _time.sleep(0.2)
    proc.kill()
    pytest.fail("child never reached its first heartbeat")


def _finish(proc, out, timeout):
    import subprocess

    try:
        return proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()  # fallback: never leave a child behind
        proc.wait(timeout=30)
        pytest.fail(f"child did not stop within {timeout}s of the stop signal")
    finally:
        out.close()


def _graceful_stop(proc):
    """Windows: CTRL_BREAK_EVENT to the child's own process group (never to pytest). POSIX: SIGTERM."""
    if WINDOWS:
        try:
            os.kill(proc.pid, signal.CTRL_BREAK_EVENT)
        except OSError as exc:  # e.g. pytest started without a console (service, some CI shells)
            proc.kill()
            proc.wait(timeout=30)
            pytest.skip(f"CTRL_BREAK_EVENT not deliverable without a console: {exc}")
        return "SIGBREAK", 128 + int(signal.SIGBREAK)  # 149
    os.kill(proc.pid, signal.SIGTERM)
    return "SIGTERM", 128 + int(signal.SIGTERM)  # 143


def test_child_graceful_stop_is_prompt_journalled_and_resumes_cleanly(tmp_path):
    import time as _time

    root, log = tmp_path / "run", tmp_path / "child.log"
    proc, out = _spawn(tmp_path, hours=48, poll=30.0, log=log)  # mid-sleep when the stop arrives
    _wait_for_heartbeat(proc, root, log)
    _time.sleep(0.5)
    name, expected = _graceful_stop(proc)
    t0 = _time.monotonic()
    code = _finish(proc, out, timeout=20)
    assert code == expected, Path(log).read_text(errors="replace")[-2000:]
    assert _time.monotonic() - t0 < 15  # sliced sleep: not the 30 s poll interval
    (stop,) = events(root, "RUN_STOPPED")
    assert stop["reason"] == f"signal:{name}" and stop["exit_code"] == expected
    assert json.loads((root / "status.json").read_text())["state"] == "STOPPED"
    proc, out = _spawn(tmp_path, hours=0, poll=30.0, log=log)  # resume: window passed -> completes
    assert _finish(proc, out, timeout=120) == 0, Path(log).read_text(errors="replace")[-2000:]
    types = [e["type"] for e in events(root) if e["type"] in (*cad146.LIFECYCLE_TYPES, "RUN_INTERRUPTION_DETECTED")]
    assert types == ["RUN_STARTED", "RUN_STOPPED", "RUN_RESUMED", "RUN_STOPPED"]  # clean stop: no interruption
    assert events(root, "RUN_STOPPED")[-1]["exit_code"] == 0


def test_child_hard_kill_cannot_journal_and_next_start_detects_the_interruption(tmp_path):
    """Popen.kill() is SIGKILL on POSIX and TerminateProcess on Windows (= taskkill /F, console close)."""
    root, log = tmp_path / "run", tmp_path / "child.log"
    proc, out = _spawn(tmp_path, hours=48, poll=30.0, log=log)
    _wait_for_heartbeat(proc, root, log)
    proc.kill()
    _finish(proc, out, timeout=30)
    assert not events(root, "RUN_STOPPED")
    proc, out = _spawn(tmp_path, hours=0, poll=30.0, log=log)
    assert _finish(proc, out, timeout=120) == 0, Path(log).read_text(errors="replace")[-2000:]
    (gap,) = events(root, "RUN_INTERRUPTION_DETECTED")
    assert gap["last_lifecycle"] == "RUN_STARTED" and gap["last_heartbeat_utc"]
    assert [e["type"] for e in events(root) if e["type"] in cad146.LIFECYCLE_TYPES] == \
        ["RUN_STARTED", "RUN_RESUMED", "RUN_STOPPED"]


@pytest.mark.skipif(not WINDOWS, reason="Windows-specific contract")
def test_windows_stop_signal_contract():
    assert int(signal.SIGBREAK) == 21 and 128 + int(signal.SIGBREAK) == 149
    assert not hasattr(signal, "SIGHUP")  # never installed on Windows; nothing else to restore


def test_cli_keyboard_interrupt_exits_130(tmp_path, cli):
    args = _args(tmp_path)

    def ctrl_c(_seconds):
        raise KeyboardInterrupt

    assert cli.cmd_run(args, presenter=accept_agreement, sleep=ctrl_c, fetch=lambda i, g: None) == 130
    assert events(args.root, "RUN_STOPPED")[-1]["reason"] == "signal:SIGINT"


def test_cli_second_run_on_a_locked_root_exits_4_without_journalling(tmp_path, cli):
    args = _args(tmp_path, hours=0.0)
    cli.cmd_run(args, presenter=accept_agreement)
    before = (Path(args.root) / "journal.jsonl").read_text()
    with exclusive_file_lock(Path(args.root) / "run.lock", timeout_seconds=1.0):
        assert cli.cmd_run(args, presenter=accept_agreement) == cli.EXIT_ALREADY_RUNNING
    assert (Path(args.root) / "journal.jsonl").read_text() == before


def test_cli_session_expiry_exit_policy_exits_3(tmp_path, cli):
    args = _args(tmp_path, on_session_expiry="exit")
    clock = _Clock(datetime.now(timezone.utc))
    sleeps = []

    def advance(seconds):
        sleeps.append(seconds)
        clock.t += timedelta(seconds=seconds)

    assert cli.cmd_run(args, presenter=accept_agreement, sleep=advance, clock=clock,
                       fetch=lambda i, g: None) == cli.EXIT_SESSION_EXPIRED
    assert len(sleeps) in (12, 13)  # about 3600 s of 300 s polls, then the cycle sees the expired sign-on
    assert events(args.root, "OPERATOR_SESSION_EXPIRED") and \
        events(args.root, "RUN_STOPPED")[-1]["reason"] == "operator_session_expired"


def test_cli_unexpected_error_is_journalled_and_exits_1(tmp_path, cli):
    (tmp_path / "arts").mkdir()
    (tmp_path / "arts" / "a.json").write_text(json.dumps(_artifact()))
    args = _args(tmp_path)

    def broken(_i, _g):
        raise RuntimeError("provider bug")

    assert cli.cmd_run(args, presenter=accept_agreement, sleep=lambda s: None, fetch=broken) == cli.EXIT_ERROR
    stop = events(args.root, "RUN_STOPPED")[-1]
    assert stop["exit_code"] == 1 and stop["reason"].startswith("error:RuntimeError:provider bug")
    assert json.loads((Path(args.root) / "status.json").read_text())["state"] == "STOPPED"


def test_cli_refused_agreement_exits_5(tmp_path, cli):
    def walk_away(review):
        return None

    assert cli.cmd_run(_args(tmp_path), presenter=walk_away) == cli.EXIT_REFUSED


def test_cli_attest_beside_a_running_root_never_touches_track_state(tmp_path, cli):
    args = _args(tmp_path, hours=0.0)
    cli.cmd_run(args, presenter=accept_agreement)
    state = Path(args.root) / "track_b" / "sim_state.json"
    state.write_text(json.dumps({"processed": [], "inflight": "coinbase|BTC-USD|3600|1"}))
    before = state.read_text()
    with exclusive_file_lock(Path(args.root) / "run.lock", timeout_seconds=1.0):  # `run` is active
        assert cli.cmd_attest(args, confirm=lambda: "robert") == 0
    assert state.read_text() == before
    assert len(events(args.root, "OPERATOR_SIGN_ON")) == 2


def test_cli_attest_refuses_when_consent_is_not_current(tmp_path, cli, monkeypatch):
    args = _args(tmp_path, hours=0.0)
    cli.cmd_run(args, presenter=accept_agreement)
    monkeypatch.setattr(cad146, "consent_status", lambda engine, run_id: (False, "withdrawn"))
    with pytest.raises(SystemExit, match="consent_not_current:withdrawn"):
        cli.cmd_attest(args, confirm=lambda: "robert")
