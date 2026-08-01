"""Phase 189 — declared broker capability profiles and operational audit matrix."""

from __future__ import annotations

from typing import Any, Mapping

from backend.app.brokers.multi_broker_readiness.contracts import BrokerCapabilityProfile

# Explicit declarations only — nothing inferred at runtime.
CAPABILITY_PROFILES: dict[str, BrokerCapabilityProfile] = {
    "OANDA": BrokerCapabilityProfile(
        broker_type="OANDA",
        fx=True,
        cfds=True,
        indices=True,
        commodities=True,
        account_information=True,
        market_data=True,
        historical_data=True,
        streaming_quotes=True,
        paper_trading=True,
        live_trading=True,  # declared product support only
        margin=True,
        short_selling=False,
        options_chains=False,
        fractional_trading=False,
        corporate_actions=False,
        execution_authority=False,
    ),
    "COINBASE": BrokerCapabilityProfile(
        broker_type="COINBASE",
        crypto=True,
        account_information=True,
        market_data=True,
        historical_data=True,
        streaming_quotes=True,
        paper_trading=True,
        live_trading=True,
        margin=False,
        short_selling=False,
        options_chains=False,
        fractional_trading=True,
        corporate_actions=False,
        execution_authority=False,
    ),
    "IBKR": BrokerCapabilityProfile(
        broker_type="IBKR",
        equities=True,
        etfs=True,
        fx=True,
        futures=True,
        options=True,
        indices=True,
        commodities=True,
        account_information=False,  # placeholder — not implemented
        market_data=False,
        historical_data=False,
        streaming_quotes=False,
        paper_trading=True,  # stub flag only
        live_trading=False,
        margin=True,
        short_selling=True,
        options_chains=True,
        fractional_trading=False,
        corporate_actions=True,
        execution_authority=False,
    ),
    "BINANCE": BrokerCapabilityProfile(
        broker_type="BINANCE",
        crypto=True,
        account_information=True,
        market_data=True,
        historical_data=True,
        streaming_quotes=True,
        paper_trading=True,
        live_trading=True,
        margin=False,
        short_selling=False,
        options_chains=False,
        fractional_trading=True,
        corporate_actions=False,
        execution_authority=False,
    ),
    "QUESTRADE": BrokerCapabilityProfile(
        broker_type="QUESTRADE",
        equities=True,
        etfs=True,
        options=True,
        account_information=True,
        market_data=True,
        historical_data=True,
        streaming_quotes=False,
        paper_trading=False,
        live_trading=True,
        margin=True,
        short_selling=True,
        options_chains=True,
        fractional_trading=False,
        corporate_actions=True,
        execution_authority=False,
    ),
    "PLUGIN": BrokerCapabilityProfile(
        broker_type="PLUGIN",
        execution_authority=False,
    ),
}

