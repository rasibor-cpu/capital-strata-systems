from typing import Any, Dict, Iterable, Optional
import os

from backend.runtime.broker_credential_diagnostics import diagnose_broker_credentials
from backend.runtime.capital_state import classify_capital_state


class RealBalanceEngine:
    """
    Fetches and normalizes real broker balances.

    PCNRASS-safe:
    - fail-closed
    - no order execution
    - no fake live balances
    - diagnostic source labels preserved for dashboard review
    """

    def __init__(self, selected_broker: str, broker_adapter: Any):
        self.selected_broker = (selected_broker or "").upper()
        self.adapter = broker_adapter

    def get_balance(self) -> Dict[str, Any]:
        try:
            if self.selected_broker == "OANDA":
                return self._get_oanda_balance()

            if self.selected_broker == "COINBASE":
                return self._get_coinbase_balance()

            return self._default_balance("UNSUPPORTED_BROKER")
        except Exception as e:
            return self._default_balance(f"ERROR_{str(e)[:60]}")

    # ---------------------------
    # OANDA
    # ---------------------------
    def _get_oanda_balance(self) -> Dict[str, Any]:
        if not self.adapter:
            return self._default_balance("NO_OANDA_ADAPTER")

        summary = self.adapter.get_account_summary()

        if not isinstance(summary, dict) or not summary.get("ok"):
            return self._default_balance("OANDA_SUMMARY_NOT_OK")

        extracted = self.adapter.extract_balance_nav(summary)

        return self._with_capital_state({
            "balance": self._to_float(extracted.get("balance")),
            "equity": self._to_float(extracted.get("nav")),
            "source": "OANDA",
            "balance_status": "AVAILABLE",
            "drawdown_status": "AVAILABLE",
            "drawdown_reason": "",
        })

    # ---------------------------
    # COINBASE
    # ---------------------------
    def _get_coinbase_balance(self) -> Dict[str, Any]:
        if not self.adapter:
            return self._default_balance("COINBASE_BALANCE_UNAVAILABLE")

        accounts_payload = self._call_first_available(
            self.adapter,
            [
                "get_accounts",
                "list_accounts",
            ],
        )

        if accounts_payload is None:
            account_balance_payload = self._call_first_available(
                self.adapter,
                [
                    "get_account_balance",
                    "get_balance",
                    "get_live_balance",
                    "get_portfolio_balance",
                    "get_account",
                ],
            )
            parsed_direct = self._extract_balance_from_payload(account_balance_payload)
            if parsed_direct is not None and parsed_direct > 0:
                return self._with_capital_state({
                    "balance": parsed_direct,
                    "equity": parsed_direct,
                    "source": "COINBASE_DIRECT_BALANCE",
                    "balance_status": "AVAILABLE",
                    "drawdown_status": "AVAILABLE",
                    "drawdown_reason": "",
                })

            return self._default_balance("COINBASE_NO_BALANCE_METHOD_VALUE")

        accounts = self._extract_accounts(accounts_payload)

        if not accounts:
            return self._default_balance("COINBASE_NO_ACCOUNTS_RETURNED")

        total = 0.0
        valued_count = 0

        for account in accounts:
            balance = self._extract_balance_from_payload(account)
            if balance is not None and balance > 0:
                total += balance
                valued_count += 1

        if total <= 0:
            return self._with_capital_state(
                {
                    "balance": 0.0,
                    "equity": 0.0,
                    "source": f"COINBASE_ZERO_BALANCE_FROM_{len(accounts)}_ACCOUNTS",
                    "balance_status": "AVAILABLE",
                    "drawdown_status": "NOT_COMPUTABLE",
                    "drawdown_reason": "Zero funded account",
                }
            )

        return self._with_capital_state({
            "balance": float(total),
            "equity": float(total),
            "source": "COINBASE",
            "account_count": len(accounts),
            "valued_count": valued_count,
            "balance_status": "AVAILABLE",
            "drawdown_status": "AVAILABLE",
            "drawdown_reason": "",
        })

    # ---------------------------
    # Helpers
    # ---------------------------
    def _call_first_available(self, obj: Any, method_names: Iterable[str]) -> Any:
        for method_name in method_names:
            method = getattr(obj, method_name, None)
            if not callable(method):
                continue
            try:
                return method()
            except Exception as e:
                return {
                    "ok": False,
                    "error": f"{method_name}: {str(e)[:120]}",
                    "source": f"{method_name}_ERROR",
                }
        return None

    def _extract_accounts(self, payload: Any) -> list[dict[str, Any]]:
        payload = self._to_plain(payload)

        if isinstance(payload, dict):
            accounts = (
                payload.get("accounts")
                or payload.get("data")
                or payload.get("results")
                or []
            )
        elif isinstance(payload, list):
            accounts = payload
        else:
            accounts = []

        return [acct for acct in accounts if isinstance(acct, dict)]

    def _extract_balance_from_payload(self, payload: Any) -> Optional[float]:
        payload = self._to_plain(payload)

        if payload is None:
            return None

        if isinstance(payload, (int, float)):
            value = float(payload)
            return value if value > 0 else None

        if isinstance(payload, str):
            value = self._to_float(payload)
            return value if value > 0 else None

        if isinstance(payload, list):
            total = 0.0
            found = False
            for item in payload:
                value = self._extract_balance_from_payload(item)
                if value is not None and value > 0:
                    total += value
                    found = True
            return total if found and total > 0 else None

        if isinstance(payload, dict):
            for key in (
                "balance",
                "cash",
                "equity",
                "available",
                "total",
                "portfolio_balance",
                "account_balance",
                "available_balance",
                "balance_usd",
                "value",
                "amount",
            ):
                if key not in payload:
                    continue

                value = payload.get(key)

                if isinstance(value, dict):
                    value = (
                        value.get("value")
                        or value.get("amount")
                        or value.get("balance")
                        or value.get("cash")
                    )

                parsed = self._to_float(value)
                if parsed > 0:
                    return parsed

            accounts = (
                payload.get("accounts")
                or payload.get("data")
                or payload.get("results")
            )
            if isinstance(accounts, list):
                return self._extract_balance_from_payload(accounts)

        return None

    def _to_plain(self, obj: Any) -> Any:
        if obj is None:
            return None

        if isinstance(obj, (dict, list, str, int, float, bool)):
            return obj

        if hasattr(obj, "to_dict"):
            try:
                return obj.to_dict()
            except Exception:
                pass

        if hasattr(obj, "__dict__"):
            try:
                return {
                    key: self._to_plain(value)
                    for key, value in vars(obj).items()
                    if not key.startswith("_")
                }
            except Exception:
                pass

        return obj

    def _to_float(self, value: Any) -> float:
        try:
            return float(value or 0.0)
        except Exception:
            return 0.0

    def _default_balance(self, reason: str = "DEFAULT") -> Dict[str, Any]:
        payload = {
            "balance": None,
            "equity": None,
            "source": reason,
            "balance_status": "NOT_AVAILABLE",
            "drawdown_status": "NOT_COMPUTABLE",
            "drawdown_reason": "Broker balance unavailable",
        }
        return self._with_capital_state(payload)

    def _with_capital_state(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        broker = str(self.selected_broker or "NONE").upper()
        mode = "live" if broker in {"COINBASE", "OANDA"} else "paper"
        diagnostics = diagnose_broker_credentials(str(broker).lower(), env=os.environ).as_dict()
        classification = classify_capital_state(
            selected_broker=broker,
            broker_mode=mode,
            balance=payload.get("balance"),
            equity=payload.get("equity"),
            balance_status=str(payload.get("balance_status", "NOT_AVAILABLE")),
            drawdown_reason=str(payload.get("drawdown_reason", "")),
            credential_diagnostics=diagnostics,
        )
        merged = {**payload, **classification}
        if merged.get("trade_gate_decision") == "BLOCK":
            merged["drawdown_status"] = "NOT_COMPUTABLE"
            if not str(merged.get("drawdown_reason", "")).strip():
                merged["drawdown_reason"] = "Capital state unavailable"
        return merged
