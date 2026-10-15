"""CSS-065: cross-platform interprocess lock and authorization-ledger concurrency.

Every multi-process test uses real child interpreters (subprocess), so on Windows
these tests exercise the real msvcrt backend and on POSIX the real fcntl backend.
``test_windows_backend_*`` additionally simulates a Windows import on any platform
(fcntl made unimportable, msvcrt replaced by a recording fake) in a fresh child
interpreter, so the Windows code path is covered even off-Windows.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path

import pytest

from backend.runtime.interprocess_lock import (
    LOCK_BACKEND,
    InterprocessLockTimeout,
    exclusive_file_lock,
)
from backend.runtime.pilot_authorization_ledger import PilotAuthorizationLedger, PilotReplayError

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV = {**os.environ, "PYTHONPATH": str(REPO_ROOT) + os.pathsep + os.environ.get("PYTHONPATH", "")}


def _child(code: str, *args: str, **kw) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-c", textwrap.dedent(code), *args], cwd=REPO_ROOT, env=ENV,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, **kw,
    )


def _wait_for_line(proc: subprocess.Popen, expected: str, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        line = proc.stdout.readline()
        if line.strip() == expected:
            return
        if not line and proc.poll() is not None:
            break
    raise AssertionError(f"child never printed {expected!r}: {proc.stderr.read()}")


HOLD_LOCK = """
import sys
from backend.runtime.interprocess_lock import exclusive_file_lock
with exclusive_file_lock(sys.argv[1]):
    print("locked", flush=True)
    sys.stdin.readline()          # hold until the parent closes stdin or kills us
print("released", flush=True)
"""


# ---------------------------------------------------------------------- backend selection / import

def test_backend_matches_platform_and_never_requires_fcntl_on_windows():
    assert LOCK_BACKEND == ("msvcrt" if sys.platform == "win32" else "fcntl")
    source = (REPO_ROOT / "backend" / "runtime" / "pilot_authorization_ledger.py").read_text(encoding="utf-8")
    assert "import fcntl" not in source


WINDOWS_SIMULATION = r"""
import errno, json, os, sys, types
import backend.runtime.governed_pilot_profile, backend.runtime.pilot_dual_control  # import real deps first
# The retry script is passed as a file path: a long script on the command line
# exceeds the Windows 32,767-character limit (WinError 206).
calls, script = [], json.loads(open(sys.argv[2], encoding="utf-8").read())
fake = types.ModuleType("msvcrt"); fake.LK_NBLCK, fake.LK_UNLCK = 2, 0
def locking(fd, mode, nbytes):
    calls.append([mode, nbytes, os.lseek(fd, 0, os.SEEK_CUR)])
    if mode == fake.LK_NBLCK and script:
        err = script.pop(0)
        if err:
            raise OSError(err, os.strerror(err))
fake.locking = locking
real_platform = sys.platform
sys.modules["fcntl"] = None            # any `import fcntl` now raises ImportError
sys.modules["msvcrt"] = fake
sys.platform = "win32"
import backend.runtime.interprocess_lock as lock_mod
sys.platform = real_platform
from backend.runtime.pilot_authorization_ledger import PilotAuthorizationLedger, PilotReplayError
ledger = PilotAuthorizationLedger(sys.argv[1]); ledger.lock_timeout_seconds = float(sys.argv[3])
try:
    ledger.revoke("win-sim-1", revoked_by="test", reason="sim")
    outcome = "ok"
except PilotReplayError as exc:
    outcome = "replay:" + str(exc)
except OSError as exc:
    outcome = "oserror:" + str(exc.errno)
print(json.dumps({"backend": lock_mod.LOCK_BACKEND, "calls": calls, "outcome": outcome,
                  "entries": len(ledger.verify_chain())}))
