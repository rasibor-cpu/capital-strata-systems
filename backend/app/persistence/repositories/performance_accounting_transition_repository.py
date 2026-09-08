from __future__ import annotations

from typing import Any

from backend.app.persistence.repositories.base_repository import (
    BaseRepository,
)
from backend.commercialization.performance_accounting import (
    PerformanceAccountingTransition,
)


class PerformanceAccountingTransitionRepository(BaseRepository):
    """
    Persistence boundary for immutable COM-002C accounting transitions.

    Deliberately exposes no update or delete method.

    Each attributable trade may produce one authoritative accounting
    transition. Duplicate insertion for the same trade_id fails at the
    database primary-key constraint rather than rewriting accounting
    history.
    """

    def create_transition(
        self,
        transition: PerformanceAccountingTransition,
    ) -> None:
        previous_state = transition.previous_state
        new_state = transition.new_state

        self.execute(
            """
            INSERT INTO performance_accounting_transitions (
                trade_id,
                currency,
                previous_cumulative_attributable_pnl,
                previous_high_water_mark,
                previous_loss_carryforward,
                attributable_realized_pnl,
                recovered_loss,
                new_economic_gain,
                new_cumulative_attributable_pnl,
                new_high_water_mark,
                new_loss_carryforward
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                transition.trade_id,
                new_state.currency,
                str(
                    previous_state.cumulative_attributable_pnl
                ),
                str(previous_state.high_water_mark),
                str(previous_state.loss_carryforward),
                str(transition.attributable_realized_pnl),
                str(transition.recovered_loss),
                str(transition.new_economic_gain),
                str(
                    new_state.cumulative_attributable_pnl
                ),
                str(new_state.high_water_mark),
                str(new_state.loss_carryforward),
            ),
        )

    def get_by_trade_id(
        self,
        trade_id: str,
    ) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT *
            FROM performance_accounting_transitions
            WHERE trade_id = ?
            """,
            (trade_id,),
        )

        if row is None:
            return None

        return dict(row)

    def list_all(
        self,
    ) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT *
            FROM performance_accounting_transitions
            ORDER BY created_at ASC, trade_id ASC
            """
        )

        return [dict(row) for row in rows]
