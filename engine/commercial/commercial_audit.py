"""Append-only, hash-chained audit history for commercial controls.

Guarantees provided (and only these):

* Application semantics are append-only: this class exposes no update or
  delete API, and SQLite triggers abort any UPDATE or DELETE on the table, so
  application code sharing the database cannot rewrite history either.
* Tamper evidence: each event stores the SHA-256 of its canonical content
  chained to the previous event's hash. ``verify()`` recomputes the chain and
  reports the first inconsistent event.

This is NOT cryptographic immutability. Someone with direct write access to the
database file can drop the triggers and rewrite the whole chain consistently;
detecting that requires anchoring the head hash outside this database.
Corrections are recorded as new events; original events are never modified.
"""
import hashlib
import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

GENESIS_HASH = "0" * 64

_FIELDS = (
    "event_id", "occurred_at", "actor_id", "actor_role", "action", "object_type",
    "object_id", "previous_state", "resulting_state", "outcome", "reason",
    "correlation_id", "maker_id", "checker_id", "reference", "evidence_ref", "details_json",
)


class AuditOutcome:
    SUCCEEDED = "SUCCEEDED"
    DENIED = "DENIED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class CommercialAuditEvent:
    seq: int
    event_id: str
    occurred_at: str
    actor_id: Optional[str]
    actor_role: Optional[str]
    action: str
    object_type: str
    object_id: Optional[str]
    previous_state: Optional[str]
    resulting_state: Optional[str]
    outcome: str
    reason: Optional[str]
    correlation_id: Optional[str]
    maker_id: Optional[str]
    checker_id: Optional[str]
    reference: Optional[str]
    evidence_ref: Optional[str]
    details_json: str
    prev_hash: str
    event_hash: str

    @property
    def details(self) -> Dict[str, Any]:
        return json.loads(self.details_json)


@dataclass(frozen=True)
class AuditVerification:
    ok: bool
    events_checked: int
    first_invalid_seq: Optional[int] = None
    problem: Optional[str] = None