"""


def _simulate_windows(tmp_path, script, timeout="5"):
    script_path = tmp_path.parent / f"{tmp_path.name}_sim_script.json"
    script_path.write_text(json.dumps(script), encoding="utf-8")
    proc = _child(WINDOWS_SIMULATION, str(tmp_path), str(script_path), timeout)
    out, err = proc.communicate(timeout=60)
    assert proc.returncode == 0, err
    return json.loads(out.strip().splitlines()[-1])


def test_windows_backend_imports_without_fcntl_and_locks_byte_zero(tmp_path):
    result = _simulate_windows(tmp_path, [])
    assert result["backend"] == "msvcrt" and result["outcome"] == "ok" and result["entries"] == 1
    assert result["calls"] == [[2, 1, 0], [0, 1, 0]]   # LK_NBLCK then LK_UNLCK, 1 byte at offset 0


def test_windows_backend_retries_contention_then_succeeds(tmp_path):
    import errno

    result = _simulate_windows(tmp_path, [errno.EACCES, errno.EACCES, 0])
    assert result["outcome"] == "ok" and result["entries"] == 1
    assert [c[0] for c in result["calls"]] == [2, 2, 2, 0]


def test_windows_backend_times_out_fail_closed(tmp_path):
    import errno

    result = _simulate_windows(tmp_path, [errno.EACCES] * 10_000, timeout="0.3")
    assert result["outcome"].startswith("replay:ledger lock timeout") and result["entries"] == 0
    assert 0 not in [c[0] for c in result["calls"]]     # never "unlocked" a lock it did not hold


def test_windows_backend_non_contention_error_is_not_swallowed(tmp_path):
    import errno

    result = _simulate_windows(tmp_path, [errno.EBADF])
    assert result["outcome"] == f"oserror:{errno.EBADF}" and result["entries"] == 0


# ---------------------------------------------------------------------- real lock behaviour

def test_acquire_release_reacquire_and_lock_file_untouched(tmp_path):
    path = tmp_path / "x.lock"
    with exclusive_file_lock(path):
        pass
    with exclusive_file_lock(path, timeout_seconds=1):
        pass
    assert path.exists() and path.stat().st_size == 0


def test_invalid_timeout_rejected(tmp_path):
    with pytest.raises(ValueError):
        with exclusive_file_lock(tmp_path / "x.lock", timeout_seconds=0):
            pass


def test_other_process_holding_lock_causes_timeout_then_release_allows(tmp_path):
    path = tmp_path / "x.lock"
    holder = _child(HOLD_LOCK, str(path))
    try:
        _wait_for_line(holder, "locked")
        started = time.monotonic()
        with pytest.raises(InterprocessLockTimeout):
            with exclusive_file_lock(path, timeout_seconds=0.5):
                pass
        assert time.monotonic() - started >= 0.45
    finally:
        holder.stdin.close()
        _wait_for_line(holder, "released")
        holder.wait(timeout=30)
    with exclusive_file_lock(path, timeout_seconds=5):
        pass


def test_crashed_holder_never_leaves_a_stale_lock(tmp_path):
    path = tmp_path / "x.lock"
    holder = _child(HOLD_LOCK, str(path))
    _wait_for_line(holder, "locked")
    holder.kill()                          # no unlock, no cleanup
    holder.wait(timeout=30)
    with exclusive_file_lock(path, timeout_seconds=5):
        pass


def test_threads_in_one_process_exclude_each_other(tmp_path):
    path = tmp_path / "x.lock"
    entered, release, outcome = threading.Event(), threading.Event(), {}

    def hold():
        with exclusive_file_lock(path):
            entered.set()
            release.wait(10)

    t = threading.Thread(target=hold)
    t.start()
    try:
        assert entered.wait(10)
        try:
            with exclusive_file_lock(path, timeout_seconds=0.3):
                outcome["second"] = "acquired"
        except InterprocessLockTimeout:
            outcome["second"] = "timeout"
    finally:
        release.set()
        t.join(10)
    assert outcome["second"] == "timeout"


# ---------------------------------------------------------------------- ledger under concurrency

WRITER = """
import sys
from backend.runtime.pilot_authorization_ledger import PilotAuthorizationLedger, PilotReplayError
ledger = PilotAuthorizationLedger(sys.argv[1])
for approval_id in sys.argv[2].split(","):
    try:
        ledger.revoke(approval_id, revoked_by="w", reason="race")
        print("ok", flush=True)
    except PilotReplayError:
        print("replay", flush=True)
