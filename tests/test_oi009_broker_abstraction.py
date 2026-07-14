from __future__ import annotations

import inspect
import json
from datetime import date, timedelta

import pytest

from backend.options.options_broker_abstraction import OptionsBrokerAbstractionError
from backend.options.options_broker_capabilities import OptionsBrokerCapabilities, default_paper_options_capabilities
from backend.options.options_broker_health import OptionsBrokerHealthMonitor
from backend.options.options_broker_registry import OptionsBrokerRegistry, create_default_paper_options_registry
from backend.options.options_chain_provider import OptionsChainProvider
from backend.options.options_contract_provider import OptionsContractProvider
from backend.options.options_income_dashboard import build_options_income_dashboard
from backend.options.options_income_opportunity_scanner import IncomeOpportunityScanner
from backend.options.options_income_portfolio import OptionsIncomePortfolioConstructor
from backend.options.options_income_risk_governance import OptionsIncomeRiskGovernanceEngine
from backend.options.options_income_stress_testing import OptionsIncomeStressTester
from backend.options.options_market_data_provider import OptionsMarketDataProvider
from backend.options.options_paper_broker import OptionsPaperBroker
from backend.options.paper_income_lifecycle import PaperIncomeLifecycleEngine
from backend.options.paper_position_repository import PaperPositionRepository
from backend.trading.option_contract import CanonicalOptionContract

import backend.options.options_broker_abstraction as abstraction_module
import backend.options.options_paper_broker as paper_broker_module


AS_OF = date(2026, 7, 14)
EXPIRY_1 = (AS_OF + timedelta(days=30)).isoformat()
EXPIRY_2 = (AS_OF + timedelta(days=37)).isoformat()
NOW = "2026-07-14T00:00:00+00:00"


def _clock() -> str:
    return NOW


def _contract(option_type: str, *, underlying: str = "SPY", expiry: str = EXPIRY_1, strike: float | None = None) -> CanonicalOptionContract:
    option_type = option_type.upper()
    strike = 105.0 if strike is None and option_type == "CALL" else (95.0 if strike is None else strike)
    return CanonicalOptionContract.from_dict(
        {
            "underlying_symbol": underlying,
            "option_symbol": f"{underlying}-{expiry}-{option_type[0]}-{int(strike)}",
            "expiration_date": expiry,
            "strike": strike,
            "option_type": option_type,
            "bid": 1.9,
            "ask": 2.1,
            "midpoint": 2.0,
            "last": 2.0,
            "volume": 250,
            "open_interest": 800,
            "implied_volatility": 0.22,
            "delta": 0.30 if option_type == "CALL" else -0.30,
            "gamma": 0.02,
            "theta": -0.01,
            "vega": 0.10,
            "rho": 0.01,
            "intrinsic_value": 0.0,
            "extrinsic_value": 2.0,
            "probability_itm": 0.30,
            "exchange": "CBOE",
            "multiplier": 100,
            "currency": "USD",
            "timestamp": NOW,
        }
    )


def _contracts():
    return [
        _contract("CALL", underlying="SPY", expiry=EXPIRY_1, strike=105),
        _contract("PUT", underlying="SPY", expiry=EXPIRY_1, strike=95),
        _contract("CALL", underlying="QQQ", expiry=EXPIRY_2, strike=105),
        _contract("PUT", underlying="QQQ", expiry=EXPIRY_2, strike=95),
    ]


def _broker() -> OptionsPaperBroker:
    return OptionsPaperBroker(provider_name="paper_options_test", contracts=_contracts(), buying_power=50000.0)


def test_provider_registration_and_lookup():
    broker = _broker()
    registry = OptionsBrokerRegistry()
    entry = registry.register(broker, priority=10)

    assert entry.provider_name == "paper_options_test"
    assert registry.get("paper_options_test") is broker
    assert registry.entry("paper_options_test")["execution_allowed"] is False
    assert registry.providers()[0]["provider_name"] == "paper_options_test"


def test_duplicate_provider_and_missing_provider_fail_closed():
    registry = OptionsBrokerRegistry()
    broker = _broker()
    registry.register(broker)

    with pytest.raises(OptionsBrokerAbstractionError, match="duplicate provider"):
        registry.register(broker)
    with pytest.raises(OptionsBrokerAbstractionError, match="missing provider"):
        registry.get("missing")


def test_registry_rejects_unsupported_provider_and_strategy():
    registry = OptionsBrokerRegistry()

    with pytest.raises(OptionsBrokerAbstractionError, match="unsupported provider"):
        registry.register(object())  # type: ignore[arg-type]
    with pytest.raises(OptionsBrokerAbstractionError, match="unsupported strategy"):
        registry.register(_broker(), supported_strategies=["IRON_CONDOR"])


def test_default_registry_registers_paper_provider_only():
    registry = create_default_paper_options_registry(_broker())
    provider = registry.providers()[0]

    assert provider["capabilities"]["supports_live_mode"] is False
    assert provider["capabilities"]["supports_paper_mode"] is True
    assert provider["live_trading_blocked"] is True


