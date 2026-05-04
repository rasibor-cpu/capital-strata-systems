from typing import Dict, Any


class RealBalanceEngine:
    """
    Fetches and normalizes real broker balances.
    PCNRASS-safe: fail-closed, no crashes.
    """

    def __init__(self, selected_broker: str, broker_adapter: Any):
        self.selected_broker = (selected_broker or "").upper()
        self.adapter = broker_adapter

    def get_balance(self) -> Dict[str, float]:
        try:
            if self.selected_broker == "OANDA":
                return self._get_oanda_balance()

            if self.selected_broker == "COINBASE":
                return self._get_coinbase_balance()

            return self._default_balance()

        except Exception as e:
            return {
                "balance": 0.0,
                "equity": 0.0,
                "source": f"ERROR_{str(e)[:30]}",
            }

    # ---------------------------
    # OANDA
    # ---------------------------
    def _get_oanda_balance(self):
        if not self.adapter:
            return self._default_balance()

        summary = self.adapter.get_account_summary()

        if not summary.get("ok"):
            return self._default_balance()

        extracted = self.adapter.extract_balance_nav(summary)

        return {
            "balance": float(extracted.get("balance", 0.0)),
            "equity": float(extracted.get("nav", 0.0)),
            "source": "OANDA",
        }

    # ---------------------------
    # COINBASE
    # ---------------------------
    def _get_coinbase_balance(self):
        if not self.adapter:
            return self._default_balance()

        try:
            accounts = self.adapter.get_accounts()

            total = 0.0

            for acc in accounts:
                balance = float(acc.get("balance", 0.0))
                total += balance

            return {
                "balance": total,
                "equity": total,
                "source": "COINBASE",
            }

        except Exception:
            return self._default_balance()

    # ---------------------------
    def _default_balance(self):
        return {
            "balance": 0.0,
            "equity": 0.0,
            "source": "DEFAULT",
        }