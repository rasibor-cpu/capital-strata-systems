from __future__ import annotations

import json
import os
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Iterable, Mapping


class RegimeHistoryRepositoryError(RuntimeError):
    """Fail-closed exception for regime history persistence errors."""


@dataclass(frozen=True)
class RegimeHistoryRecord:
    timestamp: str
    regime: str
    symbol: str
    confidence: float


_REQUIRED_FIELDS = tuple(RegimeHistoryRecord.__dataclass_fields__.keys())
_SUPPORTED_REGIMES = {
    "TRENDING",
    "RANGING",
    "BREAKOUT",
    "REVERSAL",
    "HIGH_VOLATILITY",
    "LOW_VOLATILITY",
    "UNKNOWN",
}


class RegimeHistoryRepository:
    """JSON-backed repository for canonical regime history."""

    def __init__(self, storage_path: str | Path):
        self.storage_path = Path(storage_path)

    def create_storage(self) -> None:
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            if not self.storage_path.exists():
                self._atomic_write([])
            else:
                self.load_history()
        except RegimeHistoryRepositoryError:
            raise
        except Exception as exc:
            raise RegimeHistoryRepositoryError(f"Unable to create regime history storage: {exc}") from exc

    def load_history(self) -> list[dict[str, Any]]:
        try:
            if not self.storage_path.exists():
                raise RegimeHistoryRepositoryError(f"Regime history storage does not exist: {self.storage_path}")
            with self.storage_path.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
            if not isinstance(raw, list):
                raise RegimeHistoryRepositoryError("Regime history storage must contain a JSON list")
            return [asdict(self._normalize_record(item)) for item in raw]
        except RegimeHistoryRepositoryError:
            raise
        except Exception as exc:
            raise RegimeHistoryRepositoryError(f"Unable to load regime history: {exc}") from exc

    def append_regime(self, record: Mapping[str, Any] | RegimeHistoryRecord) -> dict[str, Any]:
        normalized = self._normalize_record(record)
        rows = self.load_history()
        rows.append(asdict(normalized))
        self._atomic_write(rows)
        return asdict(normalized)

    def list_recent_regimes(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.load_history()
        return list(reversed(rows))[: max(0, int(limit))]

    def regime_counts(self) -> dict[str, int]:
        rows = self.load_history()
        counter = Counter(str(row["regime"]).upper() for row in rows)
        return {key: counter[key] for key in sorted(counter.keys())}

    def symbol_regime_history(self, symbol: str, limit: int = 50) -> list[dict[str, Any]]:
        target_symbol = str(symbol or "").strip().upper()
        if not target_symbol:
            raise RegimeHistoryRepositoryError("Symbol must be non-empty")

        rows = [
            row
            for row in self.load_history()
            if str(row.get("symbol", "")).upper() == target_symbol
        ]
        return list(reversed(rows))[: max(0, int(limit))]

    def _atomic_write(self, rows: Iterable[Mapping[str, Any]]) -> None:
        normalized = [asdict(self._normalize_record(item)) for item in rows]
        try:
            with NamedTemporaryFile("w", encoding="utf-8", dir=self.storage_path.parent, delete=False) as tmp:
                json.dump(normalized, tmp, indent=2, sort_keys=True)
                tmp.write("\n")
                tmp_name = tmp.name
            os.replace(tmp_name, self.storage_path)
        except Exception as exc:
            raise RegimeHistoryRepositoryError(f"Unable to persist regime history: {exc}") from exc

    @staticmethod
    def _normalize_record(raw: Mapping[str, Any] | RegimeHistoryRecord) -> RegimeHistoryRecord:
        if isinstance(raw, RegimeHistoryRecord):
            payload = asdict(raw)
        elif isinstance(raw, Mapping):
            payload = dict(raw)
        else:
            raise RegimeHistoryRepositoryError("Regime history record must be a mapping or RegimeHistoryRecord")

        missing = [field for field in _REQUIRED_FIELDS if field not in payload]
        if missing:
            raise RegimeHistoryRepositoryError(
                f"Regime history missing required fields: {', '.join(missing)}"
            )

        timestamp = str(payload["timestamp"]).strip()
        regime = str(payload["regime"]).strip().upper()
        symbol = str(payload["symbol"]).strip().upper()
        try:
            confidence = float(payload["confidence"])
        except (TypeError, ValueError) as exc:
            raise RegimeHistoryRepositoryError("Regime history confidence must be numeric") from exc

        if not timestamp:
            raise RegimeHistoryRepositoryError("Regime history timestamp must be non-empty")
        if regime not in _SUPPORTED_REGIMES:
            raise RegimeHistoryRepositoryError("Regime history regime is invalid")
        if not symbol:
            raise RegimeHistoryRepositoryError("Regime history symbol must be non-empty")
        if confidence < 0 or confidence > 1:
            raise RegimeHistoryRepositoryError("Regime history confidence must be between 0 and 1")

        return RegimeHistoryRecord(
            timestamp=timestamp,
            regime=regime,
            symbol=symbol,
            confidence=confidence,
        )
