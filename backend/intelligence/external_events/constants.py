"""Trust tiers and safety constants for MI-EXT-001."""

from __future__ import annotations

SCHEMA_VERSION = "css.mi_ext_001.external_event.v1"
PARSER_VERSION = "mi_ext_001.parser.v1"
CATALOGUE_SCHEMA_VERSION = "css.mi_ext_001.source_catalogue.v1"

ADVISORY_ONLY = True
EXECUTION_ALLOWED = False

UNKNOWN = "UNKNOWN"
UNAVAILABLE = "UNAVAILABLE"


class TrustTier:
    TIER_1_OFFICIAL_PRIMARY = "TIER_1_OFFICIAL_PRIMARY"
    TIER_2_VERIFIED_INSTITUTIONAL = "TIER_2_VERIFIED_INSTITUTIONAL"
    TIER_3_SECONDARY_NEWS = "TIER_3_SECONDARY_NEWS"
    TIER_4_UNVERIFIED_SOCIAL = "TIER_4_UNVERIFIED_SOCIAL"

    ORDER = (
        TIER_1_OFFICIAL_PRIMARY,
        TIER_2_VERIFIED_INSTITUTIONAL,
        TIER_3_SECONDARY_NEWS,
        TIER_4_UNVERIFIED_SOCIAL,
    )

    @classmethod
    def rank(cls, tier: str) -> int:
        try:
            return cls.ORDER.index(str(tier))
        except ValueError:
            return len(cls.ORDER)


FRESHNESS_STATES = ("FRESH", "AGING", "STALE", "EXPIRED", "FUTURE", "UNKNOWN")

EVENT_CATEGORIES = (
    "monetary_policy",
    "inflation",
    "employment",
    "gdp_growth",
    "interest_rates",
    "currency_intervention",
    "fiscal_policy",
    "sovereign_debt",
    "regulatory_action",
    "issuer_earnings",
    "dividends",
    "corporate_actions",
    "mergers_acquisitions",
    "capital_raising",
    "credit_events",
    "ratings_changes",
    "market_disruption",
    "exchange_outage",
    "broker_outage",
    "litigation",
    "sanctions_geopolitics",
    "commodity_supply_demand",
    "options_futures_expiration",
    "volatility_event",
    "crypto_regulation",
    "digital_asset_protocol_exchange",
    "unknown",
)

# Default freshness windows (seconds) by category family
DEFAULT_FRESHNESS_WINDOWS_SEC = {
    "real_time_market_alert": {"fresh": 300, "aging": 900, "stale": 3600, "expired": 21600},
    "regulatory_announcement": {"fresh": 3600, "aging": 21600, "stale": 86400, "expired": 604800},
    "issuer_filing": {"fresh": 3600, "aging": 43200, "stale": 259200, "expired": 2592000},
    "macroeconomic_release": {"fresh": 1800, "aging": 21600, "stale": 172800, "expired": 1209600},
    "central_bank_decision": {"fresh": 1800, "aging": 43200, "stale": 604800, "expired": 2592000},
    "daily_research": {"fresh": 21600, "aging": 86400, "stale": 259200, "expired": 1209600},
    "weekly_outlook": {"fresh": 86400, "aging": 345600, "stale": 1209600, "expired": 5184000},
    "long_form_analysis": {"fresh": 259200, "aging": 1209600, "stale": 5184000, "expired": 15552000},
    "default": {"fresh": 3600, "aging": 21600, "stale": 86400, "expired": 604800},
}
