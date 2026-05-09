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
            f"API Health:              {contract.api_health}",
            f"Reconnect State:         {contract.reconnect_state}",
            f"Account Readiness:       {contract.account_readiness}",
            f"Missing Credentials:     {self._format_bool(contract.missing_credentials)}",
            f"Latency MS:              {contract.latency_ms:.2f}",
            f"Readiness Status:        {contract.readiness_status}",
            (
                "Readiness Reasons:       "
                f"{', '.join(contract.readiness_reasons) if contract.readiness_reasons else 'NONE'}"
            ),
            (
                "Supported Assets:       "
                f"{', '.join(contract.supported_assets) if contract.supported_assets else 'NONE'}"
            ),
            "==============================",
        ]

        return "\n".join(lines)

    @staticmethod
    def _format_bool(value: bool) -> str:
        return "YES" if value else "NO"