def _event_hash(prev_hash: str, content: Dict[str, Any]) -> str:
    canonical = json.dumps({"prev_hash": prev_hash, **{k: content[k] for k in _FIELDS}}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class CommercialAuditLog:
    def __init__(self, db_path: str):
        self.db_path = str(Path(db_path))
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS commercial_audit_events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    occurred_at TEXT NOT NULL,
                    actor_id TEXT,
                    actor_role TEXT,
                    action TEXT NOT NULL,
                    object_type TEXT NOT NULL,
                    object_id TEXT,
                    previous_state TEXT,
                    resulting_state TEXT,
                    outcome TEXT NOT NULL,
                    reason TEXT,
                    correlation_id TEXT,
                    maker_id TEXT,
                    checker_id TEXT,
                    reference TEXT,
                    evidence_ref TEXT,
                    details_json TEXT NOT NULL,
                    prev_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL UNIQUE
                )"""
            )
            conn.execute(
                """CREATE TRIGGER IF NOT EXISTS commercial_audit_events_no_update
                BEFORE UPDATE ON commercial_audit_events
                BEGIN SELECT RAISE(ABORT, 'commercial audit events are append-only'); END"""
            )
            conn.execute(
                """CREATE TRIGGER IF NOT EXISTS commercial_audit_events_no_delete
                BEFORE DELETE ON commercial_audit_events
                BEGIN SELECT RAISE(ABORT, 'commercial audit events are append-only'); END"""
            )
        finally:
            conn.close()

    def append(
        self,
        *,
        action: str,
        object_type: str,
        outcome: str,
        actor_id: Optional[str] = None,
        actor_role: Optional[str] = None,
        object_id: Optional[str] = None,
        previous_state: Optional[str] = None,
        resulting_state: Optional[str] = None,
        reason: Optional[str] = None,
        correlation_id: Optional[str] = None,
        maker_id: Optional[str] = None,
        checker_id: Optional[str] = None,
        reference: Optional[str] = None,
        evidence_ref: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> CommercialAuditEvent:
        if not action or not object_type or not outcome:
            raise ValueError("audit action, object_type and outcome are required")
        content = {
            "event_id": str(uuid.uuid4()),
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "actor_id": actor_id, "actor_role": actor_role, "action": action,
            "object_type": object_type, "object_id": object_id,
            "previous_state": previous_state, "resulting_state": resulting_state,
            "outcome": outcome, "reason": reason, "correlation_id": correlation_id,
            "maker_id": maker_id, "checker_id": checker_id, "reference": reference,
            "evidence_ref": evidence_ref,
            "details_json": json.dumps(details or {}, sort_keys=True, default=str),
        }
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT event_hash FROM commercial_audit_events ORDER BY seq DESC LIMIT 1").fetchone()
            prev_hash = row["event_hash"] if row else GENESIS_HASH
            event_hash = _event_hash(prev_hash, content)
            cur = conn.execute(
                f"INSERT INTO commercial_audit_events ({', '.join(_FIELDS)}, prev_hash, event_hash) "
                f"VALUES ({', '.join('?' for _ in _FIELDS)}, ?, ?)",
                tuple(content[k] for k in _FIELDS) + (prev_hash, event_hash),
            )
            seq = cur.lastrowid
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()
        return CommercialAuditEvent(seq=seq, prev_hash=prev_hash, event_hash=event_hash, **content)

    def events(self, *, object_type: Optional[str] = None, object_id: Optional[str] = None) -> List[CommercialAuditEvent]:
        sql, params = "SELECT * FROM commercial_audit_events", []
        clauses = []
        if object_type is not None:
            clauses.append("object_type=?")
            params.append(object_type)
        if object_id is not None:
            clauses.append("object_id=?")
            params.append(object_id)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY seq"
        conn = self._connect()
        try:
            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()
        return [CommercialAuditEvent(**dict(r)) for r in rows]

    def verify(self) -> AuditVerification:
        prev_hash = GENESIS_HASH
        events = self.events()
        for event in events:
            if event.prev_hash != prev_hash:
                return AuditVerification(False, len(events), event.seq, "chain link broken")
            if _event_hash(prev_hash, asdict(event)) != event.event_hash:
                return AuditVerification(False, len(events), event.seq, "event content does not match its hash")
            prev_hash = event.event_hash
        return AuditVerification(True, len(events))

    def head_hash(self) -> str:
        events = self.events()
        return events[-1].event_hash if events else GENESIS_HASH


# ---------------------------------------------------------------------------
# External anchoring
#
# The hash chain detects edits, but whoever can write the database file can
# rebuild a fully consistent chain. Periodically recording (seq, head hash)
# checkpoints somewhere the database writer cannot rewrite, and verifying
# the live chain against them, detects that too. This module appends
# checkpoints to a JSONL file; keeping that file on separate, write-once
# storage is a deployment responsibility.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AuditAnchor:
    seq: int
    event_hash: str
    events: int
    anchored_at: str


@dataclass(frozen=True)
class AnchorVerification:
    ok: bool
    anchors_checked: int
    problem: Optional[str] = None
    anchor_seq: Optional[int] = None


def write_anchor(log: "CommercialAuditLog", anchor_path: str) -> Optional[AuditAnchor]:
    """Append a checkpoint of the current head to ``anchor_path``.

    Refuses to anchor a chain that does not verify, so a tampered chain can
    never be blessed by a new checkpoint. Returns None for an empty log.
    """
    verification = log.verify()
    if not verification.ok:
        raise ValueError(f"refusing to anchor an invalid audit chain (seq {verification.first_invalid_seq}: {verification.problem})")
    events = log.events()
    if not events:
        return None
    head = events[-1]
    anchor = AuditAnchor(seq=head.seq, event_hash=head.event_hash, events=len(events),
                         anchored_at=datetime.now(timezone.utc).isoformat())
    path = Path(anchor_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(anchor), sort_keys=True) + "\n")
    return anchor


def read_anchors(anchor_path: str) -> List[AuditAnchor]:
    path = Path(anchor_path)
    if not path.exists():
        return []
    return [AuditAnchor(**json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def verify_against_anchors(log: "CommercialAuditLog", anchor_path: str) -> AnchorVerification:
    """Every anchored event must still exist with the same hash, the chain
    must verify, and no anchored history may have been truncated."""
    anchors = read_anchors(anchor_path)
    chain = log.verify()
    if not chain.ok:
        return AnchorVerification(False, 0, f"chain invalid at seq {chain.first_invalid_seq}: {chain.problem}")
    by_seq = {e.seq: e for e in log.events()}
    for anchor in anchors:
        event = by_seq.get(anchor.seq)
        if event is None:
            return AnchorVerification(False, len(anchors), "anchored event is missing (history truncated or rebuilt)", anchor.seq)
        if event.event_hash != anchor.event_hash:
            return AnchorVerification(False, len(anchors), "anchored event hash differs (history rewritten)", anchor.seq)
        if sum(1 for s in by_seq if s <= anchor.seq) != anchor.events:
            return AnchorVerification(False, len(anchors), "event count before anchor changed", anchor.seq)
    return AnchorVerification(True, len(anchors))
