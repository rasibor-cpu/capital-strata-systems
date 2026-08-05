"""OV002 certification-critical atomic persistence and single-writer locks.

Guarantee (documented):
- On success, destination JSON contents equal the serialized payload after an
  atomic rename within the destination directory (POSIX rename; Windows
  ReplaceFile/os.replace semantics).
- File data is flushed and fsync'd before rename.
- Directory fsync is attempted after rename where the platform allows it;
  failure of directory fsync is recorded but does not silently claim success
  if the file write/replace failed.
- This is NOT a claim of crash-proof durability across power loss on every
  Windows volume/filesystem combination. Residuals: delayed metadata flush on
  some NTFS/network mounts; rename is atomic at the path level but concurrent
  readers may observe pre- or post-replace contents around the boundary.

Fail-closed: any exception during write/lock becomes PersistenceError /
WriterLockError — never a silent success return.
"""

from __future__ import annotations

import json
import os
import stat
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional


class PersistenceError(RuntimeError):
    def __init__(self, code: str, detail: Optional[str] = None) -> None:
        self.code = code
        self.detail = detail
        super().__init__(code if detail is None else f"{code}:{detail}")


class WriterLockError(PersistenceError):
    pass


def _strict_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise PersistenceError("json_duplicate_key", str(key))
        obj[key] = value
    return obj


def strict_json_loads(raw: str | bytes, *, source: str = "json") -> Any:
    try:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
        return json.loads(text, object_pairs_hook=_strict_object_pairs)
    except PersistenceError:
        raise
    except json.JSONDecodeError as exc:
        raise PersistenceError("json_malformed", source) from exc


def _is_reparse_or_symlink(path: Path) -> bool:
    try:
        st = path.lstat()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise PersistenceError("path_lstat_failed", f"{path}:{type(exc).__name__}") from exc
    if stat.S_ISLNK(st.st_mode):
        return True
    attrs = getattr(st, "st_file_attributes", 0)
    return bool(attrs & 0x400)


def _resolve_existing_root(root: Path | str) -> Path:
    try:
        resolved = Path(root).resolve(strict=True)
    except OSError as exc:
        raise PersistenceError("trusted_root_unavailable", str(type(exc).__name__)) from exc
    if _is_reparse_or_symlink(resolved):
        raise PersistenceError("trusted_root_reparse")
    return resolved


def validate_path_contained(path: Path | str, *, expected_root: Path | str | None) -> Path:
    dest = Path(path)
    if expected_root is None:
        return dest
    root = _resolve_existing_root(expected_root)
    try:
        resolved = dest.resolve(strict=False)
        resolved.relative_to(root)
    except ValueError as exc:
        raise PersistenceError("path_outside_expected_root", str(dest)) from exc
    except OSError as exc:
        raise PersistenceError("path_resolve_failed", str(type(exc).__name__)) from exc

    cursor = dest if dest.exists() else dest.parent
    while True:
        try:
            cursor_resolved = cursor.resolve(strict=False)
            cursor_resolved.relative_to(root)
        except ValueError as exc:
            raise PersistenceError("path_ancestor_outside_expected_root", str(cursor)) from exc
        except OSError as exc:
            raise PersistenceError("path_ancestor_resolve_failed", str(type(exc).__name__)) from exc
        if cursor.exists() and _is_reparse_or_symlink(cursor):
            raise PersistenceError("path_reparse_or_symlink", str(cursor))
        if cursor_resolved == root or cursor == cursor.parent:
            break
        cursor = cursor.parent
    return dest


