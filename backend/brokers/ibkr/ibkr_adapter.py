from typing import Any


class IBKRAdapter:
    """Placeholder IBKR adapter.

    Tier-1 roadmap excludes IBKR. This adapter must never report ready or
    connected as if a real IB Gateway session exists.
    """

    IMPLEMENTATION_STATUS = "PLACEHOLDER"

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7497,
        client_id: int = 1,
        paper_trading: bool = True,
    ) -> None:

        self.host = host
        self.port = port
        self.client_id = client_id
        self.paper_trading = paper_trading

        self.connected = False
        self._placeholder = True

    def connect(self) -> bool:
        # Fail-closed: no IB Gateway / TWS session is established.
        self.connected = False
        self._placeholder = True
        return False

    def disconnect(self) -> None:
        self.connected = False

    def is_connected(self) -> bool:
        return False

    def get_account_snapshot(self) -> dict[str, Any]:

        return {
            "broker": "IBKR",
            "connected": False,
            "paper_trading": self.paper_trading,
            "equity": 0,
            "cash_balance": 0,
            "buying_power": 0,
            "implementation_status": self.IMPLEMENTATION_STATUS,
            "ibkr_ready": False,
            "placeholder": True,
        }

    def get_positions(self) -> list[dict[str, Any]]:
        return []

    def health_check(self) -> dict[str, Any]:

        return {
            "broker": "IBKR",
            "connected": False,
            "host": self.host,
            "port": self.port,
            "client_id": self.client_id,
            "paper_trading": self.paper_trading,
            "ibkr_ready": False,
            "implementation_status": self.IMPLEMENTATION_STATUS,
            "placeholder": True,
        }
