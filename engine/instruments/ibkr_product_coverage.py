from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class InstrumentProduct:
    """
    Canonical CSS coverage record for an IBKR-style product family.

    This registry is a capability declaration, not a broker adapter. It must not
    place orders, open broker sessions, or imply live execution support.
    """

    code: str
    label: str
    ibkr_label: str
    css_status: str
    live_execution_wired: bool = False
    paper_execution_wired: bool = False
    dashboard_visible: bool = True
    notes: str = ""

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


CSS_ACTIVE_EXECUTION_CODES = frozenset(
    {
        "CRYPTO",
        "FOREX",
        "FUTURE",
        "OPTION",
    }
)


IBKR_INSTITUTIONAL_PRODUCTS: tuple[InstrumentProduct, ...] = (
    InstrumentProduct(
        code="STOCK",
        label="Stocks",
        ibkr_label="Stocks",
        css_status="catalog_registered",
        notes="Registered for coverage; broker execution adapter not wired.",
    ),
    InstrumentProduct(
        code="ETF",
        label="ETFs",
        ibkr_label="ETFs",
        css_status="catalog_registered",
        notes="Registered for coverage; broker execution adapter not wired.",
    ),
    InstrumentProduct(
        code="OPTION",
        label="Options",
        ibkr_label="Options",
        css_status="active_css_workflow",
        paper_execution_wired=True,
        notes="CSS workflow exists; live adapter certification remains broker-specific.",
    ),
    InstrumentProduct(
        code="FUTURE",
        label="Futures",
        ibkr_label="Futures",
        css_status="active_css_workflow",
        paper_execution_wired=True,
        notes="CSS workflow exists; live adapter certification remains broker-specific.",
    ),
    InstrumentProduct(
        code="FUTURE_OPTION",
        label="Futures Options",
        ibkr_label="Futures Options",
        css_status="catalog_registered",
        notes="Separate product family from listed equity/index options.",
    ),
    InstrumentProduct(
        code="FOREX",
        label="Spot Currencies",
        ibkr_label="Spot Currencies",
        css_status="active_css_workflow",
        paper_execution_wired=True,
        notes="CSS FX/OANDA workflow exists; IBKR certification is not implied.",
    ),
    InstrumentProduct(
        code="SPOT_GOLD",
        label="US Spot Gold",
        ibkr_label="US Spot Gold",
        css_status="catalog_registered",
        notes="Registered for coverage; broker execution adapter not wired.",
    ),
    InstrumentProduct(
        code="BOND",
        label="Bonds",
        ibkr_label="Bonds",
        css_status="catalog_registered",
        notes="Registered for coverage; broker execution adapter not wired.",
    ),
    InstrumentProduct(
        code="MUTUAL_FUND",
        label="Mutual Funds",
        ibkr_label="Mutual Funds",
        css_status="catalog_registered",
        notes="Registered for coverage; broker execution adapter not wired.",
    ),
    InstrumentProduct(
        code="HEDGE_FUND",
        label="Hedge Funds",
        ibkr_label="Hedge Funds",
        css_status="catalog_registered",
        notes="Registered for coverage; broker execution adapter not wired.",
    ),
    InstrumentProduct(
        code="CRYPTO",
        label="Cryptocurrencies",
        ibkr_label="Cryptocurrencies",
        css_status="active_css_workflow",
        paper_execution_wired=True,
        notes="CSS Coinbase workflow exists; IBKR crypto certification is not implied.",
    ),
    InstrumentProduct(
        code="EVENT_CONTRACT",
        label="Forecast and Event Contracts",
        ibkr_label="Forecast and Event Contracts",
        css_status="catalog_registered",
        notes="Registered for coverage; broker execution adapter not wired.",
    ),
)


CANONICAL_IBKR_PRODUCT_CODES = tuple(
    product.code for product in IBKR_INSTITUTIONAL_PRODUCTS
)


def get_product(code: str) -> InstrumentProduct:
    normalized = str(code).strip().upper()
    for product in IBKR_INSTITUTIONAL_PRODUCTS:
        if product.code == normalized:
            return product

    raise KeyError(f"Unknown instrument product code: {code}")


def ibkr_suite_complete() -> bool:
    return set(CANONICAL_IBKR_PRODUCT_CODES) == {
        "STOCK",
        "ETF",
        "OPTION",
        "FUTURE",
        "FUTURE_OPTION",
        "FOREX",
        "SPOT_GOLD",
        "BOND",
        "MUTUAL_FUND",
        "HEDGE_FUND",
        "CRYPTO",
        "EVENT_CONTRACT",
    }


def frontend_supported_assets() -> list[str]:
    return [product.code for product in IBKR_INSTITUTIONAL_PRODUCTS]


def coverage_report() -> dict[str, object]:
    active = [
        product.code
        for product in IBKR_INSTITUTIONAL_PRODUCTS
        if product.css_status == "active_css_workflow"
    ]
    catalog_only = [
        product.code
        for product in IBKR_INSTITUTIONAL_PRODUCTS
        if product.css_status != "active_css_workflow"
    ]

    return {
        "suite": "IBKR institutional product families",
        "complete_catalog": ibkr_suite_complete(),
        "product_count": len(IBKR_INSTITUTIONAL_PRODUCTS),
        "active_css_workflow": active,
        "catalog_registered_only": catalog_only,
        "products": [product.as_dict() for product in IBKR_INSTITUTIONAL_PRODUCTS],
    }
