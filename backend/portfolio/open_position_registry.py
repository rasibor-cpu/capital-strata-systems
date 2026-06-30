from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.portfolio.utils import safe_float


class OpenPositionRegistryError(RuntimeError):
    """Fail-closed exception for open position registry operations."""


class OpenPositionRegistry:
    """Track paper/runtime open positions from local artifacts only."""

    def __init__(self, artifacts_dir: str | Path) -> None:
        self.root = Path(artifacts_dir) / "portfolio"
        self.path = self.root / "open_position_registry.json"

    def sync_positions(
        self,
        positions: Iterable[Mapping[str, Any]] | None,
        *,
        timestamp: str | None = None,
        persist: bool = True,
    ) -> dict[str, Any]:
        if positions is None:
            return self._response("DATA UNAVAILABLE", [], ["positions_unavailable"])
        if isinstance(positions, (str, bytes)) or not isinstance(positions, Iterable):
            return self._response("DATA UNAVAILABLE", [], ["positions_must_be_iterable"])

        now = timestamp or datetime.now(timezone.utc).isoformat()
        state = self._read_state()
        open_positions = state.setdefault("open_positions", {})
        closed_positions = state.setdefault("closed_positions", [])
        seen: set[str] = set()

        for raw in positions:
            if not isinstance(raw, Mapping):
                return self._response("DATA UNAVAILABLE", [], ["position_row_not_mapping"])
            try:
                normalized = self._normalize(raw, now)
            except OpenPositionRegistryError as exc:
                return self._response("DATA UNAVAILABLE", [], [str(exc)])
            key = normalized["position_id"]
            seen.add(key)
            existing = open_positions.get(key, {})
            entry_timestamp = existing.get("entry_timestamp") or normalized["entry_timestamp"]
            open_positions[key] = {
                **existing,
                **normalized,
                "entry_timestamp": entry_timestamp,
                "last_seen": now,
                "age_seconds": self._age_seconds(entry_timestamp, now),
                "status": "OPEN",
            }

        for key in sorted(set(open_positions.keys()) - seen):
            record = dict(open_positions.pop(key))
            record["status"] = "CLOSED"
            record["closed_timestamp"] = now
            record["realized_pnl"] = safe_float(record.get("unrealized_pnl"))
            closed_positions.append(record)

        state["last_sync_time"] = now
        if persist:
            self._write_state(state)
        return self._summary_from_state(state)

    def list_open(self) -> dict[str, Any]:
        rows = list(self._read_state().get("open_positions", {}).values())
        return self._response("OK", sorted(rows, key=lambda item: str(item.get("symbol", ""))), [])

    def list_closed(self) -> dict[str, Any]:
        rows = self._read_state().get("closed_positions", [])
        rows = rows if isinstance(rows, list) else []
        return {
            "status": "OK",
            "closed_positions": [row for row in rows if isinstance(row, dict)],
            "closed_count": len(rows),
            "advisory_only": True,
            "execution_allowed": False,
        }

    def summary(self) -> dict[str, Any]:
        return self._summary_from_state(self._read_state())

    @staticmethod
    def _summary_from_state(state: Mapping[str, Any]) -> dict[str, Any]:
        rows = [row for row in state.get("open_positions", {}).values() if isinstance(row, dict)]
        total_exposure = sum(safe_float(row.get("exposure")) for row in rows)
        return {
            "status": "OK",
            "open_positions": sorted(rows, key=lambda item: str(item.get("symbol", ""))),
            "open_count": len(rows),
            "total_exposure": round(total_exposure, 8),
            "last_sync_time": state.get("last_sync_time"),
            "advisory_only": True,
            "execution_allowed": False,
        }

    def _normalize(self, row: Mapping[str, Any], now: str) -> dict[str, Any]:
        symbol = str(row.get("symbol") or row.get("asset") or "").strip().upper()
        if not symbol:
            raise OpenPositionRegistryError("position_symbol_missing")
        strategy = str(row.get("strategy_id") or row.get("strategy") or "UNSPECIFIED").strip().upper() or "UNSPECIFIED"
        quantity = safe_float(row.get("quantity", row.get("size", 0.0)))
        entry_price = safe_float(row.get("entry_price", row.get("price", row.get("current_price", 0.0))))
        current_price = safe_float(row.get("current_price", row.get("price", entry_price)))
        exposure = self._exposure(row, quantity, current_price)
        entry_timestamp = str(row.get("entry_timestamp") or row.get("opened_at") or row.get("timestamp") or now)
        unrealized = row.get("unrealized_pnl")
        if unrealized is None and quantity and entry_price and current_price:
            unrealized = (current_price - entry_price) * quantity
        return {
            "position_id": str(row.get("position_id") or row.get("id") or f"{symbol}:{strategy}").upper(),
            "symbol": symbol,
            "asset_class": str(row.get("asset_class") or row.get("class") or "UNKNOWN").strip().upper() or "UNKNOWN",
            "strategy_id": strategy,
            "direction": str(row.get("direction") or row.get("side") or "LONG").strip().upper() or "LONG",
            "quantity": round(quantity, 8),
            "entry_price": round(entry_price, 8),
            "current_price": round(current_price, 8),
            "exposure": round(abs(exposure), 8),
            "entry_timestamp": entry_timestamp,
            "unrealized_pnl": round(safe_float(unrealized), 8),
            "realized_pnl": round(safe_float(row.get("realized_pnl")), 8),
        }

    @staticmethod
    def _exposure(row: Mapping[str, Any], quantity: float, current_price: float) -> float:
        for key in ("exposure_value", "market_value", "notional_value", "position_value", "current_value", "value"):
            if row.get(key) is not None:
                return safe_float(row.get(key))
        return quantity * current_price

    def _read_state(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"open_positions": {}, "closed_positions": [], "last_sync_time": None}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {"open_positions": {}, "closed_positions": [], "last_sync_time": None, "recovered_from_corrupt_file": True}
        if not isinstance(payload, dict):
            return {"open_positions": {}, "closed_positions": [], "last_sync_time": None, "recovered_from_corrupt_file": True}
        payload.setdefault("open_positions", {})
        payload.setdefault("closed_positions", [])
        return payload

    def _write_state(self, state: Mapping[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")

    @staticmethod
    def _age_seconds(start: str, end: str) -> float:
        try:
            start_dt = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
            return round(max(0.0, (end_dt - start_dt).total_seconds()), 6)
        except Exception:
            return 0.0

    @staticmethod
    def _response(status: str, rows: list[dict[str, Any]], reasons: list[str]) -> dict[str, Any]:
        return {
            "status": status,
            "open_positions": rows,
            "open_count": len(rows),
            "total_exposure": round(sum(safe_float(row.get("exposure")) for row in rows), 8),
            "reasons": reasons,
            "advisory_only": True,
            "execution_allowed": False,
        }
