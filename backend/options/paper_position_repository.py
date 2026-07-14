from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
import json
from typing import Any, Mapping


SAFE_FLAGS = {
    "advisory_only": True,
    "execution_allowed": False,
    "live_trading_blocked": True,
    "broker_execution_armed": False,
}


class PaperPositionRepositoryError(ValueError):
    """Fail-closed repository error for paper income positions."""


@dataclass(frozen=True)
class PaperIncomeEvent:
    event_id: str
    event_type: str
    timestamp: str
    state: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _json_safe(asdict(self))


@dataclass(frozen=True)
class PaperIncomePosition:
    position_id: str
    strategy_id: str
    underlying: str
    option_symbol: str
    strategy_type: str
    quantity: float
    contracts: int
    entry_date: str
    expiry: str
    strike: float
    premium_received: float
    premium_realized: float
    premium_remaining: float
    collateral_reserved: float
    collateral_released: float
    current_state: str
    assignment_status: str
    lifecycle_events: list[dict[str, Any]]
    timestamps: dict[str, str]
    advisory_flags: dict[str, bool] = field(default_factory=lambda: dict(SAFE_FLAGS))

    def to_dict(self) -> dict[str, Any]:
        return _json_safe(asdict(self))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PaperIncomePosition":
        try:
            payload = dict(data)
            payload["lifecycle_events"] = list(payload.get("lifecycle_events", []))
            payload["timestamps"] = dict(payload.get("timestamps", {}))
            payload["advisory_flags"] = {**SAFE_FLAGS, **dict(payload.get("advisory_flags", {}))}
            position = cls(**payload)
        except TypeError as exc:
            raise PaperPositionRepositoryError("Malformed paper income position") from exc
        _validate_position(position)
        return position


class PaperPositionRepository:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else None
        self._positions: dict[str, PaperIncomePosition] = {}
        if self.path is not None and self.path.exists():
            self.load()

    def add(self, position: PaperIncomePosition) -> PaperIncomePosition:
        _validate_position(position)
        if position.position_id in self._positions:
            raise PaperPositionRepositoryError(f"Duplicate position: {position.position_id}")
        self._positions[position.position_id] = position
        self._persist()
        return position

    def get(self, position_id: str) -> PaperIncomePosition:
        key = str(position_id or "").strip()
        if key not in self._positions:
            raise PaperPositionRepositoryError(f"Unknown position: {position_id}")
        return self._positions[key]

    def update(self, position: PaperIncomePosition) -> PaperIncomePosition:
        _validate_position(position)
        if position.position_id not in self._positions:
            raise PaperPositionRepositoryError(f"Unknown position: {position.position_id}")
        self._positions[position.position_id] = position
        self._persist()
        return position

    def all(self) -> list[PaperIncomePosition]:
        return [self._positions[key] for key in sorted(self._positions)]

    def load(self) -> None:
        if self.path is None:
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            rows = raw.get("positions")
            if not isinstance(rows, list):
                raise PaperPositionRepositoryError("Repository positions must be a list")
            loaded: dict[str, PaperIncomePosition] = {}
            for row in rows:
                position = PaperIncomePosition.from_dict(row)
                if position.position_id in loaded:
                    raise PaperPositionRepositoryError(f"Duplicate position in repository: {position.position_id}")
                loaded[position.position_id] = position
        except json.JSONDecodeError as exc:
            raise PaperPositionRepositoryError("Repository corruption detected") from exc
        self._positions = loaded

    def _persist(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"positions": [position.to_dict() for position in self.all()]}
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _validate_position(position: PaperIncomePosition) -> None:
    required = (position.position_id, position.strategy_id, position.underlying, position.option_symbol, position.strategy_type)
    if any(not str(item or "").strip() for item in required):
        raise PaperPositionRepositoryError("Paper income position is missing required identity fields")
    if position.premium_received < 0 or position.premium_realized < 0 or position.premium_remaining < 0:
        raise PaperPositionRepositoryError("Paper income premium cannot be negative")
    if position.collateral_reserved < 0 or position.collateral_released < 0:
        raise PaperPositionRepositoryError("Paper income collateral cannot be negative")
    if position.collateral_released > position.collateral_reserved:
        raise PaperPositionRepositoryError("Released collateral cannot exceed reserved collateral")
    _timestamp(position.entry_date, "entry_date")
    _timestamp(position.expiry, "expiry")
    for field in ("created_at", "updated_at"):
        _timestamp(dict(position.timestamps or {}).get(field), field)
    flags = {**SAFE_FLAGS, **dict(position.advisory_flags or {})}
    if flags != SAFE_FLAGS:
        raise PaperPositionRepositoryError("Paper income advisory flags are not safe")
    if not isinstance(position.lifecycle_events, list):
        raise PaperPositionRepositoryError("Paper income lifecycle events must be a list")


def _timestamp(value: Any, field: str) -> None:
    try:
        datetime.fromisoformat(str(value or "").strip())
    except (TypeError, ValueError) as exc:
        raise PaperPositionRepositoryError(f"Invalid paper income timestamp: {field}") from exc


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


__all__ = [
    "PaperIncomeEvent",
    "PaperIncomePosition",
    "PaperPositionRepository",
    "PaperPositionRepositoryError",
    "SAFE_FLAGS",
]
