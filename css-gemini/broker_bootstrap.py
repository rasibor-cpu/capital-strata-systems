"""
broker_bootstrap.py
─────────────────────────────────────────────────────────────────
Broker discovery and selection at engine startup.

On startup:
  1. Attempts to connect to all configured brokers
  2. Reports health, latency, and available balance for each
  3. Presents an interactive selection menu (CLI)
  4. Returns the selected connector(s) ready for use

Can be run standalone:  python broker_bootstrap.py
Or imported by main.py for programmatic startup.
"""

import logging
import time
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

import config
from connectors import BaseConnector, BinanceConnector, CoinbaseConnector, IBKRConnector

logger = logging.getLogger(__name__)

RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
DIM    = "\033[2m"


@dataclass
class BrokerStatus:
    name:         str
    display_name: str
    asset_classes: list
    connected:    bool
    latency_ms:   float
    balance_usd:  float
    error:        str
    connector:    Optional[BaseConnector]


BROKER_DEFINITIONS = [
    {
        "name":          "binance",
        "display_name":  "Binance",
        "asset_classes": ["Crypto (Spot)", "Crypto (Futures)"],
        "cls":           BinanceConnector,
        "test_symbol":   "BTC/USDT",
    },
    {
        "name":          "coinbase",
        "display_name":  "Coinbase Advanced",
        "asset_classes": ["Crypto (Spot)"],
        "cls":           CoinbaseConnector,
        "test_symbol":   "BTC/USDT",
    },
    {
        "name":          "ibkr",
        "display_name":  "Interactive Brokers",
        "asset_classes": ["FX", "Futures", "Options", "Stocks"],
        "cls":           IBKRConnector,
        "test_symbol":   "EUR/USD",
    },
]


class BrokerBootstrap:

    def __init__(self):
        self.statuses: List[BrokerStatus] = []

    # ──────────────────────────────────────────
    # DISCOVERY
    # ──────────────────────────────────────────

    def discover(self, silent: bool = False) -> List[BrokerStatus]:
        """
        Attempts connection to all brokers. Returns list of BrokerStatus.
        """
        if not silent:
            self._print_header()

        self.statuses = []
        for broker in BROKER_DEFINITIONS:
            status = self._probe_broker(broker, silent)
            self.statuses.append(status)

        return self.statuses

    def _probe_broker(self, broker: dict, silent: bool) -> BrokerStatus:
        name  = broker["name"]
        cls   = broker["cls"]
        sym   = broker["test_symbol"]

        if not silent:
            print(f"  {DIM}Connecting to {broker['display_name']}...{RESET}", end="", flush=True)

        start = time.monotonic()
        try:
            connector = cls()
            # Test latency with a ticker call
            connector.get_ticker(sym)
            latency = (time.monotonic() - start) * 1000

            # Get balance
            try:
                bal = connector.get_balance()
                balance = bal.get("total_usd", 0.0)
            except Exception:
                balance = 0.0

            status = BrokerStatus(
                name=name,
                display_name=broker["display_name"],
                asset_classes=broker["asset_classes"],
                connected=True,
                latency_ms=round(latency, 1),
                balance_usd=balance,
                error="",
                connector=connector,
            )
            if not silent:
                print(f"\r  {GREEN}✓{RESET} {broker['display_name']:<28} "
                      f"latency={latency:.0f}ms  balance=${balance:,.2f}")

        except Exception as e:
            status = BrokerStatus(
                name=name,
                display_name=broker["display_name"],
                asset_classes=broker["asset_classes"],
                connected=False,
                latency_ms=0.0,
                balance_usd=0.0,
                error=str(e)[:60],
                connector=None,
            )
            if not silent:
                print(f"\r  {RED}✗{RESET} {broker['display_name']:<28} {DIM}{status.error}{RESET}")

        return status

    # ──────────────────────────────────────────
    # INTERACTIVE SELECTION (CLI)
    # ──────────────────────────────────────────

    def interactive_select(self) -> Dict[str, BaseConnector]:
        """
        Shows a menu of available brokers and lets the user pick
        which ones to activate for this session.
        Returns dict of {broker_name: connector}.
        """
        connected = [s for s in self.statuses if s.connected]

        if not connected:
            print(f"\n  {RED}No brokers connected. Check API keys and network.{RESET}\n")
            return {}

        print(f"\n{BOLD}{CYAN}  ┌─ BROKER SELECTION ─────────────────────────────┐{RESET}")
        for i, s in enumerate(connected, 1):
            classes = ", ".join(s.asset_classes)
            print(f"  {CYAN}│{RESET}  [{i}] {BOLD}{s.display_name:<22}{RESET} "
                  f"${s.balance_usd:>10,.2f}   {DIM}{classes}{RESET}")
        print(f"  {CYAN}│{RESET}  [A] All connected brokers")
        print(f"  {CYAN}└────────────────────────────────────────────────┘{RESET}\n")

        while True:
            try:
                raw = input(f"  {YELLOW}Select broker(s) [1-{len(connected)}/A]: {RESET}").strip().upper()
            except (EOFError, KeyboardInterrupt):
                raw = "A"

            if raw == "A":
                selected = connected
                break

            try:
                indices = [int(x.strip()) - 1 for x in raw.replace(",", " ").split()]
                selected = [connected[i] for i in indices if 0 <= i < len(connected)]
                if selected:
                    break
                print(f"  {RED}Invalid selection — try again.{RESET}")
            except (ValueError, IndexError):
                print(f"  {RED}Invalid input — enter numbers or A.{RESET}")

        result = {}
        print(f"\n  {GREEN}Active brokers:{RESET}")
        for s in selected:
            result[s.name] = s.connector
            print(f"    {GREEN}✓{RESET} {s.display_name}")

        print()
        return result

    # ──────────────────────────────────────────
    # AUTO SELECT (non-interactive / headless)
    # ──────────────────────────────────────────

    def auto_select(
        self,
        prefer: Optional[List[str]] = None,
    ) -> Dict[str, BaseConnector]:
        """
        Auto-selects brokers without user interaction.
        prefer: list of broker names to prioritise, e.g. ['binance', 'ibkr']
        Falls back to all connected brokers if prefer list not available.
        """
        connected = {s.name: s for s in self.statuses if s.connected}

        if not connected:
            logger.error("No brokers available")
            return {}

        if prefer:
            selected = {name: connected[name].connector
                        for name in prefer if name in connected}
            if selected:
                return selected

        return {name: s.connector for name, s in connected.items()}

    # ──────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────

    def _print_header(self):
        print(f"\n{BOLD}{CYAN}")
        print("  ╔══════════════════════════════════════════════╗")
        print("  ║         TRADING ENGINE — BROKER STARTUP      ║")
        print("  ╚══════════════════════════════════════════════╝")
        print(f"{RESET}")
        print(f"  {DIM}Probing configured brokers...{RESET}\n")

    def summary(self) -> dict:
        return {
            s.name: {
                "connected":   s.connected,
                "latency_ms":  s.latency_ms,
                "balance_usd": s.balance_usd,
                "error":       s.error,
            }
            for s in self.statuses
        }


# ══════════════════════════════════════════════════════════════
# STANDALONE  (run directly to test connectivity)
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)

    bootstrap = BrokerBootstrap()
    bootstrap.discover()
    selected = bootstrap.interactive_select()

    if selected:
        print(f"  Ready to trade with: {list(selected.keys())}")
    else:
        print("  No brokers selected — exiting.")
