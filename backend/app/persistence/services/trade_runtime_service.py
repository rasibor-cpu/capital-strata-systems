from datetime import datetime
from decimal import Decimal
from typing import Any

from backend.app.persistence.services.persistence_service import (
    PersistenceService,
)


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

    def __init__(self) -> None:
        self.persistence = PersistenceService()

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

        closed_at = (
            datetime.utcnow().isoformat()
        )

        try:
            trade_record = self.persistence.trades.get_trade(trade_id)
            if trade_record:
                from analytics.trade_outcome_ledger import TradeOutcomeLedger, TradeOutcome
                import json

                opened_at = trade_record.get("opened_at", closed_at)
                try:
                    t_entry = datetime.fromisoformat(opened_at.replace("Z", "+00:00"))
                    t_exit = datetime.fromisoformat(closed_at.replace("Z", "+00:00"))
                    holding_seconds = (t_exit - t_entry).total_seconds()
                except Exception:
                    holding_seconds = 0.0

                pnl_val = float(realized_pnl)
                win_loss = "WIN" if pnl_val > 0 else ("LOSS" if pnl_val < 0 else "BREAK_EVEN")

                entry_reason = "UNKNOWN"
                asset_class = "UNKNOWN"
                raw = trade_record.get("raw_payload_json")
                if raw:
                    try:
                        payload = json.loads(raw)
                        entry_reason = payload.get("reason", "UNKNOWN")
                        asset_class = payload.get("asset_class", "UNKNOWN")
                    except Exception:
                        pass
                
                symbol = trade_record.get("symbol", "UNKNOWN").upper()

                # Infer asset_class
                if asset_class == "UNKNOWN":
                    if any(x in symbol for x in ["BTC", "ETH", "SOL", "ADA", "DOGE"]):
                        asset_class = "CRYPTO"
                    elif any(x in symbol for x in ["EUR_", "USD_", "GBP_", "JPY", "CAD", "AUD", "NZD", "CHF"]):
                        asset_class = "FX"
                    elif any(x in symbol for x in ["GC", "CL", "ES", "NQ", "YM", "ZB", "ZN"]):
                        asset_class = "FUTURES"
                    elif "-C-" in symbol or "-P-" in symbol:
                        asset_class = "OPTIONS"

                # Infer side
                raw_side = trade_record.get("direction", "UNKNOWN").upper()
                if raw_side in ["LONG", "BUY", "CALL"]:
                    inferred_side = "BUY"
                elif raw_side in ["SHORT", "SELL", "PUT"]:
                    inferred_side = "SELL"
                else:
                    inferred_side = "UNKNOWN"

                entry_price_val = float(trade_record.get("entry_price", 0.0))
                quantity_val = float(trade_record.get("quantity", 0.0))
                amount_traded = entry_price_val * quantity_val

                broker_mode = trade_record.get("broker_mode", "UNKNOWN")
                
                engine_mode = "UNKNOWN"
                if raw:
                    try:
                        payload = json.loads(raw)
                        engine_mode = payload.get("engine_mode", "UNKNOWN")
                    except Exception:
                        pass
                
                # Fetch recent snapshot for balance if possible
                try:
                    from backend.app.persistence.services.pnl_runtime_service import PnlRuntimeService
                    pnl_svc = PnlRuntimeService()
                    snapshots = pnl_svc.get_snapshots_by_session(trade_record.get("session_id", ""))
                    if snapshots:
                        cumulative_account_balance = float(snapshots[-1].get("cumulative_account_balance", 0.0))
                    else:
                        cumulative_account_balance = 0.0
                except Exception:
                    cumulative_account_balance = 0.0

                outcome = TradeOutcome(
                    trade_id=trade_id,
                    asset_class=asset_class,
                    symbol=symbol,
                    entry_timestamp=opened_at,
                    exit_timestamp=closed_at,
                    holding_seconds=holding_seconds,
                    entry_reason=entry_reason,
                    exit_reason="ACCOUNTING_CLOSE",
                    entry_price=entry_price_val,
                    exit_price=float(exit_price),
                    quantity=quantity_val,
                    realized_pnl=pnl_val,
                    max_favorable_excursion=0.0,
                    max_adverse_excursion=0.0,
                    win_loss=win_loss,
                    side=inferred_side,
                    amount_traded=amount_traded,
                    cumulative_account_balance=cumulative_account_balance,
                    engine_mode=engine_mode,
                    broker_mode=broker_mode
                )
                TradeOutcomeLedger().append_trade(outcome)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Phase 126B Analytics Capture Failed: {e}")

        self.persistence.trades.close_trade(
            trade_id=trade_id,
            exit_price=exit_price,
            realized_pnl=realized_pnl,
            closed_at=closed_at,
        )

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