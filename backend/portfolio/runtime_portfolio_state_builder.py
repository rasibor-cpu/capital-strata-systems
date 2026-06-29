from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from backend.portfolio.utils import normalize_allocations, safe_float


class RuntimePortfolioStateBuilderError(RuntimeError):
    """Fail-closed exception for runtime portfolio state building."""


class RuntimePortfolioStateBuilder:
    """Build canonical advisory portfolio state from local runtime artifacts."""

    def __init__(
        self,
        *,
        artifacts_dir: str | Path,
        account_state_path: str | Path | None = None,
        session_state_path: str | Path | None = None,
        closed_trade_ledger_path: str | Path | None = None,
        supervisor_state_path: str | Path | None = None,
        stale_after_seconds: float = 300.0,
    ) -> None:
        self.artifacts_dir = Path(artifacts_dir)
        self.account_state_path = Path(account_state_path) if account_state_path else self.artifacts_dir / "css_account_state_pcnrass.json"
        self.session_state_path = Path(session_state_path) if session_state_path else self.artifacts_dir / "css_session_state_pcnrass.json"
        self.closed_trade_ledger_path = Path(closed_trade_ledger_path) if closed_trade_ledger_path else None
        self.supervisor_state_path = Path(supervisor_state_path) if supervisor_state_path else None
        self.stale_after_seconds = float(stale_after_seconds)

    def build(self) -> dict[str, Any]:
        reasons: list[str] = []
        account = self._read_json(self.account_state_path, "account_state", reasons)
        session = self._read_json(self.session_state_path, "session_state", reasons)
        supervisor = self._read_json(self.supervisor_state_path, "supervisor_state", reasons) if self.supervisor_state_path else {}
        trades = self._read_trades(reasons)
        positions = self._positions(account, session)

        if not account:
            reasons.append("account_state_unavailable")
        if not session:
            reasons.append("session_state_unavailable")
        if not positions:
            reasons.append("positions_unavailable")

        staleness = self._staleness(
            {
                "account_state": self.account_state_path,
                "session_state": self.session_state_path,
                "supervisor_state": self.supervisor_state_path,
                "closed_trade_ledger": self.closed_trade_ledger_path,
            }
        )
        stale_artifacts = [name for name, payload in staleness.items() if payload.get("stale") is True]
        if stale_artifacts:
            reasons.append("stale_runtime_artifacts")

        sufficient = bool(account and session and positions)
        return {
            "status": "OK" if sufficient else "DATA UNAVAILABLE",
            "account": self._account_summary(account),
            "positions": positions,
            "trades": trades,
            "performance_metrics": self._performance_metrics(account, positions, trades),
            "asset_allocations": self._asset_allocations(positions),
            "strategy_metrics": self._strategy_metrics(trades),
            "market_data": self._market_data(session, trades),
            "supervisor": supervisor if isinstance(supervisor, dict) else {},
            "staleness": staleness,
            "reasons": sorted(set(reasons)),
            "advisory_only": True,
            "execution_allowed": False,
        }

    def _read_json(self, path: Path | None, name: str, reasons: list[str]) -> dict[str, Any]:
        if path is None:
            return {}
        if not path.exists():
            reasons.append(f"{name}_missing")
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            reasons.append(f"{name}_malformed")
            return {}
        if not isinstance(payload, dict):
            reasons.append(f"{name}_not_object")
            return {}
        return payload

    def _read_trades(self, reasons: list[str]) -> list[dict[str, Any]]:
        paths = [self.artifacts_dir / "trade_outcomes.json", self.closed_trade_ledger_path]
        for path in [item for item in paths if item is not None]:
            if not path.exists():
                continue
            try:
                if path.suffix.lower() == ".jsonl":
                    rows = []
                    for line in path.read_text(encoding="utf-8").splitlines():
                        if not line.strip():
                            continue
                        payload = json.loads(line)
                        if isinstance(payload, dict):
                            rows.append(payload)
                    if rows:
                        return rows
                else:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(payload, list):
                        return [row for row in payload if isinstance(row, dict)]
                    if isinstance(payload, dict):
                        rows = payload.get("trades", payload.get("closed_trades", payload.get("outcomes", [])))
                        if isinstance(rows, list):
                            return [row for row in rows if isinstance(row, dict)]
            except Exception:
                reasons.append(f"{path.name}_malformed")
                return []
        reasons.append("trade_history_unavailable")
        return []

    @staticmethod
    def _positions(account: Mapping[str, Any], session: Mapping[str, Any]) -> list[dict[str, Any]]:
        raw_positions = account.get("positions", [])
        if not raw_positions:
            raw_positions = session.get("open_trades", [])
        if not isinstance(raw_positions, list):
            return []
        positions: list[dict[str, Any]] = []
        for idx, raw in enumerate(raw_positions):
            if not isinstance(raw, Mapping):
                continue
            symbol = str(raw.get("symbol") or raw.get("asset") or f"POSITION_{idx}").strip().upper()
            asset_class = str(raw.get("asset_class") or raw.get("class") or "UNKNOWN").strip().upper() or "UNKNOWN"
            quantity = safe_float(raw.get("quantity", raw.get("size", 0.0)))
            price = safe_float(raw.get("current_price", raw.get("entry_price", raw.get("price", 1.0))), 1.0)
            market_value = safe_float(raw.get("market_value", raw.get("notional_value", raw.get("current_value", raw.get("value", quantity * price)))))
            if market_value == 0.0 and quantity != 0.0:
                market_value = quantity * price
            positions.append(
                {
                    **dict(raw),
                    "symbol": symbol,
                    "asset_class": asset_class,
                    "quantity": quantity,
                    "current_price": price,
                    "market_value": abs(market_value),
                }
            )
        return positions

    @staticmethod
    def _account_summary(account: Mapping[str, Any]) -> dict[str, float]:
        cash = safe_float(account.get("account_balance", account.get("cash", 0.0)))
        equity = safe_float(account.get("total_equity", account.get("equity", cash)))
        unrealized = safe_float(account.get("unrealized_pnl", 0.0))
        realized = safe_float(account.get("lifetime_realized_pnl", account.get("realized_pnl", 0.0)))
        return {
            "cash": round(cash, 8),
            "equity": round(equity, 8),
            "buying_power": round(safe_float(account.get("buying_power", cash)), 8),
            "open_pnl": round(unrealized, 8),
            "realized_pnl": round(realized, 8),
            "total_pnl": round(realized + unrealized, 8),
        }

    @staticmethod
    def _performance_metrics(account: Mapping[str, Any], positions: list[dict[str, Any]], trades: list[dict[str, Any]]) -> dict[str, Any]:
        equity = safe_float(account.get("total_equity", account.get("equity", account.get("account_balance", 0.0))))
        exposure = sum(abs(safe_float(row.get("market_value"))) for row in positions)
        returns = RuntimePortfolioStateBuilder._returns(trades)
        max_drawdown = max([abs(safe_float(row.get("drawdown", row.get("max_drawdown", 0.0)))) for row in trades] or [0.0])
        negative = [value for value in returns if value < 0.0]
        downside = (sum(value * value for value in negative) / len(returns)) ** 0.5 if returns else 0.0
        average = sum(returns) / len(returns) if returns else 0.0
        return {
            "capital_efficiency": round(exposure / equity, 8) if equity > 0.0 else 0.0,
            "max_drawdown": round(max_drawdown, 8),
            "sortino": round(average / downside, 8) if downside > 0.0 else (2.0 if average > 0.0 else 1.0),
            "correlation_score": 0.0,
            "portfolio_returns": returns,
        }

    @staticmethod
    def _asset_allocations(positions: list[dict[str, Any]]) -> dict[str, float]:
        values: dict[str, float] = {}
        for row in positions:
            asset = str(row.get("asset_class") or "UNKNOWN").upper()
            values[asset] = values.get(asset, 0.0) + safe_float(row.get("market_value"))
        return normalize_allocations(values)

    @staticmethod
    def _strategy_metrics(trades: list[dict[str, Any]]) -> dict[str, Any]:
        metrics: dict[str, dict[str, float]] = {}
        for row in trades:
            strategy = str(row.get("strategy_id", row.get("strategy", "STRATEGY_UNSPECIFIED"))).strip().upper()
            item = metrics.setdefault(strategy, {"trade_count": 0.0, "total_pnl": 0.0})
            item["trade_count"] += 1.0
            item["total_pnl"] += safe_float(row.get("realized_pnl", row.get("pnl", 0.0)))
        return {
            key: {"trade_count": int(value["trade_count"]), "total_pnl": round(value["total_pnl"], 8)}
            for key, value in sorted(metrics.items())
        }

    @staticmethod
    def _market_data(session: Mapping[str, Any], trades: list[dict[str, Any]]) -> dict[str, Any]:
        session_payload = session.get("session", session)
        session_payload = session_payload if isinstance(session_payload, Mapping) else {}
        return {
            "market_regime": str(session_payload.get("market_regime", session_payload.get("detected_regime", "UNKNOWN"))).upper(),
            "risk_status": str(session_payload.get("risk_status", "GREEN")).upper(),
            "returns": RuntimePortfolioStateBuilder._returns(trades),
        }

    @staticmethod
    def _returns(trades: list[dict[str, Any]]) -> list[float]:
        returns: list[float] = []
        for row in trades:
            if row.get("realized_return") is not None:
                returns.append(safe_float(row.get("realized_return")))
                continue
            pnl = safe_float(row.get("realized_pnl", row.get("pnl", 0.0)))
            capital = abs(safe_float(row.get("capital", row.get("notional", 10000.0)), 10000.0))
            returns.append(pnl / capital if capital > 0.0 else 0.0)
        return returns

    def _staleness(self, paths: Mapping[str, Path | None]) -> dict[str, dict[str, Any]]:
        now = datetime.now(timezone.utc).timestamp()
        result: dict[str, dict[str, Any]] = {}
        for name, path in paths.items():
            if path is None:
                continue
            exists = path.exists()
            age = max(0.0, now - path.stat().st_mtime) if exists else None
            result[name] = {
                "exists": exists,
                "age_seconds": round(age, 6) if age is not None else None,
                "stale_after_seconds": self.stale_after_seconds,
                "stale": bool(age is None or age > self.stale_after_seconds),
            }
        return result