def test_contract_lookup_and_underlying_metadata():
    provider = OptionsContractProvider(_contracts())
    contract = provider.get_contract("SPY-2026-08-13-C-105")
    metadata = provider.underlying_metadata("SPY")

    assert contract.option_type == "CALL"
    assert metadata["expiries"] == [EXPIRY_1]
    assert metadata["strikes"] == [95.0, 105.0]
    assert metadata["execution_allowed"] is False


def test_missing_contract_and_duplicate_contract_fail_closed():
    with pytest.raises(OptionsBrokerAbstractionError, match="duplicate contract"):
        OptionsContractProvider([_contract("CALL"), _contract("CALL")])

    provider = OptionsContractProvider(_contracts())
    with pytest.raises(OptionsBrokerAbstractionError, match="missing contract"):
        provider.get_contract("MISSING")


def test_option_chain_lookup_exposes_calls_puts_expiries_strikes_and_greeks_fields():
    chain = OptionsChainProvider(OptionsContractProvider(_contracts())).get_chain("SPY", now=NOW).to_dict()

    assert chain["underlying_symbol"] == "SPY"
    assert chain["expiries"] == [EXPIRY_1]
    assert chain["strikes"] == [95.0, 105.0]
    assert chain["calls"][0]["delta"] == 0.30
    assert chain["puts"][0]["implied_volatility"] == 0.22
    assert chain["quality"] == "COMPLETE"


def test_missing_chain_fails_closed():
    provider = OptionsChainProvider(OptionsContractProvider(_contracts()))

    with pytest.raises(OptionsBrokerAbstractionError, match="missing chain"):
        provider.get_chain("AAPL")


def test_market_data_snapshot_refresh_cache_and_freshness():
    provider = OptionsMarketDataProvider(OptionsContractProvider(_contracts()), max_cache_age_seconds=60)
    first = provider.snapshot("SPY-2026-08-13-C-105", now=NOW).to_dict()
    cached = provider.snapshot("SPY-2026-08-13-C-105", now="2026-07-14T00:00:30+00:00").to_dict()
    refreshed = provider.snapshot("SPY-2026-08-13-C-105", now="2026-07-14T00:02:00+00:00").to_dict()

    assert first["cached"] is False
    assert cached["cached"] is True
    assert refreshed["cached"] is False
    assert first["quote"]["mark"] == 2.0
    assert first["quality"] == "COMPLETE"


def test_broker_health_online_and_degraded_states():
    broker = _broker()
    quote = broker.quote("SPY-2026-08-13-C-105", now=NOW)
    chain = broker.chain("SPY", now=NOW)
    health = OptionsBrokerHealthMonitor().assess(provider_name=broker.provider_name, market_data=quote, chain=chain).to_dict()
    degraded = OptionsBrokerHealthMonitor().assess(
        provider_name=broker.provider_name,
        market_data={**quote, "greeks": {}},
        chain={**chain, "calls": []},
        quote_latency_ms=600,
        chain_latency_ms=900,
    ).to_dict()

    assert health["status"] == "ONLINE"
    assert health["health_score"] >= 90
    assert degraded["status"] == "DEGRADED"
    assert degraded["greeks_availability"] == "UNAVAILABLE"


def test_capabilities_are_paper_only_and_live_support_is_rejected():
    capabilities = default_paper_options_capabilities("paper")

    assert capabilities.to_dict()["supports_options"] is True
    assert capabilities.to_dict()["supports_order_preview"] is True
    assert capabilities.to_dict()["supports_live_mode"] is False
    with pytest.raises(OptionsBrokerAbstractionError, match="live support"):
        OptionsBrokerCapabilities(provider_name="bad", supports_live_mode=True)


def test_paper_broker_account_summary_and_quote_paths():
    broker = _broker()
    account = broker.account_summary()
    quote = broker.quote("SPY-2026-08-13-C-105", now=NOW)
    chain = broker.chain("SPY", now=NOW)

    assert account["account_id"] == "PAPER-OPTIONS-ACCOUNT"
    assert account["buying_power"] == 50000.0
    assert quote["execution_allowed"] is False
    assert len(chain["calls"]) == 1
    assert len(chain["puts"]) == 1


def test_paper_order_preview_has_no_execution_authority_or_order_identifiers():
    broker = _broker()
    preview = broker.preview_order(
        strategy="COVERED_CALL",
        collateral=100.0,
        premium=2.0,
        quantity=1,
        option_symbol="SPY-2026-08-13-C-105",
    )

    encoded = json.dumps(preview, sort_keys=True)
    assert preview["preview_status"] == "PASS"
    assert preview["estimated_collateral"] == 100.0
    assert preview["estimated_premium"] == 2.0
    assert preview["execution_allowed"] is False
    assert "order_id" not in encoded
    assert "ticket" not in encoded
    assert "routing" not in encoded