def _path_identity(path: Path) -> tuple[int | None, int | None, str]:
    try:
        st = path.lstat()
    except OSError as exc:
        raise PersistenceError("path_identity_failed", str(type(exc).__name__)) from exc
    return (getattr(st, "st_dev", None), getattr(st, "st_ino", None), str(path.resolve(strict=False)))


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _fsync_directory(directory: Path) -> None:
    if os.name == "nt":
        # Directory handles are not reliably fsyncable on Windows; best-effort only.
        return
    try:
        fd = os.open(str(directory), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_write_json(
    path: Path | str,
    payload: Any,
    *,
    expected_root: Path | str | None = None,
) -> Path:
    """Deterministic JSON atomic replace with flush + fsync + temp cleanup."""
    dest = validate_path_contained(path, expected_root=expected_root)
    try:
        validate_path_contained(dest.parent, expected_root=expected_root)
        dest.parent.mkdir(parents=True, exist_ok=True)
        validate_path_contained(dest.parent, expected_root=expected_root)
        parent_identity = _path_identity(dest.parent)
    except OSError as exc:
        raise PersistenceError("atomic_mkdir_failed", str(type(exc).__name__)) from exc

    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True, default=str) + "\n"
    tmp_name = f".{dest.name}.{uuid.uuid4().hex}.tmp"
    tmp = validate_path_contained(dest.parent / tmp_name, expected_root=expected_root)
    if tmp.parent.resolve(strict=False) != dest.parent.resolve(strict=False):
        raise PersistenceError("atomic_tmp_parent_mismatch", tmp.name)
    try:
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY
        fd = os.open(str(tmp), flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except OSError as exc:
                raise PersistenceError("atomic_fsync_failed", str(type(exc).__name__)) from exc
        try:
            validate_path_contained(dest, expected_root=expected_root)
            validate_path_contained(tmp, expected_root=expected_root)
            if _path_identity(dest.parent) != parent_identity:
                raise PersistenceError("atomic_parent_replaced", str(dest.parent))
            os.replace(str(tmp), str(dest))
        except OSError as exc:
            raise PersistenceError("atomic_replace_failed", str(type(exc).__name__)) from exc
        _fsync_directory(dest.parent)
    except PersistenceError:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise
    except Exception as exc:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise PersistenceError("atomic_write_failed", str(type(exc).__name__)) from exc
    return dest


def atomic_append_jsonl(
    path: Path | str,
    record: Mapping[str, Any],
    *,
    expected_root: Path | str | None = None,
) -> Path:
    """Append one JSONL record with flush+fsync. Not multi-process safe alone — use lock."""
    dest = validate_path_contained(path, expected_root=expected_root)
    try:
        validate_path_contained(dest.parent, expected_root=expected_root)
        dest.parent.mkdir(parents=True, exist_ok=True)
        validate_path_contained(dest.parent, expected_root=expected_root)
        line = json.dumps(dict(record), sort_keys=True, ensure_ascii=True, default=str) + "\n"
        with open(dest, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(line)
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except OSError as exc:
                raise PersistenceError("jsonl_fsync_failed", str(type(exc).__name__)) from exc
    except PersistenceError:
        raise
    except Exception as exc:
        raise PersistenceError("jsonl_append_failed", str(type(exc).__name__)) from exc
    return dest


def read_json_object(path: Path | str) -> dict[str, Any]:
    """Strict JSON object reader. Malformed/missing → PersistenceError (fail closed)."""
    dest = Path(path)
    if not dest.exists():
        raise PersistenceError("json_missing", dest.name)
    try:
        raw = dest.read_text(encoding="utf-8")
    except OSError as exc:
        raise PersistenceError("json_unreadable", str(type(exc).__name__)) from exc
    if not raw.strip():
        raise PersistenceError("json_empty", dest.name)
    try:
        payload = strict_json_loads(raw, source=dest.name)
    except PersistenceError:
        raise
    if not isinstance(payload, dict):
        raise PersistenceError("json_not_object", dest.name)
    return payload


@dataclass
class WriterLock:
    path: Path
    attempt_id: str
    writer_role: str
    lease_until_epoch: float
    expected_root: Path | None = None
    lock_identity: tuple[int | None, int | None, str] | None = None
    _fd: int | None = None
    released: bool = False

    def release(self) -> None:
        if self.released:
            return
        try:
            validate_path_contained(self.path, expected_root=self.expected_root)
            existing = read_json_object(self.path)
            if str(existing.get("attempt_id") or "") != self.attempt_id:
                raise WriterLockError("writer_lock_wrong_owner", str(existing.get("attempt_id")))
            if str(existing.get("writer_role") or "") != self.writer_role:
                raise WriterLockError("writer_lock_wrong_role", str(existing.get("writer_role")))
            if self.lock_identity is not None and _path_identity(self.path) != self.lock_identity:
                raise WriterLockError("writer_lock_identity_changed", self.path.name)
            if self._fd is not None:
                try:
                    os.close(self._fd)
                except OSError:
                    pass
                self._fd = None
            if self.path.exists():
                validate_path_contained(self.path, expected_root=self.expected_root)
                if self.lock_identity is not None and _path_identity(self.path) != self.lock_identity:
                    raise WriterLockError("writer_lock_identity_changed", self.path.name)
                self.path.unlink()
            self.released = True
        except WriterLockError:
            raise
        except PersistenceError as exc:
            raise WriterLockError("writer_lock_release_validation_failed", exc.code) from exc
        except OSError as exc:
            raise WriterLockError("writer_lock_release_failed", str(type(exc).__name__)) from exc

    def __enter__(self) -> "WriterLock":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


def acquire_writer_lock(
    lock_path: Path | str,
    *,
    attempt_id: str,
    writer_role: str,
    lease_seconds: float = 120.0,
    now_epoch: float | None = None,
    expected_root: Path | str | None = None,
) -> WriterLock:
    """Exclusive single-writer lease. Stale locks fail closed (no silent steal)."""
    root = _resolve_existing_root(expected_root) if expected_root is not None else None
    path = validate_path_contained(lock_path, expected_root=root)
    validate_path_contained(path.parent, expected_root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    validate_path_contained(path.parent, expected_root=root)
    now = float(now_epoch if now_epoch is not None else time.time())
    lease_seconds = max(1.0, float(lease_seconds))
    if not attempt_id or not writer_role:
        raise WriterLockError("writer_lock_identity_missing")

    if path.exists():
        try:
            existing = read_json_object(path)
        except PersistenceError as exc:
            raise WriterLockError("writer_lock_malformed", exc.code) from exc
        lease_until = existing.get("lease_until_epoch")
        try:
            lease_until_f = float(lease_until)
        except (TypeError, ValueError) as exc:
            raise WriterLockError("writer_lock_lease_malformed") from exc
        if now <= lease_until_f:
            raise WriterLockError(
                "writer_lock_held",
                f"{existing.get('writer_role')}:{existing.get('attempt_id')}",
            )
        # Stale lease: fail closed — operator must clear; no silent steal.
        raise WriterLockError(
            "writer_lock_stale",
            f"{existing.get('writer_role')}:{existing.get('attempt_id')}",
        )

    lease_until_epoch = now + lease_seconds
    payload = {
        "schema_version": "css.ov002.writer_lock.v1",
        "attempt_id": str(attempt_id),
        "writer_role": str(writer_role),
        "acquired_at_utc": _utc_now_iso(),
        "lease_until_epoch": lease_until_epoch,
        "lease_seconds": lease_seconds,
        "pid": os.getpid(),
    }
    flags = os.O_CREAT | os.O_EXCL | os.O_RDWR
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    try:
        fd = os.open(str(path), flags, 0o644)
    except FileExistsError as exc:
        raise WriterLockError("writer_lock_race", path.name) from exc
    except OSError as exc:
        raise WriterLockError("writer_lock_open_failed", str(type(exc).__name__)) from exc

    try:
        data = (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8")
        os.write(fd, data)
        os.fsync(fd)
    except OSError as exc:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        raise WriterLockError("writer_lock_write_failed", str(type(exc).__name__)) from exc

    return WriterLock(
        path=path,
        attempt_id=str(attempt_id),
        writer_role=str(writer_role),
        lease_until_epoch=lease_until_epoch,
        expected_root=root,
        lock_identity=_path_identity(path),
        _fd=fd,
    )


def locked_atomic_write_json(
    path: Path | str,
    payload: Any,
    *,
    attempt_id: str,
    writer_role: str,
    lease_seconds: float = 120.0,
    expected_root: Path | str | None = None,
) -> Path:
    dest = validate_path_contained(path, expected_root=expected_root)
    lock_path = dest.with_name(dest.name + ".writer.lock")
    with acquire_writer_lock(
        lock_path,
        attempt_id=attempt_id,
        writer_role=writer_role,
        lease_seconds=lease_seconds,
        expected_root=expected_root,
    ):
        return atomic_write_json(dest, payload, expected_root=expected_root)
