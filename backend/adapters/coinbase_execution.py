# backend/adapters/coinbase_execution.py
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Tuple

from backend.adapters.coinbase_adapter import CoinbaseAdapter


@dataclass(frozen=True)
class RiskLimits:
    risk_per_trade_usd: float = 2.0
    max_daily_loss_usd: float = 10.0
    max_concurrent_positions: int = 5


class CoinbaseExecutionGate:
    """
    CSS — Coinbase Execution Gate
    - Live position sync with dust threshold
    - FIFO realized PnL from fills (idempotent)
    - Duplicate guard
    - Fail-closed execution enable
    """

    # Anything below this is treated as "dust" and not a position
    DUST_THRESHOLDS = {
        "BTC": 0.000001,  # 1e-6 BTC
    }

    def __init__(
        self,
        adapter: CoinbaseAdapter,
        limits: RiskLimits = RiskLimits(),
        state_path: str = "backend/state/coinbase_exec_state.json",
    ):
        self.adapter = adapter
        self.limits = limits
        self.state_path = os.path.join(os.getcwd(), state_path)
        self._ensure_state_file()

    # ---------------- STATE ----------------

    def _ensure_state_file(self):
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        if not os.path.exists(self.state_path):
            self._write_state(
                {
                    "daily_pnl_usd": 0.0,
                    "open_positions_count": 0,
                    "seen_order_keys": [],
                    "processed_fill_ids": [],
                    "fifo_inventory": [],
                }
            )

    def _read_state(self) -> Dict[str, Any]:
        with open(self.state_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write_state(self, s: Dict[str, Any]):
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(s, f, indent=2)

    # ---------------- POSITION SYNC ----------------

    def _is_dust(self, currency: str, value: float) -> bool:
        thr = self.DUST_THRESHOLDS.get(currency)
        if thr is None:
            # default: anything > 0 counts
            return False
        return value < thr

    def sync_open_positions(self) -> int:
        """
        Count non-fiat/non-stable holdings above dust threshold.
        """
        accounts = self.adapter.get_accounts()
        count = 0

        for acct in accounts.get("accounts", []):
            bal = acct.get("available_balance", {})
            currency = bal.get("currency")
            value = bal.get("value")

            if not currency or value is None:
                continue

            if currency in ["USD", "USDC", "CAD"]:
                continue

            try:
                v = float(value)
            except Exception:
                continue

            if v <= 0:
                continue

            if self._is_dust(currency, v):
                continue

            count += 1

        s = self._read_state()
        s["open_positions_count"] = count
        self._write_state(s)
        return count

    # ---------------- PNL / FILLS ----------------

    def _fill_unique_id(self, fill: Dict[str, Any]) -> str:
        """
        Coinbase fills may provide trade_id and/or order_id.
        Use trade_id if present; else fallback to order_id+time+size+price.
        """
        tid = fill.get("trade_id")
        if tid:
            return str(tid)
        oid = str(fill.get("order_id", ""))
        t = str(fill.get("trade_time", ""))
        s = str(fill.get("size", ""))
        p = str(fill.get("price", ""))
        return f"{oid}|{t}|{s}|{p}"

    def sync_realized_pnl(self, product_id: str = "BTC-USDC") -> float:
        """
        FIFO realized PnL using fills.
        Only processes new fills (idempotent).
        """
        fills = self.adapter._request("GET", "/api/v3/brokerage/orders/historical/fills")

        s = self._read_state()
        processed = set(s.get("processed_fill_ids", []))
        fifo_inventory: List[Dict[str, float]] = s.get("fifo_inventory", [])
        daily_pnl = float(s.get("daily_pnl_usd", 0.0))

        for fill in fills.get("fills", []):
            uid = self._fill_unique_id(fill)
            if uid in processed:
                continue

            if fill.get("product_id") != product_id:
                continue

            side = fill.get("side")
            size = float(fill.get("size", 0) or 0)
            price = float(fill.get("price", 0) or 0)

            if size <= 0 or price <= 0:
                processed.add(uid)
                continue

            if side == "BUY":
                fifo_inventory.append({"size": size, "price": price})

            elif side == "SELL":
                remaining = size
                while remaining > 0 and fifo_inventory:
                    lot = fifo_inventory[0]
                    matched = min(remaining, lot["size"])
                    pnl = matched * (price - lot["price"])
                    daily_pnl += pnl

                    lot["size"] -= matched
                    remaining -= matched

                    if lot["size"] <= 0:
                        fifo_inventory.pop(0)

            processed.add(uid)

        s["processed_fill_ids"] = list(processed)[-2000:]
        s["fifo_inventory"] = fifo_inventory
        s["daily_pnl_usd"] = daily_pnl
        self._write_state(s)
        return daily_pnl

    # ---------------- GATES ----------------

    def _execution_enabled(self) -> bool:
        return os.getenv("COINBASE_EXECUTION_ENABLED", "false").lower() == "true"

    def _trade_date(self):
        return datetime.now().strftime("%Y-%m-%d")

    def _order_key(self, maker_user_id: str, trade_date: str, payload: Dict[str, Any]) -> str:
        canon = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        raw = f"{maker_user_id}|{trade_date}|{canon}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def _check_limits(self) -> Tuple[bool, str]:
        self.sync_open_positions()
        pnl = self.sync_realized_pnl()

        if pnl <= -abs(self.limits.max_daily_loss_usd):
            return False, f"BLOCK: daily loss limit breached ({pnl})"

        s = self._read_state()
        if s.get("open_positions_count", 0) >= self.limits.max_concurrent_positions:
            return False, "BLOCK: max concurrent positions reached"

        return True, "OK"

    # ---------------- EXECUTION ----------------

    def place_market_buy_quote(
        self,
        maker_user_id: str,
        product_id: str,
        quote_size_usd: str,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        payload = {"product_id": product_id, "side": "BUY", "quote_size": quote_size_usd, "order_type": "MARKET"}
        return self._execute(maker_user_id, payload, dry_run)

    def place_market_sell_base(
        self,
        maker_user_id: str,
        product_id: str,
        base_size: str,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        payload = {"product_id": product_id, "side": "SELL", "base_size": base_size, "order_type": "MARKET"}
        return self._execute(maker_user_id, payload, dry_run)

    def _execute(self, maker_user_id: str, payload: Dict[str, Any], dry_run: bool):
        trade_date = self._trade_date()
        order_key = self._order_key(maker_user_id, trade_date, payload)

        ok, msg = self._check_limits()
        if not ok:
            return {"status": "BLOCKED", "reason": msg}

        s = self._read_state()
        if order_key in s.get("seen_order_keys", []):
            return {"status": "BLOCKED", "reason": "duplicate order"}

        if dry_run:
            return {"status": "DRY_RUN", "payload": payload}

        if not self._execution_enabled():
            return {"status": "BLOCKED", "reason": "execution disabled"}

        resp = self.adapter.place_market_order(
            product_id=payload["product_id"],
            side=payload["side"],
            quote_size=payload.get("quote_size"),
            base_size=payload.get("base_size"),
        )

        s["seen_order_keys"].append(order_key)
        self._write_state(s)

        return {"status": "SUBMITTED", "response": resp}