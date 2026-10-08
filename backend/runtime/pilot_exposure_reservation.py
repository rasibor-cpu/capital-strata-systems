"""Atomic reservation ledger for the governed CSS pilot exposure envelope.

This module is pre-execution infrastructure only. It does not place orders,
arm brokers, or grant execution authority. It serializes reservations so two
concurrent child-order requests cannot both observe the same free capacity and
oversubscribe the CAD 20 parent / CAD 40 portfolio ceilings.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterator

from backend.config.order_limit_config import (
    CanonicalOrderLimitConfig,
    DEFAULT_ORDER_LIMIT_CONFIG,
)

_CENT = Decimal("0.01")


class PilotReservationError(RuntimeError):
    pass


def _money(raw: Any, name: str) -> Decimal:
    if isinstance(raw, bool):
        raise PilotReservationError(f"{name}: boolean not permitted")
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PilotReservationError(f"{name}: invalid amount") from exc
    if not value.is_finite() or value < 0 or value != value.quantize(_CENT):
        raise PilotReservationError(f"{name}: amount must be finite, nonnegative whole cents")
    return value


@dataclass(frozen=True)
class PilotReservationDecision:
    approved: bool
    reason: str
    parent_id: str
    child_id: str
    reserved_child_cad: Decimal
    projected_parent_cad: Decimal
    projected_total_cad: Decimal
    projected_parent_count: int


class PilotExposureReservationLedger:
    """SQLite-backed atomic reservation ledger.

    SQLite BEGIN IMMEDIATE provides a cross-platform writer lock. Reservations
    are durable across process restarts and are uniquely keyed by child_id to
    prevent duplicate reservation/replay.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        config: CanonicalOrderLimitConfig = DEFAULT_ORDER_LIMIT_CONFIG,
    ) -> None:
        if not isinstance(config, CanonicalOrderLimitConfig):
            raise PilotReservationError("canonical config required")
        config.validate()
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.config = config
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pilot_reservations (
                    child_id TEXT PRIMARY KEY,
                    parent_id TEXT NOT NULL,
                    reserved_cad TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('OPEN','RELEASED','COMMITTED'))
                )
                """
            )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        return conn

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise
        finally:
            conn.close()

    def reserve(
        self,
        *,
        parent_id: str,
        child_id: str,
        proposed_child_cad: Any,
        estimated_fees_cad: Any = Decimal("0.00"),
    ) -> PilotReservationDecision:
        try:
            parent = str(parent_id).strip()
            child = str(child_id).strip()
            if not parent or not child:
                raise PilotReservationError("parent_id and child_id required")
            proposed = _money(proposed_child_cad, "proposed_child_cad")
            fees = _money(estimated_fees_cad, "estimated_fees_cad")
            if proposed <= 0:
                raise PilotReservationError("proposed child must be positive")
            reserve_amount = proposed + fees

            with self._transaction() as conn:
                existing = conn.execute(
                    "SELECT child_id FROM pilot_reservations WHERE child_id = ?",
                    (child,),
                ).fetchone()
                if existing is not None:
                    return PilotReservationDecision(
                        False, "PILOT_DUPLICATE_CHILD_RESERVATION", parent, child,
                        Decimal("0.00"), Decimal("0.00"), Decimal("0.00"), 0,
                    )

                rows = conn.execute(
                    "SELECT parent_id, reserved_cad, state FROM pilot_reservations "
                    "WHERE state IN ('OPEN','COMMITTED')"
                ).fetchall()

                parent_totals: dict[str, Decimal] = {}
                total = Decimal("0.00")
                for row in rows:
                    amount = _money(row["reserved_cad"], "stored_reserved_cad")
                    pid = str(row["parent_id"])
                    parent_totals[pid] = parent_totals.get(pid, Decimal("0.00")) + amount
                    total += amount

                existing_parent = parent_totals.get(parent, Decimal("0.00"))
                projected_parent = existing_parent + reserve_amount
                projected_total = total + reserve_amount
                projected_count = len(parent_totals) + (0 if parent in parent_totals else 1)

                if projected_parent > self.config.live_pilot_max_position_cad:
                    return PilotReservationDecision(
                        False, "PILOT_PARENT_EXPOSURE_CEILING", parent, child,
                        reserve_amount, projected_parent, projected_total, projected_count,
                    )
                if projected_count > self.config.live_pilot_max_concurrent_positions:
                    return PilotReservationDecision(
                        False, "PILOT_CONCURRENT_EXPOSURE_CEILING", parent, child,
                        reserve_amount, projected_parent, projected_total, projected_count,
                    )
                if projected_total > self.config.live_pilot_max_total_cad:
                    return PilotReservationDecision(
                        False, "PILOT_TOTAL_EXPOSURE_CEILING", parent, child,
                        reserve_amount, projected_parent, projected_total, projected_count,
                    )

                conn.execute(
                    "INSERT INTO pilot_reservations(child_id,parent_id,reserved_cad,state) "
                    "VALUES(?,?,?,'OPEN')",
                    (child, parent, str(reserve_amount)),
                )
                return PilotReservationDecision(
                    True, "PILOT_RESERVATION_CREATED", parent, child,
                    reserve_amount, projected_parent, projected_total, projected_count,
                )
        except Exception:
            return PilotReservationDecision(
                False, "PILOT_RESERVATION_EVALUATION_ERROR",
                str(parent_id).strip() if parent_id is not None else "",
                str(child_id).strip() if child_id is not None else "",
                Decimal("0.00"), Decimal("0.00"), Decimal("0.00"), 0,
            )

    def transition(self, child_id: str, *, from_state: str, to_state: str) -> bool:
        if from_state not in {"OPEN", "COMMITTED"} or to_state not in {"COMMITTED", "RELEASED"}:
            return False
        try:
            with self._transaction() as conn:
                cur = conn.execute(
                    "UPDATE pilot_reservations SET state=? WHERE child_id=? AND state=?",
                    (to_state, str(child_id).strip(), from_state),
                )
                return cur.rowcount == 1
        except Exception:
            return False

    def snapshot(self) -> list[dict[str, str]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT child_id,parent_id,reserved_cad,state FROM pilot_reservations "
                "ORDER BY parent_id,child_id"
            ).fetchall()
        return [dict(row) for row in rows]


__all__ = [
    "PilotExposureReservationLedger",
    "PilotReservationDecision",
    "PilotReservationError",
]
