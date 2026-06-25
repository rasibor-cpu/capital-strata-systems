from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Iterable, Mapping


class StrategyMemoryRepositoryError(RuntimeError):
    """Fail-closed exception for strategy memory persistence and queries."""


class DuplicateStrategyMemoryError(StrategyMemoryRepositoryError):
    """Raised when a strategy memory record_id is duplicated."""


@dataclass(frozen=True)
class StrategyMemoryRecord:
    record_id: str
    timestamp: str
    strategy_id: str
    symbol: str
    asset_class: str
    market_regime: str
    session: str
    broker: str
    trade_id: str
    realized_pnl: float
    win: bool
    confidence: float


_REQUIRED_FIELDS = tuple(StrategyMemoryRecord.__dataclass_fields__.keys())
_STRING_FIELDS = {
    "record_id",
    "timestamp",
    "strategy_id",
    "symbol",
    "asset_class",
    "market_regime",
    "session",
    "broker",
    "trade_id",
}


class StrategyMemoryRepository:
    """JSON-backed repository for canonical strategy memory records."""

    def __init__(self, storage_path: str | Path):
        self.storage_path = Path(storage_path)

    def create_storage(self) -> None:
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            if not self.storage_path.exists():
                self._atomic_write([])
            else:
                self.load_records()
        except StrategyMemoryRepositoryError:
            raise
        except Exception as exc:
            raise StrategyMemoryRepositoryError(f"Unable to create strategy memory storage: {exc}") from exc

    def persist_memory_record(self, record: Mapping[str, Any] | StrategyMemoryRecord) -> dict[str, Any]:
        normalized = self._normalize_record(record)
        rows = self.load_records()
        if any(existing["record_id"] == normalized.record_id for existing in rows):
            raise DuplicateStrategyMemoryError(
                f"Strategy memory record already exists for record_id={normalized.record_id}"
            )
        rows.append(asdict(normalized))
        self._atomic_write(rows)
        return asdict(normalized)

    def load_records(self) -> list[dict[str, Any]]:
        try:
            if not self.storage_path.exists():
                raise StrategyMemoryRepositoryError(
                    f"Strategy memory storage does not exist: {self.storage_path}"
                )
            with self.storage_path.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
            if not isinstance(raw, list):
                raise StrategyMemoryRepositoryError("Strategy memory storage must contain a JSON list")
            records = [self._normalize_record(item) for item in raw]
            self._assert_unique_record_ids(records)
            return [asdict(item) for item in records]
        except StrategyMemoryRepositoryError:
            raise
        except Exception as exc:
            raise StrategyMemoryRepositoryError(f"Unable to load strategy memory: {exc}") from exc

    def query_by_strategy(self, strategy_id: str) -> list[dict[str, Any]]:
        strategy = str(strategy_id or "").strip()
        if not strategy:
            raise StrategyMemoryRepositoryError("strategy_id must be non-empty")
        return [row for row in self.load_records() if row["strategy_id"] == strategy]

    def query_by_symbol(self, symbol: str) -> list[dict[str, Any]]:
        normalized_symbol = str(symbol or "").strip().upper()
        if not normalized_symbol:
            raise StrategyMemoryRepositoryError("symbol must be non-empty")
        return [row for row in self.load_records() if row["symbol"] == normalized_symbol]

    def query_by_regime(self, market_regime: str) -> list[dict[str, Any]]:
        regime = str(market_regime or "").strip().upper()
        if not regime:
            raise StrategyMemoryRepositoryError("market_regime must be non-empty")
        return [row for row in self.load_records() if row["market_regime"] == regime]

    def aggregate_strategy_performance(self) -> list[dict[str, Any]]:
        rows = self.load_records()
        if not rows:
            return []

        aggregates: dict[str, dict[str, Any]] = {}
        for row in rows:
            strategy_id = row["strategy_id"]
            slot = aggregates.setdefault(
                strategy_id,
                {
                    "strategy_id": strategy_id,
                    "trade_count": 0,
                    "win_count": 0,
                    "realized_pnl": 0.0,
                    "average_confidence": 0.0,
                },
            )
            slot["trade_count"] += 1
            slot["realized_pnl"] += float(row["realized_pnl"])
            slot["win_count"] += 1 if bool(row["win"]) else 0
            slot["average_confidence"] += float(row["confidence"])

        output: list[dict[str, Any]] = []
        for strategy_id in sorted(aggregates.keys()):
            entry = aggregates[strategy_id]
            trade_count = int(entry["trade_count"])
            output.append(
                {
                    "strategy_id": strategy_id,
                    "trade_count": trade_count,
                    "win_rate": entry["win_count"] / trade_count,
                    "realized_pnl": float(entry["realized_pnl"]),
                    "average_confidence": float(entry["average_confidence"]) / trade_count,
                }
            )

        return output

    def _atomic_write(self, rows: Iterable[Mapping[str, Any]]) -> None:
        normalized = [asdict(self._normalize_record(item)) for item in rows]
        self._assert_unique_record_ids([self._normalize_record(item) for item in normalized])

        try:
            with NamedTemporaryFile("w", encoding="utf-8", dir=self.storage_path.parent, delete=False) as tmp:
                json.dump(normalized, tmp, indent=2, sort_keys=True)
                tmp.write("\n")
                tmp_name = tmp.name
            os.replace(tmp_name, self.storage_path)
        except Exception as exc:
            raise StrategyMemoryRepositoryError(f"Unable to persist strategy memory: {exc}") from exc

    @staticmethod
    def _normalize_record(raw: Mapping[str, Any] | StrategyMemoryRecord) -> StrategyMemoryRecord:
        if isinstance(raw, StrategyMemoryRecord):
            payload = asdict(raw)
        elif isinstance(raw, Mapping):
            payload = dict(raw)
        else:
            raise StrategyMemoryRepositoryError("Strategy memory record must be a mapping or StrategyMemoryRecord")

        missing = [field for field in _REQUIRED_FIELDS if field not in payload]
        if missing:
            raise StrategyMemoryRepositoryError(
                f"Strategy memory record missing required fields: {', '.join(missing)}"
            )

        normalized: dict[str, Any] = {}
        for field in _STRING_FIELDS:
            value = str(payload[field]).strip()
            if not value:
                raise StrategyMemoryRepositoryError(f"Strategy memory field {field} must be non-empty")
            if field in {"symbol", "asset_class", "market_regime"}:
                value = value.upper()
            normalized[field] = value

        try:
            normalized["realized_pnl"] = float(payload["realized_pnl"])
        except (TypeError, ValueError) as exc:
            raise StrategyMemoryRepositoryError("Strategy memory realized_pnl must be numeric") from exc

        normalized["win"] = bool(payload["win"])

        try:
            normalized["confidence"] = float(payload["confidence"])
        except (TypeError, ValueError) as exc:
            raise StrategyMemoryRepositoryError("Strategy memory confidence must be numeric") from exc

        if normalized["confidence"] < 0 or normalized["confidence"] > 1:
            raise StrategyMemoryRepositoryError("Strategy memory confidence must be between 0 and 1")

        return StrategyMemoryRecord(**{field: normalized[field] for field in _REQUIRED_FIELDS})

    @staticmethod
    def _assert_unique_record_ids(records: Iterable[StrategyMemoryRecord]) -> None:
        seen: set[str] = set()
        for record in records:
            if record.record_id in seen:
                raise DuplicateStrategyMemoryError(
                    f"Duplicate strategy memory record in storage for record_id={record.record_id}"
                )
            seen.add(record.record_id)
