"""Read-only broker integration capability catalog.

Discovery metadata only: listing a provider never grants credentials, market
entitlements, regulatory eligibility or order-execution authorization.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ReadOnlyBrokerCapability:
    provider: str
    asset_classes: tuple[str, ...]
    market_data_candidate: bool
    account_data_candidate: bool
    integration_status: str
    execution_allowed: bool = False


# Candidate capabilities require separate verification against each provider's
# current API, account permissions and jurisdiction before activation.
READ_ONLY_BROKER_CATALOG = {
    "questrade": ReadOnlyBrokerCapability(
        "questrade", ("equities", "options"), True, True, "integration_incomplete"
    ),
    "binance": ReadOnlyBrokerCapability(
        "binance", ("spot_crypto",), True, True, "authorization_pending"
    ),
    "coinbase": ReadOnlyBrokerCapability(
        "coinbase", ("spot_crypto",), True, True, "verification_pending"
    ),
    "oanda": ReadOnlyBrokerCapability(
        "oanda", ("fx",), True, True, "verification_pending"
    ),
    "alpaca": ReadOnlyBrokerCapability(
        "alpaca", ("equities", "crypto"), True, True, "verification_pending"
    ),
    "interactive_brokers": ReadOnlyBrokerCapability(
        "interactive_brokers", ("equities", "options", "futures", "fx"),
        True, True, "not_integrated"
    ),
}


def list_read_only_broker_candidates() -> tuple[ReadOnlyBrokerCapability, ...]:
    return tuple(READ_ONLY_BROKER_CATALOG[key] for key in sorted(READ_ONLY_BROKER_CATALOG))


def get_read_only_broker_candidate(provider: str) -> ReadOnlyBrokerCapability:
    key = str(provider or "").strip().lower()
    return READ_ONLY_BROKER_CATALOG[key]
