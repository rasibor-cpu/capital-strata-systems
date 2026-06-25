from __future__ import annotations

from backend.trading.canonical_trading_universe import CanonicalTradingUniverse


def test_canonical_universe_has_required_groups() -> None:
    universe = CanonicalTradingUniverse()
    grouped = universe.grouped(mode="paper")

    assert set(grouped.keys()) == {"CRYPTO", "FOREX", "INDICES", "FUTURES", "OPTIONS"}
    assert len(grouped["CRYPTO"]) == 7
    assert len(grouped["FOREX"]) == 10
    assert len(grouped["INDICES"]) == 4
    assert len(grouped["FUTURES"]) == 7
    assert len(grouped["OPTIONS"]) == 2


def test_unavailable_instruments_marked_not_selectable() -> None:
    universe = CanonicalTradingUniverse()
    row = universe.by_symbol("DOGE-USD", asset_class="CRYPTO", mode="paper")

    assert row is not None
    assert row["selectable"] is False
    assert "Disabled" in row["unavailable_reason"]


def test_summary_reports_expected_counts() -> None:
    summary = CanonicalTradingUniverse().summary()

    assert summary["total"] == 30
    assert summary["groups"]["CRYPTO"] == 7
    assert summary["groups"]["FOREX"] == 10
    assert summary["groups"]["INDICES"] == 4
    assert summary["groups"]["FUTURES"] == 7
    assert summary["groups"]["OPTIONS"] == 2


def test_options_and_futures_have_explicit_tenor_metadata() -> None:
    universe = CanonicalTradingUniverse()

    options_row = universe.by_symbol("SPY", asset_class="OPTIONS", mode="paper")
    futures_row = universe.by_symbol("ES", asset_class="FUTURES", mode="paper")

    assert options_row is not None
    assert options_row["metadata_status"] == "EXPLICIT"
    assert options_row["tenor_options"] == ["2026-07-17", "2026-08-21", "2026-09-18"]
    assert options_row["default_tenor"] == "2026-07-17"
    assert options_row["expiry_source"] == "canonical_options_chain_metadata"
    assert options_row["option_types"] == ["CALL", "PUT"]
    assert options_row["strike_policy"] == "ATM_LADDER"

    assert futures_row is not None
    assert futures_row["metadata_status"] == "EXPLICIT"
    assert futures_row["tenor_options"] == ["2026H", "2026M", "2026U", "2026Z"]
    assert futures_row["default_tenor"] == "2026H"
    assert futures_row["expiry_source"] == "canonical_futures_contract_metadata"