def test_order_preview_warnings_and_fail_closed_inputs():
    broker = _broker()
    warning = broker.preview_order(
        strategy="CASH_SECURED_PUT",
        collateral=100000.0,
        premium=1.0,
        quantity=1,
        option_symbol="SPY-2026-08-13-P-95",
    )

    assert warning["preview_status"] == "WARNING"
    assert warning["warnings"] == ["INSUFFICIENT_PAPER_BUYING_POWER"]
    with pytest.raises(OptionsBrokerAbstractionError, match="unsupported strategy"):
        broker.preview_order(strategy="IRON_CONDOR", collateral=1, premium=1, quantity=1, option_symbol="SPY-2026-08-13-C-105")
    with pytest.raises(OptionsBrokerAbstractionError, match="negative collateral"):
        broker.preview_order(strategy="COVERED_CALL", collateral=-1, premium=1, quantity=1, option_symbol="SPY-2026-08-13-C-105")
    with pytest.raises(OptionsBrokerAbstractionError, match="live broker mode"):
        broker.preview_order(strategy="COVERED_CALL", collateral=1, premium=1, quantity=1, option_symbol="SPY-2026-08-13-C-105", mode="LIVE")


def test_paper_broker_rejects_live_mode_and_negative_buying_power():
    with pytest.raises(OptionsBrokerAbstractionError, match="live broker mode"):
        OptionsPaperBroker(contracts=_contracts(), mode="LIVE")
    with pytest.raises(OptionsBrokerAbstractionError, match="negative buying power"):
        OptionsPaperBroker(contracts=_contracts(), buying_power=-1)


def test_malformed_greeks_missing_iv_and_mandatory_fields_fail_closed():
    bad_greek = _contract("CALL").to_dict()
    bad_greek["delta"] = "bad"
    missing_iv = _contract("CALL").to_dict()
    missing_iv["implied_volatility"] = 0.0
    missing_symbol = _contract("CALL").to_dict()
    missing_symbol["option_symbol"] = ""

    for payload in (bad_greek, missing_iv, missing_symbol):
        with pytest.raises((OptionsBrokerAbstractionError, ValueError)):
            OptionsContractProvider([payload])


def test_oi005_oi006_oi007_oi008_integration_from_paper_broker_contracts():
    broker = _broker()
    spy_call = CanonicalOptionContract.from_dict(broker.contract("SPY-2026-08-13-C-105"))
    qqq_put = CanonicalOptionContract.from_dict(broker.contract("QQQ-2026-08-20-P-95"))
    call_candidate = IncomeOpportunityScanner().scan_covered_calls(
        [spy_call],
        underlying_symbol="SPY",
        underlying_price=100.0,
        underlying_quantity=100,
        as_of=AS_OF,
    )[0]
    put_candidate = IncomeOpportunityScanner().scan_cash_secured_puts(
        [qqq_put],
        underlying_symbol="QQQ",
        cash_collateral_available=9500.0,
        underlying_price=100.0,
        as_of=AS_OF,
    )[0]
    repository = PaperPositionRepository()
    lifecycle = PaperIncomeLifecycleEngine(repository=repository, clock=_clock)
    position = lifecycle.create_position(call_candidate, entry_date=AS_OF.isoformat())
    lifecycle.approve_position(position.position_id)
    lifecycle.open_position(position.position_id)
    active = lifecycle.activate_position(position.position_id)
    portfolio = OptionsIncomePortfolioConstructor().construct(
        portfolio_id="OI009-PAPER",
        total_capital=50000.0,
        opportunities=[call_candidate, put_candidate],
        existing_positions=[active],
        sector_by_underlying={"SPY": "ETF", "QQQ": "ETF"},
        annual_target_yield=0.10,
    ).to_dict()
    greeks = {row["option_symbol"]: {"delta": 0.05, "gamma": 0.001, "theta": -0.01, "vega": 0.01, "rho": 0.01} for row in portfolio["allocations"]}
    ivs = {row["option_symbol"]: 0.22 for row in portfolio["allocations"]}
    assessment = OptionsIncomeRiskGovernanceEngine().assess(
        portfolio,
        greeks_by_symbol=greeks,
        iv_by_symbol=ivs,
        market_data_by_underlying={"SPY": {"underlying_price": 100.0}, "QQQ": {"underlying_price": 100.0}},
    ).to_dict()
    stress = OptionsIncomeStressTester().run(portfolio, greeks=assessment["greeks_summary"], assignment=assessment["assignment_summary"]).to_dict()
    dashboard = build_options_income_dashboard(
        opportunities=[call_candidate, put_candidate],
        positions=[active],
        portfolio=portfolio,
        risk_assessment=assessment,
        stress_report=stress,
        generated_at=NOW,
    )

    assert active.current_state == "ACTIVE"
    assert portfolio["allocations"]
    assert assessment["execution_allowed"] is False
    assert dashboard["summary"]["engine_version"] == "OI-008"
    assert dashboard["paper_only"] is True
    assert dashboard["execution_allowed"] is False


def test_no_live_broker_or_execution_calls_added_to_oi009_modules():
    source = "\n".join(
        [
            inspect.getsource(abstraction_module),
            inspect.getsource(paper_broker_module),
        ]
    )

    assert "submit_order" not in source
    assert "place_order" not in source
    assert "execute_trade" not in source
    assert "enable_live" not in source
    assert ".env" not in source
    assert "PEM" not in source