BROKER_AUDIT_MATRIX: dict[str, dict[str, Any]] = {
    "OANDA": {
        "implementation_status": "PARTIAL",
        "authentication_model": "bearer_token_env",
        "connectivity": "live_ro_adapter+controlled_cert",
        "account_support": True,
        "market_data": True,
        "execution_support": False,
        "supported_asset_classes": CAPABILITY_PROFILES["OANDA"].supported_asset_classes(),
        "capability_profile": CAPABILITY_PROFILES["OANDA"].as_dict(),
        "certification_readiness": True,
        "evidence_readiness": True,
        "classification": "PARTIAL",
        "notes": "Phase 187A/188 RO stack mature; online contact needs credentials",
    },
    "COINBASE": {
        "implementation_status": "PARTIAL",
        "authentication_model": "cdp_jwt_pem",
        "connectivity": "live_ro_historical_pass",
        "account_support": True,
        "market_data": True,
        "execution_support": False,
        "supported_asset_classes": CAPABILITY_PROFILES["COINBASE"].supported_asset_classes(),
        "capability_profile": CAPABILITY_PROFILES["COINBASE"].as_dict(),
        "certification_readiness": True,
        "evidence_readiness": True,
        "classification": "PARTIAL",
        "notes": "Historical live RO PASS; unify under Phase 189 contracts",
    },
    "IBKR": {
        "implementation_status": "BLOCKED",
        "authentication_model": "none_placeholder",
        "connectivity": "none",
        "account_support": False,
        "market_data": False,
        "execution_support": False,
        "supported_asset_classes": CAPABILITY_PROFILES["IBKR"].supported_asset_classes(),
        "capability_profile": CAPABILITY_PROFILES["IBKR"].as_dict(),
        "certification_readiness": False,
        "evidence_readiness": False,
        "classification": "BLOCKED",
        "notes": "Roadmap-excluded (177C Rev B); placeholder only",
    },
    "BINANCE": {
        "implementation_status": "PARTIAL",
        "authentication_model": "api_key_secret_env",
        "connectivity": "registry_only",
        "account_support": True,
        "market_data": True,
        "execution_support": False,
        "supported_asset_classes": CAPABILITY_PROFILES["BINANCE"].supported_asset_classes(),
        "capability_profile": CAPABILITY_PROFILES["BINANCE"].as_dict(),
        "certification_readiness": False,
        "evidence_readiness": False,
        "classification": "NOT_STARTED",
        "notes": "Plugin/ops states present; dedicated live RO adapter not started",
    },
    "QUESTRADE": {
        "implementation_status": "PARTIAL",
        "authentication_model": "oauth_refresh_reference",
        "connectivity": "injected_transport",
        "account_support": True,
        "market_data": True,
        "execution_support": False,
        "supported_asset_classes": CAPABILITY_PROFILES["QUESTRADE"].supported_asset_classes(),
        "capability_profile": CAPABILITY_PROFILES["QUESTRADE"].as_dict(),
        "certification_readiness": True,
        "evidence_readiness": True,
        "classification": "PARTIAL",
        "notes": "178D/179D secure RO contracts; no default production OAuth",
    },
    "PLUGIN": {
        "implementation_status": "NOT_STARTED",
        "authentication_model": "plugin_declared",
        "connectivity": "none",
        "account_support": False,
        "market_data": False,
        "execution_support": False,
        "supported_asset_classes": (),
        "capability_profile": CAPABILITY_PROFILES["PLUGIN"].as_dict(),
        "certification_readiness": False,
        "evidence_readiness": False,
        "classification": "NOT_STARTED",
        "notes": "Future plugin onboarding via declared BrokerCapabilityProfile",
    },
}


def get_capability_profile(broker_key: str) -> BrokerCapabilityProfile:
    key = str(broker_key or "").upper()
    if key not in CAPABILITY_PROFILES:
        return BrokerCapabilityProfile(broker_type=key or "PLUGIN")
    return CAPABILITY_PROFILES[key]


def broker_readiness_from_audit(broker_key: str) -> Mapping[str, Any]:
    return dict(BROKER_AUDIT_MATRIX.get(str(broker_key).upper(), {}))


def register_plugin_capability(profile: BrokerCapabilityProfile) -> None:
    """Allow future brokers without redesign (explicit declaration required)."""
    if not profile.broker_type:
        raise ValueError("plugin profile requires broker_type")
    key = profile.broker_type.upper()
    CAPABILITY_PROFILES[key] = profile
    BROKER_AUDIT_MATRIX[key] = {
        "implementation_status": "NOT_STARTED",
        "authentication_model": "plugin_declared",
        "connectivity": "plugin_declared",
        "account_support": profile.account_information,
        "market_data": profile.market_data,
        "execution_support": False,
        "supported_asset_classes": profile.supported_asset_classes(),
        "capability_profile": profile.as_dict(),
        "certification_readiness": False,
        "evidence_readiness": False,
        "classification": "NOT_STARTED",
        "notes": "Registered via Phase 189 plugin capability declaration",
    }
