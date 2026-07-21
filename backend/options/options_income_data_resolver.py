"""Phase 178A — resolve advisory data into Options Income runtime context.

Fail-closed. Never fabricates chains, prices, or collateral. Never enables execution.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from backend.app.brokers.operational_adapter import get_operational_adapter
from backend.app.brokers.operational_state import BrokerCapability
from backend.brokers.questrade.readiness import questrade_advisory_readiness
from backend.options.options_income_advisory_contracts import SCHEMA_VERSION, broker_capability_truth
from backend.options.options_income_collateral_authority import resolve_collateral_authority
from backend.options.options_income_eligibility import (
    evaluate_cash_secured_put_eligibility,
    evaluate_covered_call_eligibility,
    summarize_exclusions,
)
from backend.options.options_income_freshness import utc_now
from backend.options.options_income_holdings_adapter import fetch_account_holdings
from backend.options.options_income_market_data_adapter import fetch_underlying_market_data
from backend.options.options_income_market_events import resolve_market_event_context
from backend.options.options_income_option_chain_adapter import fetch_option_chain
from backend.options.options_income_provider_registry import (
    get_holdings_provider,
    get_market_data_provider,
    get_option_chain_provider,
    provider_registry_status,
)
from backend.options.options_income_runtime_service import OptionsIncomeRuntimeContext
from backend.options.options_income_symbol_normalization import normalize_equity_symbol


def _broker_supports_listed_options(broker: str | None) -> bool:
    if not broker:
        return False
    truth = broker_capability_truth()["brokers"]
    row = truth.get(str(broker).upper()) or {}
    return bool(row.get("listed_equity_options"))


def _match_chain(chain_rows: Sequence[Mapping[str, Any]], symbol: str) -> Mapping[str, Any]:
    target = str(normalize_equity_symbol(symbol).get("canonical") or symbol).upper()
    for row in chain_rows:
        canon = str(row.get("canonical_underlying") or row.get("underlying_symbol") or "").upper()
        if canon == target or canon.endswith(target) or target.endswith(canon):
            return row
    return chain_rows[0] if chain_rows else {}


def resolve_options_income_advisory_data(
    *,
    underlying_symbols: Sequence[str] | None = None,
    broker: str | None = None,
    market_data_provider: Any | None = None,
    option_chain_provider: Any | None = None,
    holdings_provider: Any | None = None,
    calendar_provider: Mapping[str, Any] | None = None,
    event_provider: Mapping[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Assemble canonical advisory inputs. Providers default to registry (usually empty)."""
    ts = generated_at or utc_now()
    symbols = [str(s).strip() for s in (underlying_symbols or []) if str(s).strip()]
    md_provider = market_data_provider if market_data_provider is not None else get_market_data_provider()
    chain_provider = option_chain_provider if option_chain_provider is not None else get_option_chain_provider()
    hold_provider = holdings_provider if holdings_provider is not None else get_holdings_provider()

    registry = provider_registry_status()
    capabilities = broker_capability_truth()
    questrade = questrade_advisory_readiness(probe_env=True)
    broker_operational: dict[str, Any] | None = None
    broker_option_chain_state: dict[str, Any] | None = None
    if broker and str(broker).upper() in {"COINBASE", "BINANCE", "OANDA", "QUESTRADE"}:
        operational_adapter = get_operational_adapter(str(broker))
        broker_operational = operational_adapter.operational_snapshot()
        if hasattr(operational_adapter, "option_chain"):
            broker_option_chain_state = operational_adapter.option_chain(symbols[0] if symbols else None)
        else:
            broker_option_chain_state = operational_adapter.capability(BrokerCapability.OPTION_CHAIN)
    broker_advisory_ready = bool(
        broker
        and broker_operational
        and str(broker_operational.get("operational_state") or "").upper()
        in {"ACCOUNT_READY", "HOLDINGS_READY", "READ_ONLY_READY", "ADVISORY_READY"}
        and broker_option_chain_state
        and bool(broker_option_chain_state.get("success"))
    )

    market_rows: list[dict[str, Any]] = []
    chain_rows: list[dict[str, Any]] = []
    probe_symbols = symbols or ["SPY"]
    for sym in probe_symbols:
        market_rows.append(fetch_underlying_market_data(sym, provider=md_provider, generated_at=ts))
        chain_rows.append(fetch_option_chain(sym, provider=chain_provider, generated_at=ts))

    holdings = fetch_account_holdings(provider=hold_provider, broker=broker, generated_at=ts)
    collateral = resolve_collateral_authority(holdings=holdings, generated_at=ts)
    events = resolve_market_event_context(
        underlying=symbols[0] if symbols else None,
        calendar_provider=calendar_provider,
        event_provider=event_provider,
        generated_at=ts,
    )

    # Broker-compatible opportunity assignment: Coinbase/Binance/OANDA never get listed-options eligibility
    if broker and str(broker).upper() in {"COINBASE", "BINANCE", "OANDA"}:
        broker_ok = False
    elif broker:
        broker_ok = _broker_supports_listed_options(broker) and broker_advisory_ready
    else:
        # Unspecified broker: listed-options capability exists only via Questrade among Tier-1
        broker_ok = bool(capabilities["brokers"]["QUESTRADE"]["listed_equity_options"])

    eligibility_rows: list[dict[str, Any]] = []
    for sym in symbols:
        chain = _match_chain(chain_rows, sym)
        eligibility_rows.append(
            evaluate_covered_call_eligibility(
                underlying=str(normalize_equity_symbol(sym).get("canonical") or sym),
                holdings=holdings,
                chain=chain,
                broker_supports_listed_options=broker_ok,
            )
        )

    csp_probe = evaluate_cash_secured_put_eligibility(
        strike=100.0,
        multiplier=100,
        collateral=collateral,
        chain=chain_rows[0] if chain_rows else None,
        broker_supports_listed_options=broker_ok,
    )

    market_ready = any(str(r.get("status") or "").upper() == "READY" for r in market_rows)
    chain_ready = any(str(r.get("status") or "").upper() == "READY" for r in chain_rows)
    holdings_ready = str(holdings.get("status") or "").upper() in {"READY", "PARTIAL_DATA", "STALE"}
    collateral_ready = collateral.get("authority_level") != "UNAVAILABLE"
    stale = any(str(r.get("status") or "").upper() == "STALE" for r in (*chain_rows, *market_rows)) or str(
        holdings.get("status") or ""
    ).upper() == "STALE"
    partial = any(str(r.get("status") or "").upper() == "PARTIAL_DATA" for r in (*chain_rows, *market_rows)) or str(
        holdings.get("status") or ""
    ).upper() == "PARTIAL_DATA"
    failed = any(str(r.get("status") or "").upper() == "FAILED" for r in (*chain_rows, *market_rows)) or str(
        holdings.get("status") or ""
    ).upper() == "FAILED"

    missing: list[str] = []
    if not market_ready:
        missing.append("MARKET_DATA")
    if not chain_ready:
        missing.append("OPTION_CHAIN")
    if not holdings_ready:
        missing.append("ACCOUNT_HOLDINGS")
    if not collateral_ready:
        missing.append("COLLATERAL")
    if not broker_advisory_ready:
        missing.append("BROKER_OPERATIONAL_READINESS")

    chain_not_configured = all(
        str(r.get("status") or "").upper() == "OPTION_CHAIN_PROVIDER_NOT_CONFIGURED" for r in chain_rows
    ) if chain_rows else (chain_provider is None)

    if chain_not_configured:
        readiness_status = "DATA_DEPENDENCY_BLOCKED"
    elif failed and not (chain_ready or stale):
        readiness_status = "FAILED"
    elif stale:
        readiness_status = "STALE"
    elif partial and not (market_ready and chain_ready and holdings_ready):
        readiness_status = "PARTIAL_DATA"
    elif market_ready and chain_ready and holdings_ready and collateral_ready and broker_advisory_ready:
        readiness_status = "ADVISORY_READY"
    elif chain_ready and not holdings_ready:
        readiness_status = "PARTIAL_DATA"
    else:
        readiness_status = "DATA_DEPENDENCY_BLOCKED"

    return {
        "schema_version": SCHEMA_VERSION,
        "contract": "options_income_advisory_data",
        "generated_at": ts,
        "status": readiness_status,
        "readiness_status": readiness_status,
        "market_data": market_rows[0] if len(market_rows) == 1 else {"rows": market_rows, "status": "AGGREGATED"},
        "market_data_rows": market_rows,
        "option_chains": chain_rows[0] if len(chain_rows) == 1 else {"rows": chain_rows, "status": "AGGREGATED"},
        "option_chain_rows": chain_rows,
        "holdings": holdings,
        "collateral": collateral,
        "events": events,
        "eligibility": {
            "covered_calls": eligibility_rows,
            "cash_secured_put_probe": csp_probe,
            "exclusions_summary": summarize_exclusions(eligibility_rows),
        },
        "provider_registry": registry,
        "broker_capability_truth": capabilities,
        "questrade_readiness": questrade,
        "broker": broker,
        "broker_listed_options_compatible": broker_ok,
        "broker_operational_state": broker_operational,
        "broker_option_chain_state": broker_option_chain_state,
        "broker_expected_condition": (
            bool((broker_option_chain_state or {}).get("expected_condition"))
            if broker_option_chain_state
            else None
        ),
        "market_data_available": market_ready,
        "option_chain_available": chain_ready,
        "account_holdings_available": holdings_ready,
        "missing_dependencies": missing,
        "stale": stale,
        "partial": partial,
        "failed": failed,
        "advisory_only": True,
        "execution_allowed": False,
        "execution_ready": False,
        "live_ready": False,
        "opportunities_fabricated": False,
        "last_successful_refresh": ts if (market_ready or chain_ready or holdings_ready) else None,
        "provenance": {
            "market_data": "MARKET_DATA_PROVIDER" if md_provider else "CONFIGURATION",
            "option_chain": "OPTION_CHAIN_PROVIDER" if chain_provider else "CONFIGURATION",
            "holdings": "ACCOUNT_HOLDINGS" if hold_provider else "CONFIGURATION",
            "collateral": collateral.get("provenance"),
            "events": events.get("provenance"),
        },
    }


def build_runtime_context_from_advisory(
    advisory: Mapping[str, Any] | None = None,
    *,
    opportunities: Sequence[Any] | None = None,
    persist: bool = False,
    **ctx_kwargs: Any,
) -> OptionsIncomeRuntimeContext:
    """Map advisory resolution into OptionsIncomeRuntimeContext flags."""
    data = dict(advisory or resolve_options_income_advisory_data())
    allowed = set(OptionsIncomeRuntimeContext.__dataclass_fields__)
    extras = {k: v for k, v in ctx_kwargs.items() if k in allowed and k != "advisory_data"}
    return OptionsIncomeRuntimeContext(
        opportunities=opportunities if opportunities is not None else extras.pop("opportunities", None),
        option_chain_available=bool(data.get("option_chain_available")),
        market_data_available=bool(data.get("market_data_available")),
        account_holdings_available=bool(data.get("account_holdings_available")),
        persist=persist,
        generated_at=str(data.get("generated_at") or utc_now()),
        advisory_data=data,
        **extras,
    )


__all__ = [
    "build_runtime_context_from_advisory",
    "resolve_options_income_advisory_data",
]
