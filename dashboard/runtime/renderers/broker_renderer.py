from __future__ import annotations

from dashboard.runtime.render_contracts.broker_render_contract import (
    BrokerRenderContract,
)


class BrokerRenderer:
    """
    PCNRASS-safe pure broker renderer.
    """

    def render(self, contract: BrokerRenderContract) -> str:
        lines = [
            "==============================",
            " BROKER STATE",
            "==============================",
            f"Selected Broker:         {contract.selected_broker}",
            f"Broker Mode:             {contract.broker_mode}",
            f"Connected:               {self._format_bool(contract.connected)}",
            (
                "Live Trading Enabled:    "
                f"{self._format_bool(contract.live_trading_enabled)}"
            ),
            f"Last Heartbeat:          {contract.last_heartbeat or 'NONE'}",
            "==============================",
        ]

        return "\n".join(lines)

    @staticmethod
    def _format_bool(value: bool) -> str:
        return "YES" if value else "NO"
