from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List


@dataclass
class InstrumentSpec:
    """
    Normalized instrument specification so all asset classes can be
    evaluated through one PnL engine without multiplier confusion.
    """
    symbol: str
    asset_class: str  # "CRYPTO", "FX", "FUTURES", "OPTIONS", "EQUITY"
    multiplier: float = 1.0
    tick_size: float = 0.0
    contract_size: float = 1.0
    quote_currency: str = "USD"


@dataclass
class ExecutionCost:
    """
    Execution cost components expressed in account currency.
    """
    spread: float = 0.0
    slippage: float = 0.0
    fees: float = 0.0

    @property
    def total(self) -> float:
        return float(self.spread + self.slippage + self.fees)


@dataclass
class Position:
    """
    Minimal normalized position model for PnL computation.
    """
    symbol: str
    side: str  # "LONG" or "SHORT"
    entry_price: float
    current_price: float
    quantity: float
    instrument_spec: InstrumentSpec

    entry_cost: ExecutionCost
    estimated_exit_cost: ExecutionCost

    realized_pnl: float = 0.0
    is_open: bool = True


@dataclass
class PositionPnL:
    gross_unrealized: float
    estimated_exit_cost: float
    net_unrealized: float


@dataclass
class PortfolioSnapshot:
    starting_equity: float
    total_net_realized: float
    total_gross_unrealized: float
    total_estimated_exit_cost: float
    total_net_unrealized: float
    live_equity: float
    open_positions: int
    closed_positions: int


def _normalize_side(side: str) -> str:
    s = str(side).strip().upper()
    if s not in {"LONG", "SHORT"}:
        raise ValueError(f"Unsupported side: {side!r}")
    return s


def _direction_multiplier(side: str) -> int:
    return 1 if _normalize_side(side) == "LONG" else -1


def _safe_multiplier(spec: InstrumentSpec) -> float:
    multiplier = float(spec.multiplier)
    if multiplier <= 0:
        raise ValueError(
            f"Invalid multiplier for {spec.symbol}: {spec.multiplier}"
        )
    return multiplier


def compute_gross_unrealized(position: Position) -> float:
    """
    Compute gross unrealized PnL before estimated exit costs.
    """
    direction = _direction_multiplier(position.side)
    price_diff = float(position.current_price) - float(position.entry_price)
    quantity = float(position.quantity)
    multiplier = _safe_multiplier(position.instrument_spec)

    return direction * price_diff * quantity * multiplier


def compute_estimated_exit_cost(position: Position) -> float:
    return float(position.estimated_exit_cost.total)


def compute_position_pnl(position: Position) -> PositionPnL:
    gross = compute_gross_unrealized(position)
    exit_cost = compute_estimated_exit_cost(position)
    net = gross - exit_cost

    return PositionPnL(
        gross_unrealized=gross,
        estimated_exit_cost=exit_cost,
        net_unrealized=net,
    )


def compute_portfolio_snapshot(
    positions: Iterable[Position],
    starting_equity: float,
) -> PortfolioSnapshot:

    total_net_realized = 0.0
    total_gross_unrealized = 0.0
    total_estimated_exit_cost = 0.0
    total_net_unrealized = 0.0

    open_positions = 0
    closed_positions = 0

    for pos in positions:

        if pos.is_open:
            pnl = compute_position_pnl(pos)

            total_gross_unrealized += pnl.gross_unrealized
            total_estimated_exit_cost += pnl.estimated_exit_cost
            total_net_unrealized += pnl.net_unrealized

            open_positions += 1

        else:
            total_net_realized += float(pos.realized_pnl)
            closed_positions += 1

    live_equity = (
        float(starting_equity)
        + total_net_realized
        + total_net_unrealized
    )

    snapshot = PortfolioSnapshot(
        starting_equity=float(starting_equity),
        total_net_realized=total_net_realized,
        total_gross_unrealized=total_gross_unrealized,
        total_estimated_exit_cost=total_estimated_exit_cost,
        total_net_unrealized=total_net_unrealized,
        live_equity=live_equity,
        open_positions=open_positions,
        closed_positions=closed_positions,
    )

    validate_portfolio_snapshot(snapshot)

    return snapshot


def validate_portfolio_snapshot(snapshot: PortfolioSnapshot) -> None:
    expected_live_equity = (
        snapshot.starting_equity
        + snapshot.total_net_realized
        + snapshot.total_net_unrealized
    )

    tolerance = 1e-9
    if abs(snapshot.live_equity - expected_live_equity) > tolerance:
        raise ValueError(
            "Portfolio snapshot validation failed: "
            f"live_equity={snapshot.live_equity}, "
            f"expected={expected_live_equity}"
        )


def summarize_open_positions(positions: Iterable[Position]) -> List[dict]:

    summaries: List[dict] = []

    for pos in positions:
        if not pos.is_open:
            continue

        pnl = compute_position_pnl(pos)

        summaries.append(
            {
                "symbol": pos.symbol,
                "asset_class": pos.instrument_spec.asset_class,
                "side": _normalize_side(pos.side),
                "entry_price": float(pos.entry_price),
                "current_price": float(pos.current_price),
                "quantity": float(pos.quantity),
                "multiplier": float(pos.instrument_spec.multiplier),
                "gross_unrealized": pnl.gross_unrealized,
                "estimated_exit_cost": pnl.estimated_exit_cost,
                "net_unrealized": pnl.net_unrealized,
            }
        )

    return summaries
