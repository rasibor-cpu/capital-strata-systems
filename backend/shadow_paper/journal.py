"""Append-only, hash-chained JSONL event journal for the shadow paper runner.

Each line is one JSON object with a contiguous ``seq``, a unique ``event_id``,
an optional unique ``dedupe_key``, the previous line's hash and its own SHA-256
hash. Any break (edited, deleted, reordered, duplicated or truncated line) is a
JournalIntegrityError; the runner refuses to start on a broken journal.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

from backend.shadow_paper import SCHEMA_VERSION

LOGGER = logging.getLogger(__name__)

GENESIS_HASH = "0" * 64


class JournalIntegrityError(RuntimeError):
    """The journal cannot be trusted; operation must not continue."""


def _canonical(record: dict[str, Any]) -> str:
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def compute_hash(record: dict[str, Any]) -> str:
    body = {k: v for k, v in record.items() if k != "hash"}
    return hashlib.sha256(_canonical(body).encode("ascii")).hexdigest()


def read_journal(path: Path) -> list[dict[str, Any]]:
    """Read and fully verify a journal. Missing file means an empty journal."""
    path = Path(path)
    if not path.exists():
        return []

    raw = path.read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise JournalIntegrityError("journal ends with a partial (unterminated) line")

    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_keys: set[str] = set()
    prev_hash = GENESIS_HASH

    for line_no, line in enumerate(raw.decode("utf-8").splitlines(), start=1):
        if not line.strip():
            raise JournalIntegrityError(f"line {line_no}: blank line")
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise JournalIntegrityError(f"line {line_no}: invalid JSON ({exc.msg})") from exc
        if not isinstance(record, dict):
            raise JournalIntegrityError(f"line {line_no}: not an object")
        if record.get("schema") != SCHEMA_VERSION:
            raise JournalIntegrityError(f"line {line_no}: unexpected schema {record.get('schema')!r}")
        if record.get("seq") != line_no:
            raise JournalIntegrityError(f"line {line_no}: seq {record.get('seq')!r} is not contiguous")
        if record.get("prev_hash") != prev_hash:
            raise JournalIntegrityError(f"line {line_no}: prev_hash does not chain")
        if record.get("hash") != compute_hash(record):
            raise JournalIntegrityError(f"line {line_no}: hash mismatch (record altered)")
        event_id = record.get("event_id")
        if not isinstance(event_id, str) or event_id in seen_ids:
            raise JournalIntegrityError(f"line {line_no}: missing or duplicate event_id")
        seen_ids.add(event_id)
        key = record.get("dedupe_key")
        if key is not None:
            if key in seen_keys:
                raise JournalIntegrityError(f"line {line_no}: duplicate dedupe_key {key!r}")
            seen_keys.add(key)
        prev_hash = record["hash"]
        records.append(record)

    return records


class EventJournal:
    """Single-writer append-only journal. Verifies existing content on open."""

    def __init__(
        self,
        path: Path,
        *,
        run_id: str,
        commit_sha: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.path = Path(path)
        self.run_id = str(run_id)
        self.commit_sha = str(commit_sha)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self.path.parent.mkdir(parents=True, exist_ok=True)

        self.records = read_journal(self.path)  # raises JournalIntegrityError
        self._seq = len(self.records)
        self._prev_hash = self.records[-1]["hash"] if self.records else GENESIS_HASH
        self._dedupe_keys = {r["dedupe_key"] for r in self.records if r.get("dedupe_key") is not None}

    def has_key(self, dedupe_key: str) -> bool:
        return dedupe_key in self._dedupe_keys

    def append(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        dedupe_key: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Append one event. Returns None (and writes nothing) for a duplicate dedupe_key."""
        if dedupe_key is not None and dedupe_key in self._dedupe_keys:
            LOGGER.info("shadow journal: duplicate event suppressed (%s)", dedupe_key)
            return None

        record: dict[str, Any] = {
            "schema": SCHEMA_VERSION,
            "seq": self._seq + 1,
            "event_id": uuid.uuid4().hex,
            "dedupe_key": dedupe_key,
            "type": str(event_type),
            "ts_utc": self._clock().astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "run_id": self.run_id,
            "commit_sha": self.commit_sha,
            "payload": payload,
            "prev_hash": self._prev_hash,
        }
        record["hash"] = compute_hash(record)
        line = _canonical(record) + "\n"

        with self.path.open("a", encoding="ascii", newline="\n") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())

        self._seq += 1
        self._prev_hash = record["hash"]
        if dedupe_key is not None:
            self._dedupe_keys.add(dedupe_key)
        self.records.append(record)
        return record

    def iter_type(self, event_type: str) -> Iterator[dict[str, Any]]:
        return (r for r in self.records if r.get("type") == event_type)
