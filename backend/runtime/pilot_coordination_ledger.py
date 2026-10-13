"""Atomic coordination ledger for governed paper-route simulation (CSS-062).

This module implements the corrected single-authority SQLite transaction design:
nonce consumption, exposure-reservation, capacity checks, and the audit event
are all recorded inside ONE ``BEGIN IMMEDIATE`` transaction on ONE database.
There is no separate claim file used as replay authority; the durable
coordination record in SQLite is the single source of truth.

Recovery semantics (per approved design):
- Before commit: neither nonce consumption nor reservation survives.
- After commit: both survive; the nonce cannot be reused.
- Commit acknowledgment uncertain: reconcile; do not blindly retry or release.
- Simulation dispatch outcome unknown: preserve capacity; reject duplicate dispatch.
- Confirmed no-fill: explicit reconciliation may release capacity; the consumed
  nonce remains consumed (it is never reusable).

This is a SIMULATION-ONLY ledger. It does NOT replace the legacy dual-control
``PilotAuthorizationLedger`` (which remains authoritative for the live/paper
production route). It does NOT grant live-execution, broker, or trading
authority.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from decimal import Decimal, InvalidOperation

__all__ = [
    "PilotCoordinationLedger",
    "CoordinationReceipt",
    "CoordinationDecision",
    "PilotCoordinationError",
    "PilotCoordinationReplayError",
]


class PilotCoordinationError(RuntimeError):
    """Base error for the coordination ledger."""


class PilotCoordinationReplayError(PilotCoordinationError):
    """Raised when a nonce is replayed or an approval_id is duplicated."""


@dataclass(frozen=True)
class CoordinationDecision:
    approved: bool
    reason: str


@dataclass(frozen=True)
class CoordinationReceipt:
    success: bool
    reason: str
    approval_id: str
    nonce: str
    child_id: str
    reserved_cad: str
    transaction_id: str


class PilotCoordinationLedger:
    """One authoritative SQLite transaction spanning nonce + reservation + audit."""

    def __init__(self, db_path: Path) -> None:
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._initialize_schema()

    # ------------------------------------------------------------- schema
    def _initialize_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS coordination_records (
                    approval_id TEXT PRIMARY KEY,
                    nonce TEXT NOT NULL,
                    issuer_id TEXT NOT NULL,
                    candidate_sha TEXT NOT NULL,
                    child_id TEXT NOT NULL,
                    parent_id TEXT NOT NULL,
                    reserved_cad TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (state IN ('PENDING','COMMITTED','ROLLED_BACK')),
                    created_at TEXT NOT NULL,
                    committed_at TEXT
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_coordination_nonce
                    ON coordination_records (issuer_id, nonce);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_coordination_child
                    ON coordination_records (child_id);
                CREATE TABLE IF NOT EXISTS exposure_reservations (
                    child_id TEXT PRIMARY KEY,
                    parent_id TEXT NOT NULL,
                    reserved_cad TEXT NOT NULL,
                    fees_cad TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (state IN ('OPEN','COMMITTED','RELEASED')),
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS coordination_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    approval_id TEXT NOT NULL,
                    event TEXT NOT NULL,
                    details TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(
                str(self.path),
                isolation_level=None,  # manual BEGIN/COMMIT
                timeout=30.0,
            )
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

    # ------------------------------------------------------------ helpers
    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _money(value: Any, name: str) -> Decimal:
        try:
            amount = Decimal(str(value).strip())
        except (InvalidOperation, ValueError, AttributeError) as exc:
            raise PilotCoordinationError(f"invalid decimal: {name}") from exc
        if not amount.is_finite():
            raise PilotCoordinationError(f"non-finite decimal: {name}")
        return amount

    @staticmethod
    def _new_transaction_id() -> str:
        import uuid

        return str(uuid.uuid4())

    # --------------------------------------------------------- public API
    def nonce_is_consumed(self, *, issuer_id: str, nonce: str) -> bool:
        """Check whether a nonce is already consumed. Read-only."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM coordination_records WHERE issuer_id=? AND nonce=? AND state!='ROLLED_BACK'",
                (str(issuer_id), str(nonce)),
            ).fetchone()
        return row is not None

    def approval_exists(self, approval_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM coordination_records WHERE approval_id=?",
                (str(approval_id),),
            ).fetchone()
        return row is not None

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
        max_parent_cad: Decimal,
        max_total_cad: Decimal,
        max_concurrent_parents: int,
    ) -> CoordinationReceipt:
        """Atomically consume the nonce AND reserve exposure in ONE transaction.

        Capacity checks (CAD ceilings) are enforced inside the same
        transaction, so a rejected reservation leaves no partial state.
        """
        approval_id = str(approval_id).strip()
        nonce = str(nonce).strip()
        child_id = str(child_id).strip()
        parent_id = str(parent_id).strip()
        if not approval_id or not nonce or not child_id or not parent_id:
            raise PilotCoordinationError("approval_id, nonce, child_id, parent_id required")
        try:
            proposed = self._money(proposed_child_cad, "proposed_child_cad")
            fees = self._money(estimated_fees_cad, "estimated_fees_cad")
        except PilotCoordinationError as exc:
            return CoordinationReceipt(False, f"COORDINATION_INVALID_AMOUNT:{exc}", approval_id, nonce, child_id, "0.00", "")
        if proposed <= 0:
            return CoordinationReceipt(False, "COORDINATION_NONPOSITIVE", approval_id, nonce, child_id, "0.00", "")
        reserve_amount = proposed + fees
        if reserve_amount <= 0:
            return CoordinationReceipt(False, "COORDINATION_NONPOSITIVE", approval_id, nonce, child_id, "0.00", "")

        transaction_id = self._new_transaction_id()
        created_at = self._now_iso()

        try:
            with self._transaction() as conn:
                # -- replay / duplicate checks (inside the write transaction) --
                existing_nonce = conn.execute(
                    "SELECT approval_id FROM coordination_records WHERE issuer_id=? AND nonce=? AND state!='ROLLED_BACK'",
                    (str(issuer_id), nonce),
                ).fetchone()
                if existing_nonce is not None:
                    raise PilotCoordinationReplayError(
                        f"nonce already consumed: issuer={issuer_id} nonce={nonce} approval={existing_nonce['approval_id']}"
                    )
                existing_approval = conn.execute(
                    "SELECT 1 FROM coordination_records WHERE approval_id=?",
                    (approval_id,),
                ).fetchone()
                if existing_approval is not None:
                    raise PilotCoordinationReplayError(f"approval_id already used: {approval_id}")
                existing_child = conn.execute(
                    "SELECT 1 FROM exposure_reservations WHERE child_id=? AND state IN ('OPEN','COMMITTED')",
                    (child_id,),
                ).fetchone()
                if existing_child is not None:
                    return CoordinationReceipt(
                        False, "COORDINATION_DUPLICATE_CHILD_RESERVATION",
                        approval_id, nonce, child_id, "0.00", transaction_id,
                    )

                # -- capacity checks (all inside the same transaction) --
                rows = conn.execute(
                    "SELECT parent_id, reserved_cad FROM exposure_reservations WHERE state IN ('OPEN','COMMITTED')"
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

                if max_parent_cad is not None and projected_parent > max_parent_cad:
                    return CoordinationReceipt(
                        False, "COORDINATION_PARENT_EXPOSURE_CEILING",
                        approval_id, nonce, child_id, str(reserve_amount), transaction_id,
                    )
                if projected_count > max_concurrent_parents:
                    return CoordinationReceipt(
                        False, "COORDINATION_CONCURRENT_PARENT_CEILING",
                        approval_id, nonce, child_id, str(reserve_amount), transaction_id,
                    )
                if projected_total > max_total_cad:
                    return CoordinationReceipt(
                        False, "COORDINATION_TOTAL_EXPOSURE_CEILING",
                        approval_id, nonce, child_id, str(reserve_amount), transaction_id,
                    )

                # -- record nonce consumption + reservation + audit in ONE transaction --
                conn.execute(
                    "INSERT INTO coordination_records "
                    "(approval_id, nonce, issuer_id, candidate_sha, child_id, parent_id, reserved_cad, state, created_at, committed_at) "
                    "VALUES(?,?,?,?,?,?,?,'COMMITTED',?,?)",
                    (
                        approval_id, nonce, str(issuer_id), str(candidate_sha),
                        child_id, parent_id, str(reserve_amount), created_at, created_at,
                    ),
                )
                conn.execute(
                    "INSERT INTO exposure_reservations (child_id, parent_id, reserved_cad, fees_cad, state, created_at) "
                    "VALUES(?,?,?,?, 'OPEN', ?)",
                    (child_id, parent_id, str(reserve_amount), str(fees), created_at),
                )
                conn.execute(
                    "INSERT INTO coordination_audit (approval_id, event, details, recorded_at) "
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
            return CoordinationReceipt(False, f"COORDINATION_ERROR:{exc}", approval_id, nonce, child_id, "0.00", transaction_id)
        except sqlite3.Error as exc:
            # Any SQLite error (including transaction errors) → denial, no partial state.
            return CoordinationReceipt(False, f"COORDINATION_SQLITE_ERROR:{exc}", approval_id, nonce, child_id, "0.00", transaction_id)

    def release_reservation(self, *, child_id: str, reason: str, release_nonce: bool = False) -> bool:
        """Release an OPEN reservation. The nonce is NEVER reusable by default."""
        child_id = str(child_id).strip()
        try:
            with self._transaction() as conn:
                row = conn.execute(
                    "SELECT child_id, state FROM exposure_reservations WHERE child_id=?",
                    (child_id,),
                ).fetchone()
                if row is None or row["state"] != "OPEN":
                    return False
                conn.execute(
                    "UPDATE exposure_reservations SET state='RELEASED' WHERE child_id=? AND state='OPEN'",
                    (child_id,),
                )
                conn.execute(
                    "INSERT INTO coordination_audit (approval_id, event, details, recorded_at) VALUES(?,?,?,?)",
                    (
                        child_id,
                        "RESERVATION_RELEASED",
                        json.dumps({"child_id": child_id, "reason": str(reason), "release_nonce": bool(release_nonce)}, sort_keys=True),
                        self._now_iso(),
                    ),
                )
                if release_nonce:
                    # ONLY for explicit reconciliation; does not make the nonce
                    # reusable (nonce uniqueness is enforced via coordination_records).
                    conn.execute(
                        "UPDATE coordination_records SET state='ROLLED_BACK' WHERE child_id=? AND state='COMMITTED'",
                        (child_id,),
                    )
                return True
        except PilotCoordinationError:
            return False
        except sqlite3.Error:
            return False

    def commit_reservation(self, *, child_id: str) -> bool:
        """Transition an OPEN reservation to COMMITTED."""
        child_id = str(child_id).strip()
        try:
            with self._transaction() as conn:
                cur = conn.execute(
                    "UPDATE exposure_reservations SET state='COMMITTED' WHERE child_id=? AND state='OPEN'",
                    (child_id,),
                )
                if cur.rowcount != 1:
                    return False
                conn.execute(
                    "INSERT INTO coordination_audit (approval_id, event, details, recorded_at) VALUES(?,?,?,?)",
                    (child_id, "RESERVATION_COMMITTED", json.dumps({"child_id": child_id}, sort_keys=True), self._now_iso()),
                )
                return True
        except PilotCoordinationError:
            return False
        except sqlite3.Error:
            return False

    def reservation_state(self, *, child_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT state FROM exposure_reservations WHERE child_id=?",
                (str(child_id).strip(),),
            ).fetchone()
        return str(row["state"]) if row is not None else None

    def tamper_for_test(self, sql: str, params: tuple = ()) -> None:
        """TEST-ONLY helper: execute raw SQL in its own transaction.

        Used by tests to simulate partial-failure / desync conditions that
        must NEVER occur in production (e.g. deleting a reservation while
        leaving the coordination record). This must not be called by
        production code.
        """
        conn = self._connect()
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(sql, params)
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise

    def audit_tail(self, *, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT approval_id, event, details, recorded_at FROM coordination_audit ORDER BY id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [dict(row) for row in rows]

    def verify_consistency(self) -> dict[str, Any]:
        """Reconcile coordination_records against exposure_reservations.

        Detects:
        - a COMMITTED coordination record with no matching OPEN/COMMITTED
          reservation (journal desync);
        - an OPEN/COMMITTED reservation with no matching COMMITTED coordination
          record (orphan reservation).
        """
        problems: list[str] = []
        with self._connect() as conn:
            committed = conn.execute(
                "SELECT approval_id, child_id FROM coordination_records WHERE state='COMMITTED'"
            ).fetchall()
            by_child = {str(r["child_id"]): str(r["approval_id"]) for r in committed}
            for row in committed:
                child = str(row["child_id"])
                res = conn.execute(
                    "SELECT state FROM exposure_reservations WHERE child_id=? AND state IN ('OPEN','COMMITTED')",
                    (child,),
                ).fetchone()
                if res is None:
                    problems.append(f"JOURNAL_DESYNC: approval={row['approval_id']} child={child} has no live reservation")
            reservations = conn.execute(
                "SELECT child_id FROM exposure_reservations WHERE state IN ('OPEN','COMMITTED')"
            ).fetchall()
            for row in reservations:
                child = str(row["child_id"])
                if child not in by_child:
                    problems.append(f"ORPHAN_RESERVATION: child={child} has no COMMITTED coordination record")
        return {"consistent": not problems, "problems": problems}

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None