"""


def test_simultaneous_writers_keep_one_intact_chain(tmp_path):
    ids = [[f"w{p}-{i}" for i in range(5)] for p in range(8)]
    procs = [_child(WRITER, str(tmp_path), ",".join(batch)) for batch in ids]
    outputs = [proc.communicate(timeout=120) for proc in procs]
    assert all(proc.returncode == 0 for proc in procs), [o[1] for o in outputs]
    assert sum(o[0].split().count("ok") for o in outputs) == 40
    entries = PilotAuthorizationLedger(tmp_path).verify_chain()
    assert len(entries) == 40
    assert sorted(e["approval_id"] for e in entries) == sorted(i for batch in ids for i in batch)
    assert b"\r\n" not in (tmp_path / "journal.jsonl").read_bytes()


def test_duplicate_authorization_attempts_succeed_exactly_once(tmp_path):
    procs = [_child(WRITER, str(tmp_path), "same-approval") for _ in range(8)]
    results = [proc.communicate(timeout=120)[0].strip() for proc in procs]
    assert results.count("ok") == 1 and results.count("replay") == 7
    entries = PilotAuthorizationLedger(tmp_path).verify_chain()
    assert [e["approval_id"] for e in entries] == ["same-approval"]


def test_ledger_lock_contention_fails_closed_without_appending(tmp_path):
    ledger = PilotAuthorizationLedger(tmp_path)
    ledger.revoke("before", revoked_by="t", reason="seed")
    journal_before = (tmp_path / "journal.jsonl").read_bytes()
    holder = _child(HOLD_LOCK, str(tmp_path / "journal.lock"))
    try:
        _wait_for_line(holder, "locked")
        ledger.lock_timeout_seconds = 0.5
        with pytest.raises(PilotReplayError, match="lock timeout"):
            ledger.revoke("during", revoked_by="t", reason="contended")
    finally:
        holder.stdin.close()
        holder.wait(timeout=30)
    assert (tmp_path / "journal.jsonl").read_bytes() == journal_before
    assert ledger.is_claimed("during")            # burned: can never be consumed later (fail closed)
    with pytest.raises(PilotReplayError):
        ledger.revoke("during", revoked_by="t", reason="retry")


def test_interrupted_write_fails_closed(tmp_path):
    ledger = PilotAuthorizationLedger(tmp_path)
    ledger.revoke("a", revoked_by="t", reason="seed")
    with (tmp_path / "journal.jsonl").open("ab") as handle:
        handle.write(b'{"event": "REVOKED", "approval_id": "torn"')   # torn, unterminated line
    with pytest.raises(PilotReplayError):
        ledger.verify_chain()
    size = (tmp_path / "journal.jsonl").stat().st_size
    with pytest.raises(PilotReplayError):
        ledger.revoke("b", revoked_by="t", reason="after-crash")
    assert (tmp_path / "journal.jsonl").stat().st_size == size


def test_writer_killed_while_holding_ledger_lock_does_not_block_or_corrupt(tmp_path):
    PilotAuthorizationLedger(tmp_path).revoke("seed", revoked_by="t", reason="seed")
    holder = _child("""
        import sys
        from backend.runtime.pilot_authorization_ledger import PilotAuthorizationLedger
        ledger = PilotAuthorizationLedger(sys.argv[1])
        with ledger._locked():
            print("locked", flush=True)
            sys.stdin.readline()
    """, str(tmp_path))
    _wait_for_line(holder, "locked")
    holder.kill()
    holder.wait(timeout=30)
    ledger = PilotAuthorizationLedger(tmp_path)
    ledger.lock_timeout_seconds = 5
    ledger.revoke("after", revoked_by="t", reason="recovered")
    assert [e["approval_id"] for e in ledger.verify_chain()] == ["seed", "after"]
