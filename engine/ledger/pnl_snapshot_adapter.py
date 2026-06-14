from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Mapping

from engine.ledger import CANONICAL_PNL_SOURCE
from engine.ledger.ledger_models import PnLSnapshot
from engine.ledger.ledger_store import LedgerStore


ZERO = Decimal("0")


@dataclass(frozen=True)
class CanonicalPnLSnapshotContract:
    """
    Ledger-backed PnL contract for runtime and dashboard consumers.

    Decimal values are preserved inside the contract. Use to_runtime_dict()
    when crossing into dashboard, reporting, API, or other presentation layers.
    """

    realized_pnl: Decimal = ZERO
    unrealized_pnl: Decimal = ZERO
    net_pnl: Decimal = ZERO
    equity: Decimal = ZERO
    peak_equity: Decimal = ZERO
    current_drawdown: Decimal = ZERO
    max_drawdown: Decimal = ZERO
    asset_realized_pnl: dict[str, Decimal] = field(default_factory=dict)
    asset_unrealized_pnl: dict[str, Decimal] = field(default_factory=dict)
    open_positions: int = 0
    closed_positions: int = 0
    source: str = CANONICAL_PNL_SOURCE

    def to_runtime_dict(self) -> dict[str, object]:
        """
        Return dashboard-safe values without exposing Decimal internals.
        """

        return {
            "realized_pnl": float(self.realized_pnl),
            "unrealized_pnl": float(self.unrealized_pnl),
            "net_pnl": float(self.net_pnl),
            "equity": float(self.equity),
            "peak_equity": float(self.peak_equity),
            "current_drawdown": float(self.current_drawdown),
            "max_drawdown": float(self.max_drawdown),
            "asset_realized_pnl": {
                key: float(value)
                for key, value in self.asset_realized_pnl.items()
            },
            "asset_unrealized_pnl": {
                key: float(value)
                for key, value in self.asset_unrealized_pnl.items()
            },
            "open_positions": int(self.open_positions),
            "closed_positions": int(self.closed_positions),
            "source": self.source,
        }


def build_pnl_snapshot_contract(
    store: LedgerStore,
    *,
    starting_equity: Decimal | float | int | str = ZERO,
    peak_equity: Decimal | float | int | str | None = None,
    max_drawdown: Decimal | float | int | str | None = None,
    asset_class_by_symbol: Mapping[str, str] | None = None,
    company_id: str | None = None,
    branch_id: str | None = None,
    department_id: str | None = None,
    user_id: str | None = None,
) -> CanonicalPnLSnapshotContract:
    """
    Aggregate latest ledger PnL snapshots into a normalized runtime contract.

    The adapter reads only LedgerStore/PnLSnapshot state produced by the
    canonical PnLEngine path. It does not fetch broker data, mutate runtime
    state, or participate in trade decisions.
    """

    snapshots = store.get_latest_pnl(
        company_id=company_id,
        branch_id=branch_id,
        department_id=department_id,
        user_id=user_id,
    )
    latest_snapshots = _latest_snapshot_by_position_key(snapshots)
    asset_lookup = asset_class_by_symbol or {}

    realized = ZERO
    unrealized = ZERO
    asset_realized: dict[str, Decimal] = {}
    asset_unrealized: dict[str, Decimal] = {}
    open_positions = 0
    closed_positions = 0

    for snapshot in latest_snapshots:
        snap_realized = _to_decimal(snapshot.realized_pnl)
        snap_unrealized = _to_decimal(snapshot.unrealized_pnl)
        realized += snap_realized
        unrealized += snap_unrealized

        asset_class = _asset_class_for_snapshot(snapshot, asset_lookup)
        asset_realized[asset_class] = (
            asset_realized.get(asset_class, ZERO) + snap_realized
        )
        asset_unrealized[asset_class] = (
            asset_unrealized.get(asset_class, ZERO) + snap_unrealized
        )

        if _snapshot_open_quantity(snapshot) != ZERO:
            open_positions += 1
        else:
            closed_positions += 1

    net_pnl = realized + unrealized
    equity = _to_decimal(starting_equity) + net_pnl

    resolved_peak = (
        max(equity, _to_decimal(peak_equity))
        if peak_equity is not None
        else equity
    )
    current_drawdown = _drawdown(resolved_peak, equity)
    resolved_max_drawdown = (
        max(current_drawdown, _to_decimal(max_drawdown))
        if max_drawdown is not None
        else current_drawdown
    )

    return CanonicalPnLSnapshotContract(
        realized_pnl=realized,
        unrealized_pnl=unrealized,
        net_pnl=net_pnl,
        equity=equity,
        peak_equity=resolved_peak,
        current_drawdown=current_drawdown,
        max_drawdown=resolved_max_drawdown,
        asset_realized_pnl=asset_realized,
        asset_unrealized_pnl=asset_unrealized,
        open_positions=open_positions,
        closed_positions=closed_positions,
        source=CANONICAL_PNL_SOURCE,
    )


def _latest_snapshot_by_position_key(
    snapshots: list[PnLSnapshot],
) -> list[PnLSnapshot]:
    latest: dict[tuple[str | None, ...], PnLSnapshot] = {}

    for snapshot in snapshots:
        key = (
            snapshot.company_id,
            snapshot.branch_id,
            snapshot.department_id,
            snapshot.user_id,
            snapshot.symbol,
            snapshot.currency,
        )
        current = latest.get(key)
        if current is None or snapshot.as_of > current.as_of:
            latest[key] = snapshot

    return list(latest.values())


def _asset_class_for_snapshot(
    snapshot: PnLSnapshot,
    asset_lookup: Mapping[str, str],
) -> str:
    asset_class = asset_lookup.get(snapshot.symbol, "UNKNOWN")
    normalized = str(asset_class or "UNKNOWN").strip().upper()
    return normalized or "UNKNOWN"


def _snapshot_open_quantity(snapshot: PnLSnapshot) -> Decimal:
    return _to_decimal(snapshot.meta.get("qty", ZERO))


def _drawdown(peak_equity: Decimal, equity: Decimal) -> Decimal:
    if peak_equity <= ZERO:
        return ZERO
    drawdown = (peak_equity - equity) / peak_equity
    return max(drawdown, ZERO)


def _to_decimal(value: Decimal | float | int | str | None) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))
