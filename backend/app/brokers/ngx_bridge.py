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
SOURCES = BROKERS | REGISTRARS


@dataclass(frozen=True)
class NGXSource:
    source_id: str
    kind: str
    api_status: str = "not_authorized"
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if self.source_id not in SOURCES:
            raise ValueError("Unrecognized NGX source")
        expected = "broker" if self.source_id in BROKERS else "registrar"
        if self.kind != expected or self.execution_allowed:
            raise ValueError("NGX source kind mismatch or execution requested")
        if self.api_status != "not_authorized":
            raise ValueError("API authorization must be verified by a separate connector")


SOURCE_CATALOG = tuple(
    NGXSource(name, "broker" if name in BROKERS else "registrar")
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
        if broker not in BROKERS or not account or not symbol or currency != "NGN":
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
        if registrar not in REGISTRARS or not symbol:
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
