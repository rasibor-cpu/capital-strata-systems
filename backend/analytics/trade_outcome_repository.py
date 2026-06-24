from __future__ import annotations

import json
import os
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Iterable, Mapping


class TradeOutcomeRepositoryError(RuntimeError):
    """Base explicit fail-closed exception for trade outcome persistence."""


class DuplicateTradeOutcomeError(TradeOutcomeRepositoryError):
    """Raised when a completed trade_id is already persisted."""


@dataclass(frozen=True)
class TradeOutcomeRecord:
    trade_id: str
    timestamp_open: str
    timestamp_close: str
    symbol: str
    asset_class: str
    entry_price: float
    exit_price: float
    quantity: float
    realized_pnl: float
    holding_duration_seconds: float
    strategy_id: str
    market_regime: str
    broker: str


_REQUIRED_FIELDS = tuple(TradeOutcomeRecord.__dataclass_fields__.keys())
_STRING_FIELDS = {
    "trade_id",
    "timestamp_open",
    "timestamp_close",
    "symbol",
    "asset_class",
    "strategy_id",
    "market_regime",
    "broker",
}
_FLOAT_FIELDS = {
    "entry_price",
    "exit_price",
    "quantity",
    "realized_pnl",
    "holding_duration_seconds",
}


class TradeOutcomeRepository:
    """JSON-backed fail-closed repository for canonical completed trade outcomes."""

    def __init__(self, storage_path: str | Path):
        self.storage_path = Path(storage_path)

    def create_storage(self) -> None:
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            if not self.storage_path.exists():
                self._atomic_write([])
            else:
                self.load_outcomes()
        except TradeOutcomeRepositoryError:
            raise
        except Exception as exc:  # pragma: no cover - defensive fail-closed wrapper
            raise TradeOutcomeRepositoryError(f"Unable to create trade outcome storage: {exc}") from exc

    def load_outcomes(self) -> list[dict[str, Any]]:
        try:
            if not self.storage_path.exists():
                raise TradeOutcomeRepositoryError(f"Trade outcome storage does not exist: {self.storage_path}")
            with self.storage_path.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
            if not isinstance(raw, list):
                raise TradeOutcomeRepositoryError("Trade outcome storage must contain a JSON list")
            outcomes = [self._normalize_record(item) for item in raw]
            self._assert_unique_trade_ids(outcomes)
            return [asdict(item) for item in outcomes]
        except TradeOutcomeRepositoryError:
            raise
        except Exception as exc:
            raise TradeOutcomeRepositoryError(f"Unable to load trade outcomes: {exc}") from exc

    def append_outcome(self, outcome: Mapping[str, Any] | TradeOutcomeRecord) -> dict[str, Any]:
        record = self._normalize_record(outcome)
        outcomes = self.load_outcomes()
        if any(existing["trade_id"] == record.trade_id for existing in outcomes):
            raise DuplicateTradeOutcomeError(f"Trade outcome already exists for trade_id={record.trade_id}")
        outcomes.append(asdict(record))
        self._atomic_write(outcomes)
        return asdict(record)

    def aggregate_by_symbol(self) -> list[dict[str, Any]]:
        return self._aggregate_by("symbol")

    def aggregate_by_asset_class(self) -> list[dict[str, Any]]:
        return self._aggregate_by("asset_class")

    def aggregate_by_strategy_id(self) -> list[dict[str, Any]]:
        return self._aggregate_by("strategy_id")

    def _aggregate_by(self, field: str) -> list[dict[str, Any]]:
        totals: dict[str, dict[str, Any]] = defaultdict(lambda: {"trade_count": 0, "realized_pnl": 0.0})
        for outcome in self.load_outcomes():
            key = str(outcome[field])
            totals[key]["trade_count"] += 1
            totals[key]["realized_pnl"] += float(outcome["realized_pnl"])
        return [
            {field: key, "trade_count": value["trade_count"], "realized_pnl": value["realized_pnl"]}
            for key, value in sorted(totals.items())
        ]

    def _atomic_write(self, outcomes: Iterable[Mapping[str, Any]]) -> None:
        normalized = [asdict(self._normalize_record(item)) for item in outcomes]
        self._assert_unique_trade_ids([self._normalize_record(item) for item in normalized])
        try:
            with NamedTemporaryFile("w", encoding="utf-8", dir=self.storage_path.parent, delete=False) as tmp:
                json.dump(normalized, tmp, indent=2, sort_keys=True)
                tmp.write("\n")
                tmp_name = tmp.name
            os.replace(tmp_name, self.storage_path)
        except Exception as exc:
            raise TradeOutcomeRepositoryError(f"Unable to persist trade outcomes: {exc}") from exc

    @staticmethod
    def _normalize_record(raw: Mapping[str, Any] | TradeOutcomeRecord) -> TradeOutcomeRecord:
        if isinstance(raw, TradeOutcomeRecord):
            raw_map = asdict(raw)
        elif isinstance(raw, Mapping):
            raw_map = dict(raw)
        else:
            raise TradeOutcomeRepositoryError("Trade outcome must be a mapping or TradeOutcomeRecord")

        missing = [field for field in _REQUIRED_FIELDS if field not in raw_map]
        if missing:
            raise TradeOutcomeRepositoryError(f"Trade outcome missing required fields: {', '.join(missing)}")

        normalized: dict[str, Any] = {}
        for field in _STRING_FIELDS:
            value = str(raw_map[field]).strip()
            if not value:
                raise TradeOutcomeRepositoryError(f"Trade outcome field {field} must be non-empty")
            normalized[field] = value
        for field in _FLOAT_FIELDS:
            try:
                normalized[field] = float(raw_map[field])
            except (TypeError, ValueError) as exc:
                raise TradeOutcomeRepositoryError(f"Trade outcome field {field} must be numeric") from exc
        return TradeOutcomeRecord(**{field: normalized[field] for field in _REQUIRED_FIELDS})

    @staticmethod
    def _assert_unique_trade_ids(outcomes: Iterable[TradeOutcomeRecord]) -> None:
        seen: set[str] = set()
        for outcome in outcomes:
            if outcome.trade_id in seen:
                raise DuplicateTradeOutcomeError(f"Duplicate trade outcome in storage for trade_id={outcome.trade_id}")
            seen.add(outcome.trade_id)


