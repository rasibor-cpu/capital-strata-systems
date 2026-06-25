from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Mapping


class TradeExplanationRepositoryError(RuntimeError):
    """Fail-closed exception for explanation persistence."""


class TradeExplanationRepository:
    def __init__(self, storage_path: str | Path):
        self.storage_path = Path(storage_path)

    def create_storage(self) -> None:
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            if not self.storage_path.exists():
                self._atomic_write([])
            else:
                self.load_explanations()
        except TradeExplanationRepositoryError:
            raise
        except Exception as exc:
            raise TradeExplanationRepositoryError(f"Unable to create explanation storage: {exc}") from exc

    def persist_explanation(self, explanation: Mapping[str, Any]) -> dict[str, Any]:
        normalized = self._normalize(explanation)
        rows = self.load_explanations()
        rows.append(normalized)
        self._atomic_write(rows)
        return normalized

    def load_explanations(self) -> list[dict[str, Any]]:
        try:
            if not self.storage_path.exists():
                return []
            raw = json.loads(self.storage_path.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                raise TradeExplanationRepositoryError("Explanation storage must contain a JSON list")
            return [self._normalize(item) for item in raw]
        except TradeExplanationRepositoryError:
            raise
        except Exception as exc:
            raise TradeExplanationRepositoryError(f"Unable to load explanations: {exc}") from exc

    def query_by_trade_id(self, trade_id: str) -> list[dict[str, Any]]:
        normalized = str(trade_id or "").strip()
        if not normalized:
            raise TradeExplanationRepositoryError("trade_id must be non-empty")
        return [row for row in self.load_explanations() if row["trade_id"] == normalized]

    def query_by_strategy(self, strategy_id: str) -> list[dict[str, Any]]:
        normalized = str(strategy_id or "").strip()
        if not normalized:
            raise TradeExplanationRepositoryError("strategy_id must be non-empty")
        return [row for row in self.load_explanations() if row["strategy_id"] == normalized]

    def query_by_regime(self, market_regime: str) -> list[dict[str, Any]]:
        normalized = str(market_regime or "").strip().upper()
        if not normalized:
            raise TradeExplanationRepositoryError("market_regime must be non-empty")
        return [row for row in self.load_explanations() if row["market_regime"] == normalized]

    def _atomic_write(self, rows: list[dict[str, Any]]) -> None:
        try:
            with NamedTemporaryFile("w", encoding="utf-8", dir=self.storage_path.parent, delete=False) as tmp:
                json.dump(rows, tmp, indent=2, sort_keys=True)
                tmp.write("\n")
                tmp_name = tmp.name
            os.replace(tmp_name, self.storage_path)
        except Exception as exc:
            raise TradeExplanationRepositoryError(f"Unable to persist explanations: {exc}") from exc

    def _normalize(self, explanation: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(explanation, Mapping):
            raise TradeExplanationRepositoryError("Explanation must be a mapping")
        trade_id = str(explanation.get("trade_id") or "").strip()
        strategy_id = str(explanation.get("strategy_id") or explanation.get("strategy") or "UNKNOWN").strip() or "UNKNOWN"
        market_regime = str(explanation.get("market_regime") or "UNKNOWN").strip().upper() or "UNKNOWN"
        if not trade_id:
            raise TradeExplanationRepositoryError("trade_id must be non-empty")
        return {
            "explanation_id": str(explanation.get("explanation_id") or f"{trade_id}:{strategy_id}"),
            "trade_id": trade_id,
            "strategy_id": strategy_id,
            "market_regime": market_regime,
            "why_selected": str(explanation.get("why_selected") or "").strip(),
            "why_rejected": str(explanation.get("why_rejected") or "").strip(),
            "supporting_indicators": dict(explanation.get("supporting_indicators") or {}),
            "historical_confidence": float(explanation.get("historical_confidence", explanation.get("confidence", 0.0))),
            "alternative_strategy": str(explanation.get("alternative_strategy") or "").strip(),
            "alternative_timeframe": str(explanation.get("alternative_timeframe") or "").strip(),
            "entry_reason": str(explanation.get("entry_reason") or "").strip(),
            "exit_reason": str(explanation.get("exit_reason") or "").strip(),
            "trade_quality": str(explanation.get("trade_quality") or "").strip(),
            "confidence": float(explanation.get("confidence", 0.0)),
            "position_size": float(explanation.get("position_size", 0.0)),
            "capital_allocation": float(explanation.get("capital_allocation", 0.0)),
            "holding_time_seconds": float(explanation.get("holding_time_seconds", 0.0)),
            "pnl": float(explanation.get("pnl", 0.0)),
            "decision_optimal": bool(explanation.get("decision_optimal", False)),
        }
