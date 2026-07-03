from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Optional, Tuple

from engine.domain.executions import ExecutionReport
from engine.ledger.ledger_models import PnLSnapshot
from engine.ledger.ledger_store import LedgerStore


ScopeKey = Tuple[str, str, str, str]  # company, branch, dept, user
PosKey = Tuple[str, str, str, str, str, str]  # scope + symbol + currency


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class PositionState:
    """
    V1 position state (average cost).
    Supports all currencies by treating currency as an opaque code string.
    """
    symbol: str
    currency: str
    qty: Decimal = Decimal("0")
    avg_cost: Decimal = Decimal("0")  # per-unit
    realized_pnl: Decimal = Decimal("0")


class PnLEngine:
    """
    Rolling P&L engine (v1).

    - Updates average-cost position state from ExecutionReport
    - Computes realized P&L on SELL
    - Computes unrealized P&L from provided market prices
    - Stores snapshots into LedgerStore
    - Optionally nets realized exit P&L through an execution cost engine
    """

    def __init__(self, store: LedgerStore, cost_engine=None):
        self.store = store
        self.cost_engine = cost_engine
        self._state: Dict[PosKey, PositionState] = {}

    # ─────────────────────────────
    # Public API
    # ─────────────────────────────
    def update_from_execution(self, r: ExecutionReport) -> None:
        """
        Update position state and realized P&L from one execution.
        """
        posting_ccy = (r.settlement_currency or r.currency) or "NA"
        side = (r.side or "").upper()
        symbol = r.symbol

        scope = self._scope_key(r)
        key: PosKey = (*scope, symbol, posting_ccy)

        st = self._state.get(key)
        if st is None:
            st = PositionState(symbol=symbol, currency=posting_ccy)
            self._state[key] = st

        qty = Decimal(str(r.filled_qty or 0.0))
        price = Decimal(str(r.fill_price or 0.0))

        if qty <= 0:
            return

        if side == "BUY":
            # New avg cost = (old_cost + new_cost) / new_qty_total
            old_value = st.qty * st.avg_cost
            new_value = qty * price
            new_qty_total = st.qty + qty

            if new_qty_total > 0:
                st.avg_cost = (old_value + new_value) / new_qty_total
                st.qty = new_qty_total

        elif side == "SELL":
            # Realized P&L = (sell_price - avg_cost) * sold_qty
            sold_qty = qty

            # If selling more than held, clamp to held (v1 safety)
            if sold_qty > st.qty:
                sold_qty = st.qty

            realized = (price - st.avg_cost) * sold_qty
            realized = self._apply_exit_costs(
                symbol=symbol,
                notional=abs(sold_qty * price),
                realized=realized,
            )
            st.realized_pnl += realized
            st.qty -= sold_qty

            # If position fully closed, keep avg_cost but qty = 0
            if st.qty == 0:
                # avg_cost remains last known cost basis (harmless)
                pass
        else:
            return

    def snapshot(
        self,
        *,
        as_of: Optional[datetime] = None,
        market_prices: Optional[Dict[str, float]] = None,
        company_id: Optional[str] = None,
        branch_id: Optional[str] = None,
        department_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        """
        Create PnLSnapshot records for matching scopes.

        market_prices: dict[symbol] -> latest price (float).
        Unrealized P&L is computed only if price is provided.
        """
        as_of = as_of or _utc_now()
        market_prices = market_prices or {}

        for key, st in self._state.items():
            comp, br, dept, usr, sym, ccy = key

            if company_id is not None and comp != (company_id or "COMPANY:NA"):
                continue
            if branch_id is not None and br != (branch_id or "BRANCH:NA"):
                continue
            if department_id is not None and dept != (department_id or "DEPT:NA"):
                continue
            if user_id is not None and usr != (user_id or "USER:NA"):
                continue

            px = market_prices.get(sym)
            unreal = Decimal("0")
            if px is not None:
                px_d = Decimal(str(px))
                unreal = (px_d - st.avg_cost) * st.qty

            snap = PnLSnapshot(
                as_of=as_of,
                symbol=sym,
                currency=ccy,
                realized_pnl=st.realized_pnl,
                unrealized_pnl=unreal,
                company_id=comp if comp != "COMPANY:NA" else None,
                branch_id=br if br != "BRANCH:NA" else None,
                department_id=dept if dept != "DEPT:NA" else None,
                user_id=usr if usr != "USER:NA" else None,
                meta={
                    "qty": str(st.qty),
                    "avg_cost": str(st.avg_cost),
                },
            )

            self.store.add_pnl_snapshot(snap)

    # ─────────────────────────────
    # Helpers
    # ─────────────────────────────
    def _scope_key(self, r: ExecutionReport) -> ScopeKey:
        return (
            r.company_id or "COMPANY:NA",
            r.branch_id or "BRANCH:NA",
            r.department_id or "DEPT:NA",
            r.user_id or "USER:NA",
        )

    def _apply_exit_costs(
        self,
        *,
        symbol: str,
        notional: Decimal,
        realized: Decimal,
    ) -> Decimal:
        if self.cost_engine is None or notional <= 0:
            return realized

        raw_pnl = float(realized)
        adjusted_pnl = self.cost_engine.apply_costs(
            instrument=symbol,
            notional=float(notional),
            raw_pnl=raw_pnl,
        )
        # Cost engines are currently float-based; preserve the gross Decimal
        # realized value and subtract only the boundary-converted cost delta.
        cost_delta = Decimal(str(raw_pnl)) - Decimal(str(adjusted_pnl))

        return realized - cost_delta
