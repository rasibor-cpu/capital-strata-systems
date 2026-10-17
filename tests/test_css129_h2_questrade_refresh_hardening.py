"""H2: Questrade refresh-token single-flight, durable persistence and fail-closed behaviour.

Fakes only: no real credentials, no network. The fake OAuth server enforces Questrade's
single-use refresh-token semantics (a spent token is answered with 401).
"""
from __future__ import annotations

import errno
import json
import logging
import multiprocessing as mp
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import threading
import time

import pytest

from backend.brokers.questrade import dpapi_refresh_token_store as dpapi_mod
from backend.brokers.questrade import oauth_refresh as oauth_mod
from backend.brokers.questrade.dpapi_refresh_token_store import WindowsDpapiRefreshTokenStore
from backend.brokers.questrade.errors import TokenStoreError
from backend.brokers.questrade.oauth_refresh import QuestradeBoundedOAuthRefresh, QuestradeOAuthHttpResponse
from backend.brokers.questrade.refresh_coordination import InterProcessFileLock, thread_lock_for, coordination_key
from backend.brokers.questrade.token_lifecycle import InMemoryRefreshTokenStore

NOW = datetime(2026, 10, 16, 22, 0, tzinfo=timezone.utc)
SEED = "FAKE-RT-SEED-0000"


@pytest.fixture(autouse=True)
def _reset_state():
    oauth_mod._reset_rotation_state_for_tests()
    yield
    oauth_mod._reset_rotation_state_for_tests()


class FakeProtect:
    """Reversible stand-in for DPAPI (tests only)."""

    def encrypt(self, plaintext: str) -> bytes:
        return ("FAKEDPAPI:" + plaintext[::-1]).encode()

    def decrypt(self, ciphertext: bytes) -> str:
        raw = ciphertext.decode()
        assert raw.startswith("FAKEDPAPI:")
        return raw[len("FAKEDPAPI:"):][::-1]


class FileOAuthServer:
    """Single-use refresh tokens; state kept in a JSON file so several processes share it."""

    def __init__(self, state_path: Path, *, servers=None, delay: float = 0.0):
        self.state_path = Path(state_path)
        self.servers = servers or ["https://api01.iq.questrade.com/"]
        self.delay = delay
        if not self.state_path.exists():
            self.state_path.write_text(json.dumps({"valid": SEED, "n": 0, "posts": 0, "spent_posts": 0}))

    def state(self):
        return json.loads(self.state_path.read_text())

    def post_form(self, *, url, data, headers, timeout_seconds, allow_redirects):
        st = self.state()
        st["posts"] += 1
        if self.delay:
            time.sleep(self.delay)
        if data["refresh_token"] != st["valid"]:
            st["spent_posts"] += 1
            self.state_path.write_text(json.dumps(st))
            return QuestradeOAuthHttpResponse(status_code=401, payload={})
        st["n"] += 1
        new = f"FAKE-RT-GEN-{st['n']:04d}"
        st["valid"] = new
        self.state_path.write_text(json.dumps(st))
        return QuestradeOAuthHttpResponse(status_code=200, payload={
            "access_token": f"FAKE-AT-GEN-{st['n']:04d}", "refresh_token": new, "token_type": "Bearer",
            "expires_in": 1800, "api_server": self.servers[(st["n"] - 1) % len(self.servers)]})


def _store(path: Path) -> WindowsDpapiRefreshTokenStore:
    return WindowsDpapiRefreshTokenStore(path, protect_backend=FakeProtect(), now=NOW)


@pytest.fixture
def env(tmp_path):
    token_path = tmp_path / "secrets" / "questrade.rt"
    token_path.parent.mkdir()
    _store(token_path).save_refresh_token(SEED)
    server = FileOAuthServer(tmp_path / "server.json")
    return token_path, server


def _ref(store, server, **kw):
    kw.setdefault("now", NOW)
    kw.setdefault("sleeper", lambda s: None)
    return QuestradeBoundedOAuthRefresh(store, transport=server, **kw)


# ----------------------------------------------------------------------------- single-flight
def test_n_threads_one_post_and_shared_bundle(env):
    token_path, server = env
    server.delay = 0.05
    results, bundles = [], []
    barrier = threading.Barrier(8)

    def worker():
        r = _ref(_store(token_path), server)  # separate store objects, same file => same key
        barrier.wait()
        results.append(r.refresh())
        bundles.append(r.memory_bundle)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert server.state()["posts"] == 1 and server.state()["spent_posts"] == 0
    assert all(r["success"] for r in results), [r["reason"] for r in results]
    assert sum(1 for r in results if r["network_call_performed"]) == 1
    assert len({b.access_token for b in bundles}) == 1
    assert _store(token_path).load() == "FAKE-RT-GEN-0001"


