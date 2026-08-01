"""Deterministic event classification."""

from __future__ import annotations

import re

from backend.intelligence.external_events.constants import EVENT_CATEGORIES

_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("monetary_policy", ("fomc", "monetary policy", "policy rate", "mpc", "central bank")),
    ("interest_rates", ("interest rate", "rate hike", "rate cut", "federal funds", "mpr")),
    ("inflation", ("inflation", "cpi", "pce", "consumer price")),
    ("employment", ("nonfarm", "unemployment", "payroll", "jobs report", "employment")),
    ("gdp_growth", ("gdp", "gross domestic", "growth print")),
    ("currency_intervention", ("fx intervention", "currency intervention", "naira intervention")),
    ("fiscal_policy", ("budget", "fiscal", "stimulus bill")),
    ("sovereign_debt", ("sovereign debt", "bond auction", "dmo", "treasury auction")),
    ("regulatory_action", ("sec charges", "enforcement action", "regulatory", "cease and desist")),
    ("issuer_earnings", ("earnings", "quarterly results", "q1 results", "q2 results")),
    ("dividends", ("dividend", "dividend declaration")),
    ("corporate_actions", ("stock split", "buyback", "share repurchase")),
    ("mergers_acquisitions", ("merger", "acquisition", "takeover")),
    ("capital_raising", ("ipo", "follow-on offering", "rights issue", "capital raise")),
    ("credit_events", ("default", "bankruptcy", "credit event", "restructuring")),
    ("ratings_changes", ("downgrade", "upgrade", "credit rating")),
    ("market_disruption", ("trading halt", "circuit breaker", "market disruption")),
    ("exchange_outage", ("exchange outage", "matching engine", "ngx outage", "nyse outage")),
    ("broker_outage", ("broker outage", "broker downtime")),
    ("litigation", ("lawsuit", "litigation", "court ruling")),
    ("sanctions_geopolitics", ("sanction", "geopolitic", "embargo")),
    ("commodity_supply_demand", ("opec", "crude supply", "inventory draw")),
    ("options_futures_expiration", ("options expiration", "futures expiry", "opex")),
    ("volatility_event", ("volatility spike", "vix surge")),
    ("crypto_regulation", ("crypto regulation", "digital asset regulation", "stablecoin bill")),
    ("digital_asset_protocol_exchange", ("protocol upgrade", "chain halt", "exchange listing", "coinbase announce")),
]


def classify_event(title: str, summary: str = "") -> str:
    text = f"{title} {summary}".casefold()
    text = re.sub(r"\s+", " ", text)
    for category, needles in _RULES:
        if any(needle in text for needle in needles):
            return category
    return "unknown"


def assert_known_category(category: str) -> str:
    value = str(category or "unknown")
    if value not in EVENT_CATEGORIES:
        return "unknown"
    return value
