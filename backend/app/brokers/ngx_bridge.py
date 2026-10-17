"""Fail-closed, read-only NGX broker and registrar reconciliation boundary.

No credentials, network transport, order placement, or persistent account identifiers
are embedded here. Upstream connectors must be separately authorized.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Iterable, Mapping

BROKERS = frozenset({"investment_one", "meristem", "cardinalstone", "coronation_securities"})
REGISTRARS = frozenset({"gt_registrars"})
CANADIAN_BROKERS = frozenset({"questrade"})
US_BANKS = frozenset({"chase", "bank_of_america", "wells_fargo", "citi", "capital_one", "us_bank"})
US_BROKERS = frozenset({"fidelity", "charles_schwab", "interactive_brokers", "robinhood", "etrade"})
CANADIAN_BANKS = frozenset({"rbc", "td", "scotiabank", "bmo", "cibc", "national_bank"})
PENSION_PROVIDERS = frozenset({"stanbic_ibtc_pension_managers"})
SOURCES = BROKERS | CANADIAN_BROKERS | US_BROKERS | REGISTRARS | PENSION_PROVIDERS | CANADIAN_BANKS | US_BANKS


@dataclass(frozen=True)
class NGXSource:
    source_id: str
    kind: str
    api_status: str = "not_authorized"
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if self.kind not in {"broker", "registrar", "pension", "bank"}:
            raise ValueError("Invalid institution type")
        if not self.source_id or not self.source_id.replace("_", "").isalnum():
            raise ValueError("Invalid institution identifier")
        if self.execution_allowed:
            raise ValueError("NGX source kind mismatch or execution requested")
        if self.api_status != "not_authorized":
            raise ValueError("API authorization must be verified by a separate connector")


SOURCE_CATALOG = tuple(
    NGXSource(name, "broker" if name in BROKERS | CANADIAN_BROKERS | US_BROKERS else
              "registrar" if name in REGISTRARS else
              "bank" if name in CANADIAN_BANKS | US_BANKS else "pension")
    for name in sorted(SOURCES)
)


def _decimal(value: object, *, positive: bool = False) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError("Missing or invalid numeric value")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Invalid numeric value") from exc
    if not number.is_finite() or (positive and number <= 0) or number < 0:
        raise ValueError("Non-finite or negative numeric value")
    return number


def reconcile_ngx_positions(
    broker_positions: Iterable[Mapping[str, object]],
    registrar_records: Iterable[Mapping[str, object]] = (),
) -> dict[str, object]:
    """Consolidate broker snapshots; registrar records are corroboration-only.

    Inputs are normalized, pre-authorized records. The account_key must be a
    non-secret opaque alias, never a raw CSCS number or CHN. Each broker/account/
    symbol combination must occur once to avoid counting duplicate snapshots.
    """
    consolidated: dict[str, Decimal] = defaultdict(Decimal)
    accounts: set[tuple[str, str]] = set()
    seen: set[tuple[str, str, str]] = set()
    details: list[dict[str, str]] = []
    for item in broker_positions:
        broker = str(item.get("broker", "")).strip().lower()
        account = str(item.get("account_key", "")).strip()
        symbol = str(item.get("symbol", "")).strip().upper()
        currency = str(item.get("currency", "NGN")).strip().upper()
        if not broker or not broker.replace("_", "").isalnum() or not account or not symbol or currency != "NGN":
            raise ValueError("Invalid NGX broker position")
        key = (broker, account, symbol)
        if key in seen:
            raise ValueError("Duplicate broker/account/symbol snapshot")
        seen.add(key)
        accounts.add((broker, account))
        quantity = _decimal(item.get("quantity"))
        consolidated[symbol] += quantity
        details.append({"broker": broker, "account_key": account, "symbol": symbol,
                        "quantity": str(quantity), "currency": "NGN"})

    corroboration: list[dict[str, str]] = []
    for item in registrar_records:
        registrar = str(item.get("registrar", "")).strip().lower()
        symbol = str(item.get("symbol", "")).strip().upper()
        if not registrar or not registrar.replace("_", "").isalnum() or not symbol:
            raise ValueError("Invalid registrar record")
        quantity = _decimal(item.get("quantity"))
        corroboration.append({
            "registrar": registrar, "symbol": symbol,
            "reported_quantity": str(quantity),
            "broker_total": str(consolidated[symbol]) if symbol in consolidated else "unknown",
            "status": ("MATCH" if symbol in consolidated and consolidated[symbol] == quantity
                       else "UNVERIFIED"),
        })

    return {
        "status": "READ_ONLY",
        "execution_allowed": False,
        "real_time_fill_feed": False,
        "pnl_promotion_authority": False,
        "account_count": len(accounts),
        "positions": details,
        "consolidated_quantities": {key: str(value) for key, value in sorted(consolidated.items())},
        "registrar_corroboration": corroboration,
        "registrar_quantities_included_in_portfolio": False,
    }


def summarize_pension_snapshot(snapshot: Mapping[str, object]) -> dict[str, object]:
    """Read-only pension snapshot, separate from NGX holdings and trading capital."""
    provider = str(snapshot.get("provider", "")).strip().lower()
    if not provider or not provider.replace("_", "").isalnum():
        raise ValueError("Invalid pension provider")
    account_key = str(snapshot.get("account_key", "")).strip()
    if not account_key:
        raise ValueError("Opaque pension account alias required")
    currency = str(snapshot.get("currency", "NGN")).strip().upper()
    if currency != "NGN":
        raise ValueError("Unsupported pension snapshot currency")
    balance = _decimal(snapshot.get("balance"))
    return {"provider": provider, "account_key": account_key,
            "currency": currency, "balance": str(balance), "asset_class": "PENSION",
            "included_in_trading_capital": False, "execution_allowed": False,
            "source_status": "USER_SUPPLIED_UNVERIFIED"}


def register_institution(source_id: str, kind: str, *, display_name: str) -> NGXSource:
    """User-defined institution metadata; never implies an authenticated connector."""
    if not isinstance(display_name, str) or not display_name.strip():
        raise ValueError("Institution display name required")
    return NGXSource(source_id.strip().lower(), kind.strip().lower())


def summarize_bank_snapshot(snapshot: Mapping[str, object]) -> dict[str, object]:
    """Unverified read-only bank balance; never available for trading by default.

    Institution IDs are user-configurable. No connection or bank authorization
    is implied. Account keys must be non-secret aliases, not account numbers.
    """
    provider = str(snapshot.get("provider", "")).strip().lower()
    account_key = str(snapshot.get("account_key", "")).strip()
    currency = str(snapshot.get("currency", "CAD")).strip().upper()
    if not provider or not provider.replace("_", "").isalnum() or not account_key:
        raise ValueError("Valid bank provider and opaque account alias required")
    if currency not in {"CAD", "USD"}:
        raise ValueError("Unsupported bank snapshot currency")
    balance = _decimal(snapshot.get("balance"))
    return {"provider": provider, "account_key": account_key,
            "currency": currency, "balance": str(balance),
            "asset_class": "CASH", "source_status": "USER_SUPPLIED_UNVERIFIED",
            "included_in_trading_capital": False, "execution_allowed": False,
            "transfer_authority": False}


CANADIAN_SIMULATION_CAPITAL_CAD = Decimal("14600")


def summarize_broker_account(snapshot: Mapping[str, object]) -> dict[str, object]:
    """Generic read-only account metadata for Canadian or other brokerages.

    This does not make Questrade API authorization or market-data access available.
    """
    provider = str(snapshot.get("provider", "")).strip().lower()
    account_key = str(snapshot.get("account_key", "")).strip()
    currency = str(snapshot.get("currency", "CAD")).strip().upper()
    if not provider or not provider.replace("_", "").isalnum() or not account_key:
        raise ValueError("Broker and opaque account alias required")
    if currency not in {"CAD", "USD"}:
        raise ValueError("Unsupported brokerage account currency")
    return {"provider": provider, "account_key": account_key,
            "currency": currency, "kind": "broker",
            "connection_status": "NOT_AUTHORIZED", "execution_allowed": False,
            "transfer_authority": False}


def summarize_us_institution_account(snapshot: Mapping[str, object]) -> dict[str, object]:
    """US institution metadata only; no bank-linking, ACH, wire or trade authority."""
    provider = str(snapshot.get("provider", "")).strip().lower()
    kind = str(snapshot.get("kind", "")).strip().lower()
    account_key = str(snapshot.get("account_key", "")).strip()
    currency = str(snapshot.get("currency", "USD")).strip().upper()
    if not provider or not provider.replace("_", "").isalnum() or kind not in {"bank", "broker"}:
        raise ValueError("Invalid US institution")
    if not account_key or currency != "USD":
        raise ValueError("Valid account alias and USD currency required")
    return {"provider": provider, "kind": kind, "account_key": account_key,
            "currency": "USD", "connection_status": "NOT_AUTHORIZED",
            "included_in_trading_capital": False, "execution_allowed": False,
            "transfer_authority": False, "ach_authority": False,
            "wire_authority": False}