def test_in_memory_store_threads_one_post(tmp_path):
    server = FileOAuthServer(tmp_path / "s.json", delay=0.02)
    store = InMemoryRefreshTokenStore()
    store.save_refresh_token(SEED)
    results = []
    threads = [threading.Thread(target=lambda: results.append(_ref(store, server).refresh())) for _ in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert server.state()["posts"] == 1
    assert all(r["success"] for r in results)


def _child(token_path: str, server_state: str, marker_dir: str, out: str) -> None:
    class PeekStore(WindowsDpapiRefreshTokenStore):
        _peeked = False

        def load_refresh_token(self):
            value = super().load_refresh_token()
            if not self._peeked:
                self._peeked = True
                Path(marker_dir, f"peek-{os.getpid()}").write_text("1")
            return value

    store = PeekStore(token_path, protect_backend=FakeProtect(), now=NOW)
    server = FileOAuthServer(Path(server_state))
    result = QuestradeBoundedOAuthRefresh(store, transport=server, now=NOW, lock_timeout_seconds=30).refresh()
    Path(out).write_text(json.dumps({"success": result["success"], "reason": result["reason"]}))


def test_two_processes_exactly_one_post(env, tmp_path):
    token_path, server = env
    markers = tmp_path / "markers"
    markers.mkdir()
    ctx = mp.get_context("spawn")
    holder = InterProcessFileLock(_store(token_path).lock_path(), timeout_seconds=5)
    holder.acquire()  # both children peek T0, then queue on the lock
    try:
        procs = [ctx.Process(target=_child, args=(str(token_path), str(server.state_path), str(markers),
                                                  str(tmp_path / f"out{i}.json"))) for i in range(2)]
        [p.start() for p in procs]
        deadline = time.time() + 60
        while len(list(markers.iterdir())) < 2 and time.time() < deadline:
            time.sleep(0.05)
        assert len(list(markers.iterdir())) == 2
        time.sleep(0.2)
    finally:
        holder.release()
    [p.join(60) for p in procs]
    outs = sorted((json.loads((tmp_path / f"out{i}.json").read_text()) for i in range(2)), key=lambda o: o["reason"])
    assert server.state()["posts"] == 1 and server.state()["spent_posts"] == 0
    assert [o["reason"] for o in outs] == ["QUESTRADE_REFRESH_ROTATED_BY_PEER", "ok"]
    assert _store(token_path).load() == "FAKE-RT-GEN-0001"


# ----------------------------------------------------------------------------- persistence failure
class FlakyStore(InMemoryRefreshTokenStore):
    def __init__(self, failures: int):
        super().__init__()
        self.failures = failures
        self.calls = 0

    def replace(self, bundle):
        self.calls += 1
        if self.failures > 0:
            self.failures -= 1
            raise OSError(errno.ENOSPC, "No space left on device")
        super().replace(bundle)


def test_persist_retry_succeeds_within_bound(tmp_path):
    server = FileOAuthServer(tmp_path / "s.json")
    store = FlakyStore(failures=2)
    store.save_refresh_token(SEED)
    r = _ref(store, server, persist_attempts=3)
    out = r.refresh()
    assert out["success"] and store.calls == 3 and server.state()["posts"] == 1
    assert store.load_refresh_token() == "FAKE-RT-GEN-0001"


def test_crash_window_persist_fails_then_recovers_without_second_post(tmp_path):
    server = FileOAuthServer(tmp_path / "s.json")
    store = FlakyStore(failures=99)
    store.save_refresh_token(SEED)
    r = _ref(store, server, persist_attempts=3)
    out = r.refresh()
    assert out["status"] == "DEGRADED" and out["success"] is False
    assert out["operator_action_required"] and out["rotated_refresh_token_held_in_memory"]
    assert r.memory_bundle is None  # fail closed: unsaved token is not handed to API clients
    assert r.pending_persistence()
    assert store.load_refresh_token() == SEED  # previous value preserved, never overwritten partially
    out2 = r.refresh()  # still failing: still no POST with the spent token
    assert out2["status"] == "DEGRADED" and server.state()["posts"] == 1
    store.failures = 0
    out3 = _ref(store, server).refresh()  # a different caller in the same process
    assert out3["success"] and out3["network_call_performed"] is False
    assert server.state()["posts"] == 1 and store.load_refresh_token() == "FAKE-RT-GEN-0001"


def test_process_crash_before_persist_is_reported_as_revoked_not_looped(tmp_path):
    """Documented residual risk: a crash between POST and persist loses the rotated token."""
    server = FileOAuthServer(tmp_path / "s.json")
    store = FlakyStore(failures=99)
    store.save_refresh_token(SEED)
    _ref(store, server, persist_attempts=1).refresh()
    oauth_mod._reset_rotation_state_for_tests()  # simulate the process dying
    store.failures = 0
    out = _ref(store, server).refresh()
    assert out["reason"] == "QUESTRADE_AUTHORIZATION_REVOKED" and out["success"] is False
    assert server.state()["posts"] == 2  # one bounded attempt, no retry loop


@pytest.mark.parametrize("failure", ["replace", "fsync", "disk_full_mkstemp", "write"])
def test_atomic_replace_failures_preserve_previous_file(env, monkeypatch, failure):
    token_path, server = env
    store = _store(token_path)
    before = token_path.read_bytes()
    boom = OSError(errno.ENOSPC, "No space left on device")
    if failure == "replace":
        monkeypatch.setattr(dpapi_mod.os, "replace", lambda *a, **k: (_ for _ in ()).throw(boom))
    elif failure == "fsync":
        monkeypatch.setattr(dpapi_mod.os, "fsync", lambda *a, **k: (_ for _ in ()).throw(boom))
    elif failure == "disk_full_mkstemp":
        monkeypatch.setattr(dpapi_mod.tempfile, "mkstemp", lambda *a, **k: (_ for _ in ()).throw(boom))
    else:
        real_fdopen = os.fdopen

        class Full:
            def __init__(self, fd, mode):
                self._h = real_fdopen(fd, mode)

            def __enter__(self):
                return self

            def __exit__(self, *e):
                self._h.close()

            def write(self, data):
                raise boom
        monkeypatch.setattr(dpapi_mod.os, "fdopen", Full)
    out = _ref(store, server, persist_attempts=2).refresh()
    assert out["status"] == "DEGRADED"
    assert token_path.read_bytes() == before
    leftovers = [p.name for p in token_path.parent.iterdir() if p.name.endswith(".tmp")]
    assert leftovers == []
    with pytest.raises(TokenStoreError) as info:
        store.save_refresh_token("FAKE-RT-DIRECT")
    assert info.value.code == "QUESTRADE_TOKEN_REPLACE_FAILED"
    assert info.value.__cause__ is None and "FAKE-RT" not in str(info.value)


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
def test_persisted_file_is_owner_only(env):
    token_path, server = env
    assert _ref(_store(token_path), server).refresh()["success"]
    assert (token_path.stat().st_mode & 0o777) == 0o600


# ----------------------------------------------------------------------------- rotation chain / api_server
def test_rotation_chain_and_api_server_change(env):
    token_path, server = env
    server.servers = ["https://api01.iq.questrade.com/", "https://api05.iq.questrade.com/",
                      "https://api07.iq.questrade.com/"]
    seen = []
    for i in range(4):
        r = _ref(_store(token_path), server, now=NOW + timedelta(hours=i))  # previous access expired
        out = r.refresh()
        assert out["success"], out["reason"]
        seen.append((r.memory_bundle.generation, r.memory_bundle.api_server))
        assert _store(token_path).load() == f"FAKE-RT-GEN-{i + 1:04d}"
    st = server.state()
    assert st["posts"] == 4 and st["spent_posts"] == 0
    assert [g for g, _ in seen] == [1, 2, 3, 4]
    assert len({s for _, s in seen[:3]}) == 3  # api_server follows each refresh response


def test_reuse_within_validity_avoids_post(env):
    token_path, server = env
    assert _ref(_store(token_path), server).refresh()["success"]
    again = _ref(_store(token_path), server, now=NOW + timedelta(minutes=5)).refresh()
    assert again["success"] and again["reused_in_process_rotation"] and server.state()["posts"] == 1


def test_rejected_api_server_fails_closed(env):
    token_path, server = env
    server.servers = ["http://evil.example.com/"]
    r = _ref(_store(token_path), server)
    out = r.refresh()
    assert out["success"] is False and r.memory_bundle is None
    assert out["rotated_refresh_token_persisted"] is True
    assert _store(token_path).load() == "FAKE-RT-GEN-0001"  # rotated token not lost


# ----------------------------------------------------------------------------- locks
def test_process_lock_timeout_makes_no_post(env):
    token_path, server = env
    with InterProcessFileLock(_store(token_path).lock_path(), timeout_seconds=1):
        out = _ref(_store(token_path), server, lock_timeout_seconds=0.2).refresh()
    assert out["reason"] == "QUESTRADE_REFRESH_LOCK_TIMEOUT" and out["network_call_performed"] is False
    assert server.state()["posts"] == 0


def test_thread_lock_timeout_makes_no_post(env):
    token_path, server = env
    store = _store(token_path)
    lock = thread_lock_for(coordination_key(store))
    lock.acquire()
    try:
        out = _ref(store, server, lock_timeout_seconds=0.1).refresh()
    finally:
        lock.release()
    assert out["reason"] == "QUESTRADE_REFRESH_LOCK_TIMEOUT" and server.state()["posts"] == 0


def test_stale_lock_file_left_by_dead_owner_is_reclaimed(env):
    token_path, server = env
    lock_path = _store(token_path).lock_path()
    lock_path.write_text("pid=999999 acquired_unix=1\n")  # file present, no OS lock held
    lock = InterProcessFileLock(lock_path, timeout_seconds=1)
    with lock:
        assert lock.reclaimed_stale
    assert _ref(_store(token_path), server).refresh()["success"]


def test_clean_release_is_not_reported_as_stale_reclaim(env):
    lock_path = _store(env[0]).lock_path()
    first = InterProcessFileLock(lock_path, timeout_seconds=1)
    with first:
        pass
    second = InterProcessFileLock(lock_path, timeout_seconds=1)
    with second:
        assert second.reclaimed_stale is False  # previous holder released cleanly
    assert lock_path.stat().st_size == 0


def test_lock_from_crashed_holder_is_reported_as_stale_reclaim(env):
    lock_path = _store(env[0]).lock_path()
    p = mp.get_context("spawn").Process(target=_die_holding_lock, args=(str(lock_path),))
    p.start()
    p.join(60)
    assert p.exitcode == 17
    lock = InterProcessFileLock(lock_path, timeout_seconds=5)
    with lock:
        assert lock.reclaimed_stale is True


def test_zero_lock_timeout_never_waits_on_either_lock(env):
    token_path, server = env
    store = _store(token_path)
    lock = thread_lock_for(coordination_key(store))
    lock.acquire()
    started = time.monotonic()
    try:
        out = _ref(store, server, lock_timeout_seconds=0).refresh()
    finally:
        lock.release()
    assert time.monotonic() - started < 1.0  # previously blocked forever on the thread lock
    assert out["reason"] == "QUESTRADE_REFRESH_LOCK_TIMEOUT" and server.state()["posts"] == 0


def _die_holding_lock(lock_path: str) -> None:
    InterProcessFileLock(Path(lock_path), timeout_seconds=5).acquire()
    os._exit(17)  # crash without releasing


def test_lock_held_by_crashed_process_is_released_by_os(env):
    token_path, server = env
    lock_path = _store(token_path).lock_path()
    p = mp.get_context("spawn").Process(target=_die_holding_lock, args=(str(lock_path),))
    p.start()
    p.join(60)
    assert p.exitcode == 17
    out = _ref(_store(token_path), server, lock_timeout_seconds=5).refresh()
    assert out["success"] and server.state()["posts"] == 1


# ----------------------------------------------------------------------------- redaction
def test_no_token_values_in_logs_reprs_results_or_exceptions(env, caplog, capsys):
    token_path, server = env
    caplog.set_level(logging.DEBUG)
    texts = []
    r = _ref(_store(token_path), server)
    texts += [json.dumps(r.refresh(), default=str), repr(r), repr(r.memory_bundle), repr(_store(token_path))]
    texts.append(json.dumps(_ref(InMemoryRefreshTokenStore(), server).refresh(), default=str))
    flaky = FlakyStore(failures=99)
    flaky.save_refresh_token("FAKE-RT-GEN-0001")
    texts.append(json.dumps(_ref(flaky, server, persist_attempts=1).refresh(), default=str))

    class Leaky:
        def post_form(self, **kw):
            raise RuntimeError("boom " + kw["data"]["refresh_token"])
    s2 = InMemoryRefreshTokenStore()
    s2.save_refresh_token("FAKE-RT-LEAKY")
    texts.append(json.dumps(_ref(s2, Leaky()).refresh(), default=str))
    captured = capsys.readouterr()
    blob = "\n".join(texts) + caplog.text + captured.out + captured.err
    for secret in (SEED, "FAKE-RT-GEN-", "FAKE-AT-GEN-", "FAKE-RT-LEAKY", "FAKEDPAPI:"):
        assert secret not in blob, secret
