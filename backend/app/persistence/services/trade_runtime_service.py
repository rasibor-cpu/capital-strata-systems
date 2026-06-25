import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

from backend.app.persistence.services.persistence_service import (
    PersistenceService,
)
from backend.execution.canonical_trade_lifecycle import (
    CanonicalTradeLifecycle,
    CanonicalTradeLifecycleError,
)
from analytics.trade_outcome_ledger import TradeOutcome, TradeOutcomeLedger


class TradeRuntimeService:
    """
    Runtime trade lifecycle persistence manager.

    Responsibilities:
    - persist trade opens
    - persist trade closes
    - persist trade state transitions
    - provide runtime trade recovery access

    IMPORTANT:
    - no governance logic
    - no orchestration logic
    - no broker execution logic
    """

    def __init__(self, canonical_lifecycle: CanonicalTradeLifecycle | None = None) -> None:
        self.persistence = PersistenceService()
        self.canonical_lifecycle = canonical_lifecycle or CanonicalTradeLifecycle()
        # Backward compatibility: default service keeps close path resilient,
        # while explicitly injected lifecycle preserves strict fail-closed behavior.
        self._strict_canonical_persistence = canonical_lifecycle is not None
        self._legacy_trade_outcome_ledger = TradeOutcomeLedger()

    def open_trade(
        self,
        trade_id: str,
        session_id: str,
        broker_name: str,
        broker_mode: str,
        symbol: str,
        direction: str,
        order_type: str,
        quantity: Decimal,
        filled_quantity: Decimal,
        entry_price: Decimal,
        raw_payload_json: str | None = None,
    ) -> None:

        opened_at = (
            datetime.utcnow().isoformat()
        )

        self.persistence.trades.create_trade(
            trade_id=trade_id,
            session_id=session_id,
            broker_name=broker_name,
            broker_mode=broker_mode,
            symbol=symbol,
            direction=direction,
            status="open",
            order_type=order_type,
            quantity=quantity,
            filled_quantity=filled_quantity,
            entry_price=entry_price,
            opened_at=opened_at,
            raw_payload_json=raw_payload_json,
        )

    def update_trade_status(
        self,
        trade_id: str,
        status: str,
    ) -> None:

        self.persistence.trades.update_trade_status(
            trade_id=trade_id,
            status=status,
        )

    def close_trade(
        self,
        trade_id: str,
        exit_price: Decimal,
        realized_pnl: Decimal,
    ) -> None:

        closed_at = datetime.utcnow().isoformat()

        trade_record = None
        try:
            trade_record = self.persistence.trades.get_trade(trade_id)
        except Exception as exc:
            logging.getLogger(__name__).warning("Trade record fetch failed for %s: %s", trade_id, exc)

        if not trade_record:
            self.persistence.trades.close_trade(
                trade_id=trade_id,
                exit_price=exit_price,
                realized_pnl=realized_pnl,
                closed_at=closed_at,
            )
            return

        try:
            payload = self._build_canonical_close_payload(
                trade_id=trade_id,
                trade_record=trade_record,
                closed_at=closed_at,
                exit_price=exit_price,
                realized_pnl=realized_pnl,
            )
            self.canonical_lifecycle.persist_closed_trade_outcome(payload)
        except CanonicalTradeLifecycleError:
            if self._strict_canonical_persistence:
                raise
            logging.getLogger(__name__).warning(
                "Canonical trade lifecycle rejected close payload for %s",
                trade_id,
            )
        except Exception as exc:
            logging.getLogger(__name__).error("Canonical trade lifecycle persistence failed: %s", exc)
            if self._strict_canonical_persistence:
                raise

        self._append_legacy_trade_outcome(
            trade_id=trade_id,
            trade_record=trade_record,
            closed_at=closed_at,
            exit_price=exit_price,
            realized_pnl=realized_pnl,
        )

        self.persistence.trades.close_trade(
            trade_id=trade_id,
            exit_price=exit_price,
            realized_pnl=realized_pnl,
            closed_at=closed_at,
        )

    def _build_canonical_close_payload(
        self,
        *,
        trade_id: str,
        trade_record: dict[str, Any],
        closed_at: str,
        exit_price: Decimal,
        realized_pnl: Decimal,
    ) -> dict[str, Any]:
        opened_at = str(trade_record.get("opened_at") or closed_at)
        try:
            t_entry = datetime.fromisoformat(opened_at.replace("Z", "+00:00"))
            t_exit = datetime.fromisoformat(closed_at.replace("Z", "+00:00"))
            holding_seconds = (t_exit - t_entry).total_seconds()
        except Exception:
            holding_seconds = 0.0

        raw_payload: dict[str, Any] = {}
        raw_payload_json = trade_record.get("raw_payload_json")
        if isinstance(raw_payload_json, str) and raw_payload_json:
            try:
                raw_payload = json.loads(raw_payload_json)
            except Exception:
                raw_payload = {}

        symbol = str(trade_record.get("symbol", "UNKNOWN")).upper()
        asset_class = self._normalize_asset_class(
            asset_class=raw_payload.get("asset_class") or raw_payload.get("asset") or "UNKNOWN",
            symbol=symbol,
        )

        return {
            "trade_id": str(trade_id),
            "timestamp_open": opened_at,
            "timestamp_close": closed_at,
            "symbol": symbol,
            "asset_class": asset_class,
            "entry_price": float(trade_record.get("entry_price", 0.0)),
            "exit_price": float(exit_price),
            "quantity": float(trade_record.get("quantity", 0.0)),
            "realized_pnl": float(realized_pnl),
            "holding_duration_seconds": float(holding_seconds),
            "strategy_id": str(raw_payload.get("strategy_id") or raw_payload.get("strategy") or "UNKNOWN").strip(),
            "market_regime": str(raw_payload.get("market_regime") or raw_payload.get("regime") or "UNKNOWN").strip(),
            "broker": str(trade_record.get("broker_name") or trade_record.get("broker") or "UNKNOWN").strip(),
        }

    @staticmethod
    def _normalize_asset_class(*, asset_class: Any, symbol: str) -> str:
        raw = str(asset_class or "").strip().upper()
        aliases = {
            "FX": "FX",
            "FOREX": "FX",
            "CRYPTO": "CRYPTO",
            "OPTIONS": "OPTIONS",
            "OPTION": "OPTIONS",
            "FUTURES": "FUTURES",
            "FUTURE": "FUTURES",
            "EQUITY": "EQUITIES",
            "EQUITIES": "EQUITIES",
            "STOCK": "EQUITIES",
        }
        normalized = aliases.get(raw, raw)
        if normalized and normalized != "UNKNOWN":
            return normalized

        if any(token in symbol for token in ["BTC", "ETH", "SOL", "ADA", "DOGE", "LTC", "XRP"]):
            return "CRYPTO"
        if any(token in symbol for token in ["EUR_", "USD_", "GBP_", "JPY", "CAD", "AUD", "NZD", "CHF"]):
            return "FX"
        if any(token in symbol for token in ["GC", "CL", "ES", "NQ", "YM", "ZB", "ZN", "SI"]):
            return "FUTURES"
        if "-C-" in symbol or "-P-" in symbol:
            return "OPTIONS"
        if symbol and symbol.isalpha() and len(symbol) <= 6:
            return "EQUITIES"
        return "UNKNOWN"

    def _append_legacy_trade_outcome(
        self,
        *,
        trade_id: str,
        trade_record: dict[str, Any],
        closed_at: str,
        exit_price: Decimal,
        realized_pnl: Decimal,
    ) -> None:
        try:
            raw_payload: dict[str, Any] = {}
            raw_payload_json = trade_record.get("raw_payload_json")
            if isinstance(raw_payload_json, str) and raw_payload_json:
                try:
                    raw_payload = json.loads(raw_payload_json)
                except Exception:
                    raw_payload = {}

            symbol = str(trade_record.get("symbol") or "UNKNOWN").upper()
            asset_class = self._normalize_asset_class(
                asset_class=raw_payload.get("asset_class") or raw_payload.get("asset") or "UNKNOWN",
                symbol=symbol,
            )
            direction = str(trade_record.get("direction") or "").strip().upper()
            side = "BUY" if direction in {"LONG", "BUY"} else "SELL"
            entry_price = float(trade_record.get("entry_price", 0.0) or 0.0)
            quantity = float(trade_record.get("quantity", 0.0) or 0.0)
            opened_at = str(trade_record.get("opened_at") or closed_at)
            try:
                t_entry = datetime.fromisoformat(opened_at.replace("Z", "+00:00"))
                t_exit = datetime.fromisoformat(closed_at.replace("Z", "+00:00"))
                holding_seconds = max(0.0, (t_exit - t_entry).total_seconds())
            except Exception:
                holding_seconds = 0.0

            outcome = TradeOutcome(
                trade_id=str(trade_id),
                asset_class=asset_class,
                symbol=symbol,
                entry_timestamp=opened_at,
                exit_timestamp=closed_at,
                holding_seconds=holding_seconds,
                entry_reason=str(raw_payload.get("reason") or "UNKNOWN"),
                exit_reason="ACCOUNTING_CLOSE",
                entry_price=entry_price,
                exit_price=float(exit_price),
                quantity=quantity,
                realized_pnl=float(realized_pnl),
                max_favorable_excursion=float(raw_payload.get("mfe", raw_payload.get("max_favorable_excursion", 0.0)) or 0.0),
                max_adverse_excursion=float(raw_payload.get("mae", raw_payload.get("max_adverse_excursion", 0.0)) or 0.0),
                win_loss="WIN" if float(realized_pnl) > 0 else "LOSS",
                side=side,
                amount_traded=round(entry_price * quantity, 8),
                engine_mode=str(raw_payload.get("engine_mode") or "SAFE").upper(),
                broker_mode=str(trade_record.get("broker_mode") or "UNKNOWN").upper(),
            )
            self._legacy_trade_outcome_ledger.append_trade(outcome)
        except Exception as exc:
            logging.getLogger(__name__).warning("Legacy trade outcome append failed for %s: %s", trade_id, exc)

    def get_open_trades(
        self,
        session_id: str,
    ) -> list[dict[str, Any]]:

        return (
            self.persistence.trades
            .get_open_trades(session_id)
        )

    def get_all_session_trades(
        self,
        session_id: str,
    ) -> list[dict[str, Any]]:

        return (
            self.persistence.trades
            .get_all_session_trades(session_id)
        )

    def trade_exists(
        self,
        session_id: str,
        symbol: str,
        direction: str,
    ) -> bool:

        return (
            self.persistence.trades
            .trade_exists(
                session_id=session_id,
                symbol=symbol,
                direction=direction,
            )
        )