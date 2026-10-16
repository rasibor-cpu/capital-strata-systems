"""Append-only, hash-chained JSONL log with a head anchor.

Each entry carries prev_hash and entry_hash (SHA-256 of its canonical JSON). A separate
head file records the entry count and last hash, so editing, reordering, deleting or
truncating entries (e.g. dropping a trailing suspension) is detected and fails closed.
Callers must hold their own lock around append().
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from backend.certification.ov002_persistence import (
    PersistenceError,
    atomic_append_jsonl,
    atomic_write_json,
    read_json_object,
)

GENESIS = "GENESIS"


def canonical(body: Mapping[str, Any]) -> bytes:
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")


class HashChainLog:
    def __init__(self, root: Path, name: str, error: type[Exception]) -> None:
        self.root = Path(root)
        self.path = self.root / f"{name}.jsonl"
        self.head_path = self.root / f"{name}.head.json"
        self._error = error
        self._broken = f"{name}_chain_broken"

    def events(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            if self.head_path.exists():
                raise self._error(self._broken)
            return []
        prev, out = GENESIS, []
        try:
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                event = json.loads(line)
                claimed = event.pop("entry_hash", None)
                if event.get("prev_hash") != prev or hashlib.sha256(canonical(event)).hexdigest() != claimed:
                    raise self._error(self._broken)
                prev = event["entry_hash"] = claimed
                out.append(event)
            head = read_json_object(self.head_path)
        except (ValueError, PersistenceError) as exc:
            raise self._error(self._broken) from exc
        if head.get("count") != len(out) or head.get("head_hash") != prev:
            raise self._error(self._broken)
        return out

    def append(self, body: Mapping[str, Any]) -> dict[str, Any]:
        events = self.events()
        event = {**dict(body), "prev_hash": events[-1]["entry_hash"] if events else GENESIS}
        event["entry_hash"] = hashlib.sha256(canonical(event)).hexdigest()
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_append_jsonl(self.path, event, expected_root=self.root)
        atomic_write_json(self.head_path, {"count": len(events) + 1, "head_hash": event["entry_hash"]},
                          expected_root=self.root)
        return event
