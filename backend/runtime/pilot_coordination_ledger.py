"""Authoritative pilot exposure coordination ledger (CSS-062 Blocker 1, 3, 5).

This ledger makes the existing ``pilot_reservations`` table the SINGLE
authoritative exposure view. It adds nonce consumption, coordination
metadata and audit records to the SAME database, so that legacy and new
writers share one capacity view and cannot diverge.

Design (owner-approved 2026-10-13, corrected per 5-blocker review):

- Capacity authority: the existing ``pilot_reservations`` table, unchanged.
- Coordination records: a NEW ``pilot_coordination`` table in the same DB,
  keyed by (approval_id) with a UNIQUE index on (issuer_id, nonce). A nonce
  is consumed EXACTLY ONCE, permanently (even after RELEASED/ROLLED_BACK).
- Atomicity: ONE ``BEGIN IMMEDIATE`` transaction on ONE SQLite connection
  covers replay checks, duplicate-child checks, capacity checks (CAD
  20/40/2-parents from ``CanonicalOrderLimitConfig``), and the insert of
  the nonce-consumption + reservation + audit records.
- No claim files. No caller-supplied capacity limits.

Recovery semantics:
- Before COMMIT: neither the nonce nor the reservation survives.
- After COMMIT: both survive; the nonce is permanently consumed.
- Commit-acknowledgment uncertainty: reconcile via the durable
  ``pilot_coordination`` row; do NOT assume denial and do NOT release.

Nothing here grants live-execution, broker, or trading authority.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from backend.config.order_limit_config import CanonicalOrderLimitConfig
from backend.runtime.pilot_exposure_reservation import PilotExposureReservationLedger

__all__ = [
    "AuthoritativePilotCoordinationLedger",
    "CoordinationReceipt",
    "LocalSimulatorOutcomeEvidence",
    "PilotCoordinationError",
    "PilotCoordinationReplayError",
]

_SIMULATOR_OUTCOMES = frozenset({"confirmed_no_fill", "confirmed_fill"})


@dataclass(frozen=True)
class LocalSimulatorOutcomeEvidence:
    """Typed local-simulator outcome record (CSS-062 Blocker 5).

    Independent review (2026-10-13) corrections:
    - The ledger accepts ONLY this exact type (no duck-typed objects).
    - The record is bound to one ``child_id``; it cannot release or commit a
      different reservation.
    - The outcome must match the requested transition: ``confirmed_no_fill``
      may only RELEASE, ``confirmed_fill`` may only COMMIT.

    LIMITATION (documented, not hidden): this is an in-process typed record,
    NOT a cryptographic attestation. ``evidence_hash`` is carried for audit
    but is not authenticated. Whoever constructs the record asserts the
    outcome. That is acceptable only for the local simulation path; any
    paper-broker or production integration requires authenticated broker
    outcome evidence, which is not implemented here.
    """

    outcome: str  # "confirmed_no_fill" | "confirmed_fill"
    simulator_instance_id: str
    evidence_hash: str
    child_id: str

    def verified_outcome(self) -> str:
        """Return the outcome if it is one of the allowed values, else raise."""
        if type(self.outcome) is not str or self.outcome not in _SIMULATOR_OUTCOMES:
            raise ValueError(f"invalid outcome: {self.outcome!r}")
        return self.outcome


class PilotCoordinationError(RuntimeError):
    """Base error for the coordination ledger."""


class PilotCoordinationReplayError(PilotCoordinationError):
    """Raised when a nonce is replayed or an approval_id is duplicated."""


@dataclass(frozen=True)
class CoordinationReceipt:
    success: bool
    reason: str
    approval_id: str
    nonce: str
    child_id: str
    reserved_cad: str
    transaction_id: str


class AuthoritativePilotCoordinationLedger:
    """Single-authority SQLite coordination ledger over ``pilot_reservations``."""

    _SCHEMA_VERSION = 2

    def __init__(
        self,
        path: Path | str,
        *,
        config: CanonicalOrderLimitConfig,
    ) -> None:
        if not isinstance(config, CanonicalOrderLimitConfig):
            raise PilotCoordinationError("CanonicalOrderLimitConfig required")
        config.validate()
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.config = config
        # Reuse the existing exposure ledger's connection setup so that we
        # read/write the SAME database with the same pragmas.
        self._exposure = PilotExposureReservationLedger(self.path, config=config)
        self._local = threading.local()
        self._ensure_schema()

    # ------------------------------------------------------------- schema
    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS pilot_coordination (
                    approval_id TEXT PRIMARY KEY,
                    nonce TEXT NOT NULL,
                    issuer_id TEXT NOT NULL,
                    candidate_sha TEXT NOT NULL,
                    child_id TEXT NOT NULL,
                    parent_id TEXT NOT NULL,
                    reserved_cad TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('PENDING','COMMITTED','ROLLED_BACK')),
                    created_at TEXT NOT NULL,
                    committed_at TEXT,
                    schema_version INTEGER NOT NULL DEFAULT 2
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_pilot_coordination_nonce
                    ON pilot_coordination (issuer_id, nonce);
                CREATE TABLE IF NOT EXISTS pilot_coordination_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    approval_id TEXT NOT NULL,
                    event TEXT NOT NULL,
                    details TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS pilot_coordination_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                INSERT OR IGNORE INTO pilot_coordination_meta (key, value)
                    VALUES ('schema_version', '2');
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(str(self.path), timeout=30.0, isolation_level=None)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("PRAGMA busy_timeout=30000")
            self._local.conn = conn
        return conn

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _money(value: Any, name: str) -> Decimal:
        if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
            raise PilotCoordinationError(f"invalid decimal: {name}")
        try:
            amount = Decimal(str(value).strip())
        except (InvalidOperation, ValueError, AttributeError) as exc:
            raise PilotCoordinationError(f"invalid decimal: {name}") from exc
        if not amount.is_finite():
            raise PilotCoordinationError(f"non-finite decimal: {name}")
        return amount

    # ----------------------------------------------------- legacy migration
    def reconcile_legacy(self) -> dict[str, Any]:
        """Idempotent reconciliation of legacy pilot_reservations.

        Every legacy OPEN/COMMITTED reservation must appear in
        ``pilot_coordination`` as a COMMITTED record so that the nonce
        accounting is consistent. Legacy rows are preserved as-is (their
        ``state`` and amounts are authoritative). The coordination record
        is created with the same ``child_id``/``parent_id``/``reserved_cad``
        and a synthetic legacy nonce (issuer_id='legacy') that is permanently
        consumed.

        Returns a summary: {created, skipped, failures}. Fail-closed on any
        inconsistency (an existing reservation whose child_id has a
        non-COMMITTED coordination record, or a coordination record whose
        reservation is missing).
        """
        created = 0
        skipped = 0
        failures: list[str] = []
        try:
            with self._transaction() as conn:
                # 1. Every OPEN/COMMITTED reservation must have a COMMITTED coordination record.
                rows = conn.execute(
                    "SELECT child_id, parent_id, reserved_cad, state "
                    "FROM pilot_reservations WHERE state IN ('OPEN','COMMITTED')"
                ).fetchall()
                for row in rows:
                    child = str(row["child_id"])
                    parent = str(row["parent_id"])
                    reserved = str(row["reserved_cad"])
                    state = str(row["state"])
                    # Independent review fix: a reservation already coordinated
                    # by the trusted path (any issuer) must NOT receive a
                    # second synthetic legacy record.
                    coord = conn.execute(
                        "SELECT state FROM pilot_coordination WHERE child_id=? "
                        "ORDER BY CASE state WHEN 'COMMITTED' THEN 0 ELSE 1 END LIMIT 1",
                        (child,),
                    ).fetchone()
                    if coord is not None and str(coord["state"]) == "COMMITTED":
                        skipped += 1
                        continue
                    if coord is not None and str(coord["state"]) != "COMMITTED":
                        failures.append(
                            f"LEGACY_COORDINATION_STATE_INVALID: child={child} coord_state={coord['state']} res_state={state}"
                        )
                        continue
                    conn.execute(
                        "INSERT OR IGNORE INTO pilot_coordination "
                        "(approval_id, nonce, issuer_id, candidate_sha, child_id, parent_id, reserved_cad, state, created_at, committed_at, schema_version) "
                        "VALUES(?,?,?,?,?,?,?,'COMMITTED',?,?,2)",
                        (
                            f"legacy:{child}",
                            f"legacy-nonce:{child}",
                            "legacy",
                            "legacy",
                            child,
                            parent,
                            reserved,
                            self._now_iso(),
                            self._now_iso(),
                        ),
                    )
                    if conn.execute("SELECT changes()").fetchone()[0] == 1:
                        created += 1

                # 2. Every COMMITTED coordination record must have a matching reservation.
                committed = conn.execute(
                    "SELECT approval_id, child_id FROM pilot_coordination WHERE state='COMMITTED'"
                ).fetchall()
                for row in committed:
                    child = str(row["child_id"])
                    res = conn.execute(
                        "SELECT state FROM pilot_reservations WHERE child_id=?",
                        (child,),
                    ).fetchone()
                    if res is None:
                        # Only legacy records may have a missing reservation.
                        approval = str(row["approval_id"])
                        if approval.startswith("legacy:"):
                            continue
                        failures.append(f"JOURNAL_DESYNC: approval={approval} child={child} has no reservation")
                    elif str(res["state"]) == "RELEASED":
                        # Legitimate terminal state — not a desync.
                        pass
        except PilotCoordinationError as exc:
            return {"created": created, "skipped": skipped, "failures": [f"RECONCILIATION_ERROR:{exc}"]}
        if failures:
            return {"created": created, "skipped": skipped, "failures": failures}
        return {"created": created, "skipped": skipped, "failures": []}

    def verify_consistency(self) -> dict[str, Any]:
        """Reconcile coordination records against pilot_reservations."""
        problems: list[str] = []
        with self._connect() as conn:
            committed = conn.execute(
                "SELECT approval_id, child_id FROM pilot_coordination WHERE state='COMMITTED'"
            ).fetchall()
            for row in committed:
                child = str(row["child_id"])
                res = conn.execute(
                    "SELECT state FROM pilot_reservations WHERE child_id=?",
                    (child,),
                ).fetchone()
                approval = str(row["approval_id"])
                if res is None:
                    if approval.startswith("legacy:"):
                        continue
                    problems.append(f"JOURNAL_DESYNC: approval={approval} child={child} has no reservation")
                elif str(res["state"]) == "RELEASED":
                    # Legitimate terminal state.
                    pass
            reservations = conn.execute(
                "SELECT child_id FROM pilot_reservations WHERE state IN ('OPEN','COMMITTED')"
            ).fetchall()
            committed_children = {str(r["child_id"]) for r in committed}
            for row in reservations:
                child = str(row["child_id"])
                if child not in committed_children:
                    # A legacy OPEN/COMMITTED reservation with no coordination record.
                    # reconcile_legacy() fixes this; report as OUTSTANDING.
                    problems.append(f"OUTSTANDING_LEGACY_RESERVATION: child={child} has no COMMITTED coordination record")
        return {"consistent": not problems, "problems": problems}

    # --------------------------------------------------------- public API
    def nonce_is_consumed(self, *, issuer_id: str, nonce: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM pilot_coordination WHERE issuer_id=? AND nonce=? AND state!='ROLLED_BACK'",
                (str(issuer_id), str(nonce)),
            ).fetchone()
        return row is not None

    def approval_exists(self, approval_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM pilot_coordination WHERE approval_id=?",
                (str(approval_id),),
            ).fetchone()
        return row is not None

    def coordination_state(self, *, approval_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT state FROM pilot_coordination WHERE approval_id=?",
                (str(approval_id).strip(),),
            ).fetchone()
        return str(row["state"]) if row is not None else None

    def atomic_consume_and_reserve(
        self,
        *,
        approval_id: str,
        nonce: str,
        issuer_id: str,
        candidate_sha: str,
        parent_id: str,
        child_id: str,
        proposed_child_cad: Any,
        estimated_fees_cad: Any,
    ) -> CoordinationReceipt:
        """Atomically consume the nonce AND reserve exposure in ONE transaction.

        Capacity limits come from ``self.config`` (CanonicalOrderLimitConfig),
        NOT from caller input. No caller can raise the ceilings.
        """
        approval_id = str(approval_id).strip()
        nonce = str(nonce).strip()
        child_id = str(child_id).strip()
        parent_id = str(parent_id).strip()
        if not approval_id or not nonce or not child_id or not parent_id:
            return CoordinationReceipt(
                False, "COORDINATION_MISSING_FIELDS", approval_id, nonce, child_id, "0.00", ""
            )
        try:
            proposed = self._money(proposed_child_cad, "proposed_child_cad")
            fees = self._money(estimated_fees_cad, "estimated_fees_cad")
        except PilotCoordinationError as exc:
            return CoordinationReceipt(
                False, f"COORDINATION_INVALID_AMOUNT:{exc}", approval_id, nonce, child_id, "0.00", ""
            )
        if proposed <= 0 or fees < 0:
            return CoordinationReceipt(
                False, "COORDINATION_NONPOSITIVE", approval_id, nonce, child_id, "0.00", ""
            )
        reserve_amount = proposed + fees
        if reserve_amount <= 0:
            return CoordinationReceipt(
                False, "COORDINATION_NONPOSITIVE", approval_id, nonce, child_id, "0.00", ""
            )

        transaction_id = self._new_transaction_id()
        created_at = self._now_iso()
        max_parent = self.config.live_pilot_max_position_cad
        max_total = self.config.live_pilot_max_total_cad
        max_parents = self.config.live_pilot_max_concurrent_positions

        try:
            with self._transaction() as conn:
                # Replay/duplicate checks (inside the write transaction).
                existing_nonce = conn.execute(
                    "SELECT approval_id FROM pilot_coordination WHERE issuer_id=? AND nonce=? AND state!='ROLLED_BACK'",
                    (str(issuer_id), nonce),
                ).fetchone()
                if existing_nonce is not None:
                    return CoordinationReceipt(
                        False, "COORDINATION_REPLAY_REJECTED",
                        approval_id, nonce, child_id, "0.00", transaction_id,
                    )
                existing_approval = conn.execute(
                    "SELECT 1 FROM pilot_coordination WHERE approval_id=?",
                    (approval_id,),
                ).fetchone()
                if existing_approval is not None:
                    return CoordinationReceipt(
                        False, "COORDINATION_REPLAY_REJECTED",
                        approval_id, nonce, child_id, "0.00", transaction_id,
                    )
                existing_child = conn.execute(
                    "SELECT 1 FROM pilot_reservations WHERE child_id=? AND state IN ('OPEN','COMMITTED')",
                    (child_id,),
                ).fetchone()
                if existing_child is not None:
                    return CoordinationReceipt(
                        False, "COORDINATION_DUPLICATE_CHILD_RESERVATION",
                        approval_id, nonce, child_id, "0.00", transaction_id,
                    )

                # Capacity checks against the AUTHORITATIVE pilot_reservations table.
                rows = conn.execute(
                    "SELECT parent_id, reserved_cad FROM pilot_reservations WHERE state IN ('OPEN','COMMITTED')"
                ).fetchall()
                parent_totals: dict[str, Decimal] = {}
                total = Decimal("0.00")
                for row in rows:
                    amount = self._money(row["reserved_cad"], "stored_reserved_cad")
                    pid = str(row["parent_id"])
                    parent_totals[pid] = parent_totals.get(pid, Decimal("0.00")) + amount
                    total += amount
                existing_parent = parent_totals.get(parent_id, Decimal("0.00"))
                projected_parent = existing_parent + reserve_amount
                projected_total = total + reserve_amount
                projected_count = len(parent_totals) + (0 if parent_id in parent_totals else 1)

                if max_parent is not None and projected_parent > max_parent:
                    return CoordinationReceipt(
                        False, "COORDINATION_PARENT_EXPOSURE_CEILING",
                        approval_id, nonce, child_id, str(reserve_amount), transaction_id,
                    )
                if projected_count > max_parents:
                    return CoordinationReceipt(
                        False, "COORDINATION_CONCURRENT_PARENT_CEILING",
                        approval_id, nonce, child_id, str(reserve_amount), transaction_id,
                    )
                if max_total is not None and projected_total > max_total:
                    return CoordinationReceipt(
                        False, "COORDINATION_TOTAL_EXPOSURE_CEILING",
                        approval_id, nonce, child_id, str(reserve_amount), transaction_id,
                    )

                # Insert nonce-consumption + reservation + audit in ONE transaction.
                conn.execute(
                    "INSERT INTO pilot_coordination "
                    "(approval_id, nonce, issuer_id, candidate_sha, child_id, parent_id, reserved_cad, state, created_at, committed_at, schema_version) "
                    "VALUES(?,?,?,?,?,?,?,'COMMITTED',?,?,2)",
                    (
                        approval_id, nonce, str(issuer_id), str(candidate_sha),
                        child_id, parent_id, str(reserve_amount), created_at, created_at,
                    ),
                )
                conn.execute(
                    "INSERT INTO pilot_reservations(child_id,parent_id,reserved_cad,state) "
                    "VALUES(?,?,?,'OPEN')",
                    (child_id, parent_id, str(reserve_amount)),
                )
                conn.execute(
                    "INSERT INTO pilot_coordination_audit (approval_id, event, details, recorded_at) "
                    "VALUES(?,?,?,?)",
                    (
                        approval_id,
                        "ATOMIC_CONSUME_AND_RESERVE_COMMITTED",
                        json.dumps(
                            {
                                "transaction_id": transaction_id,
                                "nonce": nonce,
                                "child_id": child_id,
                                "parent_id": parent_id,
                                "reserved_cad": str(reserve_amount),
                                "fees_cad": str(fees),
                                "candidate_sha": str(candidate_sha),
                                "issuer_id": str(issuer_id),
                            },
                            sort_keys=True,
                        ),
                        created_at,
                    ),
                )
                return CoordinationReceipt(
                    True, "COORDINATION_COMMITTED",
                    approval_id, nonce, child_id, str(reserve_amount), transaction_id,
                )
        except PilotCoordinationReplayError as exc:
            return CoordinationReceipt(False, f"COORDINATION_REPLAY_REJECTED:{exc}", approval_id, nonce, child_id, "0.00", transaction_id)
        except sqlite3.IntegrityError as exc:
            # Unique-constraint violation (nonce or approval_id already committed).
            # The nonce is NEVER reusable, even after ROLLED_BACK.
            return CoordinationReceipt(False, f"COORDINATION_REPLAY_REJECTED:{exc}", approval_id, nonce, child_id, "0.00", transaction_id)
        except PilotCoordinationError as exc:
            # e.g. a corrupt stored amount read inside the transaction (rolled back).
            return CoordinationReceipt(
                False, f"COORDINATION_STATE_INVALID:{exc}", approval_id, nonce, child_id, "0.00", transaction_id
            )
        except sqlite3.Error as exc:
            # A SQLite error AFTER COMMIT is ambiguous: the transaction may
            # actually be durable. Reconcile before returning a denial.
            # Independent review fix: durability must be proven for THIS
            # transaction (its unique transaction_id in the committed audit
            # record), not merely the existence of the approval_id — otherwise
            # a replayed approval_id that hits a SQLite error would be
            # reported as a success.
            try:
                durable = self._transaction_is_durable(
                    approval_id=approval_id, transaction_id=transaction_id
                )
            except Exception:
                durable = False
            if durable:
                # The commit succeeded but the acknowledgment failed. The nonce
                # is consumed and the reservation is durable — report
                # COMMIT_ACK_UNCERTAIN (do NOT assume denial, do NOT release).
                return CoordinationReceipt(
                    True, "COORDINATION_COMMIT_ACK_UNCERTAIN",
                    approval_id, nonce, child_id, str(reserve_amount), transaction_id,
                )
            # The commit genuinely failed. No state survives.
            return CoordinationReceipt(
                False, f"COORDINATION_SQLITE_ERROR:{exc}", approval_id, nonce, child_id, "0.00", transaction_id
            )

    def release_reservation(
        self,
        *,
        child_id: str,
        reason: str,
        confirmed_by_simulator: Any = None,
    ) -> bool:
        """Release an OPEN reservation. The nonce is NEVER reusable.

        ``confirmed_by_simulator`` must be an object with a verifiable
        local-simulator outcome evidence method. A caller-supplied string is
        NOT evidence. If no simulator evidence is provided, the release is
        refused (fail closed).
        """
        child_id = str(child_id).strip()
        if not self._verify_simulator_evidence(
            confirmed_by_simulator, child_id=child_id, required_outcome="confirmed_no_fill"
        ):
            return False
        try:
            with self._transaction() as conn:
                row = conn.execute(
                    "SELECT child_id, state FROM pilot_reservations WHERE child_id=?",
                    (child_id,),
                ).fetchone()
                if row is None or str(row["state"]) != "OPEN":
                    return False
                conn.execute(
                    "UPDATE pilot_reservations SET state='RELEASED' WHERE child_id=? AND state='OPEN'",
                    (child_id,),
                )
                conn.execute(
                    "INSERT INTO pilot_coordination_audit (approval_id, event, details, recorded_at) VALUES(?,?,?,?)",
                    (
                        child_id,
                        "RESERVATION_RELEASED",
                        json.dumps({"child_id": child_id, "reason": str(reason)}, sort_keys=True),
                        self._now_iso(),
                    ),
                )
                return True
        except (PilotCoordinationError, sqlite3.Error):
            return False

    def commit_reservation(self, *, child_id: str, confirmed_by_simulator: Any = None) -> bool:
        """Transition an OPEN reservation to COMMITTED (verified simulator evidence)."""
        child_id = str(child_id).strip()
        if not self._verify_simulator_evidence(
            confirmed_by_simulator, child_id=child_id, required_outcome="confirmed_fill"
        ):
            return False
        try:
            with self._transaction() as conn:
                cur = conn.execute(
                    "UPDATE pilot_reservations SET state='COMMITTED' WHERE child_id=? AND state='OPEN'",
                    (child_id,),
                )
                if cur.rowcount != 1:
                    return False
                conn.execute(
                    "INSERT INTO pilot_coordination_audit (approval_id, event, details, recorded_at) VALUES(?,?,?,?)",
                    (child_id, "RESERVATION_COMMITTED", json.dumps({"child_id": child_id}, sort_keys=True), self._now_iso()),
                )
                return True
        except (PilotCoordinationError, sqlite3.Error):
            return False

    @staticmethod
    def _verify_simulator_evidence(
        evidence: Any,
        *,
        child_id: str,
        required_outcome: str,
    ) -> bool:
        """Verify local-simulator outcome evidence for ONE transition. Fail closed.

        - exact type ``LocalSimulatorOutcomeEvidence`` (duck types rejected);
        - bound to the same ``child_id``;
        - outcome equals the outcome the transition requires (a fill can
          never release capacity; a no-fill can never commit).
        """
        if type(evidence) is not LocalSimulatorOutcomeEvidence:
            return False
        if type(evidence.child_id) is not str or evidence.child_id.strip() != child_id:
            return False
        try:
            outcome = evidence.verified_outcome()
        except Exception:
            return False
        return outcome == required_outcome

    def _transaction_is_durable(self, *, approval_id: str, transaction_id: str) -> bool:
        """True only if THIS transaction's commit record is durable.

        Uses a fresh connection so a broken thread-local connection cannot
        mask the durable state.
        """
        if not transaction_id:
            return False
        conn = sqlite3.connect(str(self.path), timeout=30.0, isolation_level=None)
        try:
            rows = conn.execute(
                "SELECT details FROM pilot_coordination_audit "
                "WHERE approval_id=? AND event='ATOMIC_CONSUME_AND_RESERVE_COMMITTED'",
                (approval_id,),
            ).fetchall()
        finally:
            conn.close()
        for (details,) in rows:
            try:
                if json.loads(details).get("transaction_id") == transaction_id:
                    return True
            except (ValueError, TypeError, AttributeError):
                continue
        return False

    def reservation_state(self, *, child_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT state FROM pilot_reservations WHERE child_id=?",
                (str(child_id).strip(),),
            ).fetchone()
        return str(row["state"]) if row is not None else None

    def audit_tail(self, *, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT approval_id, event, details, recorded_at FROM pilot_coordination_audit ORDER BY id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [dict(row) for row in rows]

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    @staticmethod
    def _new_transaction_id() -> str:
        import uuid

        return str(uuid.uuid4())
