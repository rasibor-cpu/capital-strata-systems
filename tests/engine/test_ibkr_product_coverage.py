from __future__ import annotations

import pytest

from engine.instruments import (
    CANONICAL_IBKR_PRODUCT_CODES,
    CSS_ACTIVE_EXECUTION_CODES,
    coverage_report,
    frontend_supported_assets,
    get_product,
    ibkr_suite_complete,
)


EXPECTED_IBKR_PRODUCT_CODES = {
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


def test_ibkr_product_catalog_covers_official_product_families() -> None:
    assert set(CANONICAL_IBKR_PRODUCT_CODES) == EXPECTED_IBKR_PRODUCT_CODES
    assert set(frontend_supported_assets()) == EXPECTED_IBKR_PRODUCT_CODES
    assert ibkr_suite_complete() is True


def test_css_active_execution_is_not_misstated_as_full_ibkr_coverage() -> None:
    report = coverage_report()

    assert report["complete_catalog"] is True
    assert report["product_count"] == len(EXPECTED_IBKR_PRODUCT_CODES)
    assert set(report["active_css_workflow"]) == CSS_ACTIVE_EXECUTION_CODES
    assert set(report["catalog_registered_only"]) == (
        EXPECTED_IBKR_PRODUCT_CODES - CSS_ACTIVE_EXECUTION_CODES
    )


def test_registered_products_expose_safe_capability_metadata() -> None:
    crypto = get_product("crypto")
    stock = get_product("stock")

    assert crypto.code == "CRYPTO"
    assert crypto.css_status == "active_css_workflow"
    assert crypto.paper_execution_wired is True
    assert stock.code == "STOCK"
    assert stock.css_status == "catalog_registered"
    assert stock.live_execution_wired is False


def test_unknown_product_code_fails_closed() -> None:
    with pytest.raises(KeyError):
        get_product("unsupported-asset")