def persist_completed_trade_outcome(
    repository: TradeOutcomeRepository,
    outcome: Mapping[str, Any] | TradeOutcomeRecord,
) -> dict[str, Any]:
    """Adapter/hook for canonical close paths to persist a completed trade outcome.

    Intended integration point: call this immediately after the canonical trade close
    path computes final realized PnL and before the close result is considered durable.
    The function intentionally raises explicit repository exceptions so callers fail
    closed instead of silently losing completed-trade analytics.
    """

    return repository.append_outcome(outcome)


def _rank(rows: list[dict[str, Any]], key_name: str, *, reverse: bool, limit: int) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: (row["realized_pnl"], row[key_name]), reverse=reverse)[:limit]


def build_trade_outcome_analytics_adapter(
    repository: TradeOutcomeRepository,
    *,
    limit: int = 10,
) -> dict[str, list[dict[str, Any]]]:
    if limit <= 0:
        raise TradeOutcomeRepositoryError("Analytics adapter limit must be positive")
    symbol_rows = repository.aggregate_by_symbol()
    asset_rows = repository.aggregate_by_asset_class()
    strategy_rows = repository.aggregate_by_strategy_id()
    return {
        "top_symbols": _rank(symbol_rows, "symbol", reverse=True, limit=limit),
        "worst_symbols": _rank(symbol_rows, "symbol", reverse=False, limit=limit),
        "top_asset_classes": _rank(asset_rows, "asset_class", reverse=True, limit=limit),
        "top_strategies": _rank(strategy_rows, "strategy_id", reverse=True, limit=limit),
    }
