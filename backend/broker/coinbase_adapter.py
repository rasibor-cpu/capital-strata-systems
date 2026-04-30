# ADD THIS METHOD INSIDE CoinbaseAdapter CLASS

def get_live_balance(self) -> Dict[str, Any]:
    """
    Phase 3B-3: Live capital retrieval (PCNRASS SAFE)

    Attempts to extract total account balance from CoinbaseExecutor.
    """

    if self.paper_mode:
        return {
            "ok": True,
            "balance": 0.0,
            "source": "paper_mode",
        }

    if self.executor is None:
        self.connect()

    if self.executor is None:
        return {
            "ok": False,
            "error": "Executor not available",
            "balance": None,
        }

    try:
        # --- Try common Coinbase executor methods ---
        for method_name in ["get_accounts", "list_accounts", "get_balance"]:
            method = getattr(self.executor, method_name, None)

            if not callable(method):
                continue

            result = method()

            # --- Case 1: direct float ---
            if isinstance(result, (int, float)):
                return {
                    "ok": True,
                    "balance": float(result),
                    "source": f"executor.{method_name}",
                }

            # --- Case 2: dict ---
            if isinstance(result, dict):
                for key in ["balance", "total", "equity", "portfolio_balance"]:
                    val = result.get(key)
                    try:
                        if val is not None:
                            return {
                                "ok": True,
                                "balance": float(val),
                                "source": f"{method_name}.{key}",
                            }
                    except:
                        pass

            # --- Case 3: list of accounts ---
            if isinstance(result, list):
                total = 0.0

                for acct in result:
                    if not isinstance(acct, dict):
                        continue

                    for key in ["balance", "available_balance", "cash"]:
                        val = acct.get(key)

                        if isinstance(val, dict):
                            val = val.get("value") or val.get("amount")

                        try:
                            total += float(val or 0)
                        except:
                            pass

                if total > 0:
                    return {
                        "ok": True,
                        "balance": total,
                        "source": f"{method_name}.accounts_sum",
                    }

        return {
            "ok": False,
            "error": "No balance method succeeded",
            "balance": None,
        }

    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "balance": None,
        }