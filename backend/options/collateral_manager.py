from __future__ import annotations

from dataclasses import dataclass


COLLATERAL_SHARES = "SHARES"
COLLATERAL_CASH = "CASH"


class CollateralManagerError(ValueError):
    """Raised when paper collateral operations are invalid."""


@dataclass(frozen=True)
class CollateralRecord:
    position_id: str
    collateral_type: str
    amount_reserved: float
    amount_released: float = 0.0
    reserved: bool = True
    released: bool = False

    def to_dict(self) -> dict[str, float | str | bool]:
        return {
            "position_id": self.position_id,
            "collateral_type": self.collateral_type,
            "amount_reserved": self.amount_reserved,
            "amount_released": self.amount_released,
            "reserved": self.reserved,
            "released": self.released,
        }


class CollateralManager:
    def __init__(self) -> None:
        self._records: dict[str, CollateralRecord] = {}

    def reserve_shares(self, *, position_id: str, shares: float) -> CollateralRecord:
        return self._reserve(position_id=position_id, collateral_type=COLLATERAL_SHARES, amount=shares)

    def reserve_cash(self, *, position_id: str, cash: float) -> CollateralRecord:
        return self._reserve(position_id=position_id, collateral_type=COLLATERAL_CASH, amount=cash)

    def release(self, *, position_id: str) -> CollateralRecord:
        key = _key(position_id)
        record = self._records.get(key)
        if record is None:
            raise CollateralManagerError(f"No reserved collateral for {position_id}")
        if record.released:
            raise CollateralManagerError(f"Collateral already released for {position_id}")
        released = CollateralRecord(
            position_id=record.position_id,
            collateral_type=record.collateral_type,
            amount_reserved=record.amount_reserved,
            amount_released=record.amount_reserved,
            reserved=False,
            released=True,
        )
        self._records[key] = released
        return released

    def get(self, position_id: str) -> CollateralRecord:
        key = _key(position_id)
        if key not in self._records:
            raise CollateralManagerError(f"No collateral record for {position_id}")
        return self._records[key]

    def _reserve(self, *, position_id: str, collateral_type: str, amount: float) -> CollateralRecord:
        key = _key(position_id)
        if key in self._records and not self._records[key].released:
            raise CollateralManagerError(f"Collateral already reserved for {position_id}")
        try:
            numeric = float(amount)
        except (TypeError, ValueError) as exc:
            raise CollateralManagerError("Collateral amount must be numeric") from exc
        if numeric <= 0.0:
            raise CollateralManagerError("Collateral amount must be positive")
        record = CollateralRecord(key, collateral_type, round(numeric, 6))
        self._records[key] = record
        return record


def _key(position_id: str) -> str:
    key = str(position_id or "").strip()
    if not key:
        raise CollateralManagerError("position_id is required")
    return key


__all__ = [
    "COLLATERAL_CASH",
    "COLLATERAL_SHARES",
    "CollateralManager",
    "CollateralManagerError",
    "CollateralRecord",
]
