from typing import Any


class IBKRAdapter:

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

    def connect(self) -> bool:
        self.connected = True
        return self.connected

    def disconnect(self) -> None:
        self.connected = False

    def is_connected(self) -> bool:
        return self.connected

    def get_account_snapshot(self) -> dict[str, Any]:

        return {
            "broker": "IBKR",
            "connected": self.connected,
            "paper_trading": self.paper_trading,
            "equity": 0,
            "cash_balance": 0,
            "buying_power": 0,
        }

    def get_positions(self) -> list[dict[str, Any]]:
        return []

    def health_check(self) -> dict[str, Any]:

        return {
            "broker": "IBKR",
            "connected": self.connected,
            "host": self.host,
            "port": self.port,
            "client_id": self.client_id,
            "paper_trading": self.paper_trading,
            "ibkr_ready": True,
        }
