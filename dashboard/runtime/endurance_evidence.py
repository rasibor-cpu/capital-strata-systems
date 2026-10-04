"""Tamper-evident, restart-surviving evidence primitives for endurance runs.

Ported in design (not in code) from the OV-002 R1 remediation on
``css-rclive-w1-autonomous-supervisor`` (``backend/certification/
ov002_persistence.py``): atomic JSON writes, an append-only hash-chained
ledger, SHA-256 manifests and terminal-state monotonicity. That branch's
modules target the July runtime topology (``launcher/`` +
``css_live_dashboard.py``), which this release line does not have, so the
primitives are re-implemented here against this line's own supervisor.

Nothing here can grant trading, broker or certification authority.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

GENESIS_HASH = "0" * 64


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: str | os.PathLike[str]) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


# On Windows, os.replace() onto a file that another process currently has
# open fails with PermissionError (Python opens files without
# FILE_SHARE_DELETE). The supervisor rewrites its state every second while the
# monitor reads it, so over a 72 h run such collisions are expected; a reader
# holds the file for milliseconds, so a short bounded retry absorbs them.
REPLACE_RETRIES = 50
REPLACE_RETRY_SECONDS = 0.02
READ_RETRIES = 10


def _replace_with_retry(src: str, dst: Path) -> None:
    for attempt in range(REPLACE_RETRIES):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == REPLACE_RETRIES - 1:
                raise
            time.sleep(REPLACE_RETRY_SECONDS)


def atomic_write_json(path: str | os.PathLike[str], payload: Any) -> None:
    """Write-then-rename so a crash never leaves a half-written state file."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{target.name}.", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, indent=2, default=str)
            handle.flush()
            os.fsync(handle.fileno())
        _replace_with_retry(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_json_retry(path: str | os.PathLike[str]) -> Any:
    """read_json that rides out a concurrent atomic replace (Windows sharing
    violation, or a reader racing the rename). Raises after the last try."""
    for attempt in range(READ_RETRIES):
        try:
            return read_json(path)
        except (PermissionError, json.JSONDecodeError):
            if attempt == READ_RETRIES - 1:
                raise
            time.sleep(REPLACE_RETRY_SECONDS)
    raise AssertionError("unreachable")  # pragma: no cover


def read_json(path: str | os.PathLike[str]) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


class LedgerError(RuntimeError):
    pass


class HashChainedLedger:
    """Append-only JSONL ledger. Each row carries ``seq``, ``prev_hash`` and
    ``hash`` (SHA-256 of the row without ``hash``), so a deleted, reordered or
    edited row breaks ``verify()``. Reopening an existing ledger continues the
    chain, which is what lets evidence survive a recorder restart."""

    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._seq, self._last_hash = self._tail()

    def _tail(self) -> tuple[int, str]:
        if not self.path.exists():
            return 0, GENESIS_HASH
        rows = self.verify()
        if not rows:
            return 0, GENESIS_HASH
        return int(rows[-1]["seq"]), str(rows[-1]["hash"])

    def append(self, event_type: str, **fields: Any) -> dict[str, Any]:
        row = {
            "seq": self._seq + 1,
            "recorded_at_utc": utc_now(),
            "event_type": str(event_type),
            **fields,
            "prev_hash": self._last_hash,
        }
        row["hash"] = sha256_text(canonical_json(row))
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(canonical_json(row) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self._seq, self._last_hash = row["seq"], row["hash"]
        return row

    def verify(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if not self.path.exists():
            return rows
        prev = GENESIS_HASH
        with open(self.path, "r", encoding="utf-8") as handle:
            for number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise LedgerError(f"{self.path.name}: line {number} is not JSON") from exc
                claimed = row.get("hash")
                body = {k: v for k, v in row.items() if k != "hash"}
                if row.get("prev_hash") != prev:
                    raise LedgerError(f"{self.path.name}: chain broken at seq {row.get('seq')}")
                if sha256_text(canonical_json(body)) != claimed:
                    raise LedgerError(f"{self.path.name}: hash mismatch at seq {row.get('seq')}")
                if row.get("seq") != len(rows) + 1:
                    raise LedgerError(f"{self.path.name}: sequence gap at seq {row.get('seq')}")
                rows.append(row)
                prev = claimed
        return rows


def build_manifest(root: str | os.PathLike[str], *, exclude: Iterable[str] = ("MANIFEST.json",)) -> dict[str, Any]:
    base = Path(root)
    skip = set(exclude)
    files = {}
    for path in sorted(p for p in base.rglob("*") if p.is_file()):
        rel = path.relative_to(base).as_posix()
        if rel in skip or path.name.startswith("."):
            continue
        files[rel] = {"sha256": sha256_file(path), "bytes": path.stat().st_size}
    return {"generated_at_utc": utc_now(), "files": files}


def verify_manifest(root: str | os.PathLike[str], manifest: dict[str, Any]) -> list[str]:
    """Return the problems found; an empty list means every listed file matches.

    Append-only files may legitimately have grown after the manifest was
    written, so a file only fails if it is missing or its recorded prefix no
    longer hashes the same (i.e. something already recorded was changed)."""
    problems = []
    base = Path(root)
    for rel, meta in manifest.get("files", {}).items():
        path = base / rel
        if not path.exists():
            problems.append(f"missing: {rel}")
            continue
        size = int(meta.get("bytes", -1))
        with open(path, "rb") as handle:
            prefix = handle.read(size)
        if len(prefix) != size or hashlib.sha256(prefix).hexdigest() != meta.get("sha256"):
            problems.append(f"changed: {rel}")
    return problems


# ---------------------------------------------------------------------------
# Process inspection (read-only). Never uses os.kill(pid, 0) on Windows, where
# os.kill terminates the target process.
# ---------------------------------------------------------------------------
def pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    if os.name == "nt":  # pragma: no cover - exercised on the Windows host
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, int(pid))  # QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        kernel32.CloseHandle(handle)
        return bool(ok) and code.value == 259  # STILL_ACTIVE
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    state = process_state(pid)
    return state not in {"Z (zombie)", "X (dead)"}


def process_state(pid: int | None) -> str | None:
    """Linux ``/proc/<pid>/status`` State line; None where unavailable."""
    if not pid:
        return None
    try:
        with open(f"/proc/{int(pid)}/status", "r", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("State:"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        return None
    return None


def process_resources(pid: int | None) -> dict[str, Any]:
    """Best-effort RSS / threads / open file count. Missing values are
    reported as None with a reason, never guessed."""
    out: dict[str, Any] = {"pid": pid, "rss_kb": None, "threads": None, "open_fds": None, "source": None}
    if not pid:
        out["source"] = "no_pid"
        return out
    if os.name == "nt":  # pragma: no cover - exercised on the Windows host
        return _windows_process_resources(int(pid), out)
    try:
        with open(f"/proc/{int(pid)}/status", "r", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("VmRSS:"):
                    out["rss_kb"] = int(line.split()[1])
                elif line.startswith("Threads:"):
                    out["threads"] = int(line.split()[1])
        out["open_fds"] = len(os.listdir(f"/proc/{int(pid)}/fd"))
        out["source"] = "procfs"
    except (OSError, ValueError):
        out["source"] = f"unavailable_on_{platform.system().lower()}"
    return out


def _windows_process_resources(pid: int, out: dict[str, Any]) -> dict[str, Any]:  # pragma: no cover
    """Working set and handle count via psapi/kernel32 (read-only query)."""
    import ctypes
    from ctypes import wintypes

    class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(0x1000 | 0x0010, False, pid)  # QUERY_LIMITED_INFORMATION | VM_READ
    if not handle:
        out["source"] = "windows_open_process_failed"
        return out
    try:
        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            out["rss_kb"] = int(counters.WorkingSetSize // 1024)
        handles = wintypes.DWORD()
        if kernel32.GetProcessHandleCount(handle, ctypes.byref(handles)):
            out["open_fds"] = int(handles.value)  # Windows handle count
        out["source"] = "win32"
    finally:
        kernel32.CloseHandle(handle)
    return out


__all__ = [
    "GENESIS_HASH", "HashChainedLedger", "LedgerError", "atomic_write_json", "build_manifest",
    "canonical_json", "pid_alive", "process_resources", "process_state", "read_json", "read_json_retry",
    "sha256_file", "sha256_text", "utc_now", "verify_manifest",
]
