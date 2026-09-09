from decimal import Decimal

import pytest

from backend.commercialization.client_earnings_summary import CommercialClientEarningsSummary
from backend.commercialization.withdrawable_funds import (
    CommercialWithdrawableFundsSummary,
    build_client_earnings_history,
)


@pytest.fixture
def base_history_entry():
    return {
        "period_start": "2026-09-01T00:00:00Z",
        "period_end": "2026-10-01T00:00:00Z",
        "performance_currency": "CAD",
        "billing_currency": "USD",
        "realized_attributable_profit": Decimal("150"),
        "recovered_loss": Decimal("20"),
        "new_economic_gain": Decimal("130"),
        "selected_fee_basis": "PERFORMANCE_COMPENSATION",
        "selected_fee_amount": Decimal("45"),
        "net_earnings_after_css_fee": Decimal("85"),
        "invoice_id": "INV-123",
        "receivable_id": "REC-123",
        "evidence_refs": ("evidence:one",),
    }


def test_withdrawable_summary_formula_and_reasons():
    summary = CommercialWithdrawableFundsSummary(
        account_reference="ACCT-001",
        account_currency="CAD",
        as_of="2026-09-15T00:00:00Z",
        total_cash=Decimal("250"),
        settled_cash=Decimal("180"),
        unsettled_proceeds=Decimal("60"),
        reserved_for_open_orders=Decimal("10"),
        reserved_for_margin_or_positions=Decimal("20"),
        pending_css_charge=Decimal("5"),
        other_restricted_amount=Decimal("4"),
        total_restricted_amount=Decimal("39"),
        available_to_withdraw=Decimal("141"),
        data_freshness="CURRENT",
        is_complete=True,
        restriction_reasons=("OPEN_ORDER_RESERVE", "MARGIN_OR_POSITION_RESERVE", "PENDING_CSS_CHARGE"),
        evidence_refs=("broker:balance:1",),
    )

    assert summary.available_to_withdraw == Decimal("141")
    assert "OPEN_ORDER_RESERVE" in summary.restriction_reasons
    assert summary.data_freshness == "CURRENT"


def test_withdrawable_summary_incomplete_for_missing_broker_data():
    summary = CommercialWithdrawableFundsSummary(
        account_reference="ACCT-001",
        account_currency="CAD",
        as_of="2026-09-15T00:00:00Z",
        total_cash=None,
        settled_cash=None,
        unsettled_proceeds=None,
        reserved_for_open_orders=None,
        reserved_for_margin_or_positions=None,
        pending_css_charge=None,
        other_restricted_amount=None,
        total_restricted_amount=None,
        available_to_withdraw=None,
        data_freshness="UNKNOWN",
        is_complete=False,
        restriction_reasons=("INCOMPLETE_BROKER_DATA",),
        evidence_refs=("broker:state:missing",),
    )

    assert summary.is_complete is False
    assert summary.available_to_withdraw is None
    assert "INCOMPLETE_BROKER_DATA" in summary.restriction_reasons


def test_history_entry_composes_from_existing_period_values(base_history_entry):
    entry = build_client_earnings_history(base_history_entry)

    assert entry["period_start"] == "2026-09-01T00:00:00Z"
    assert entry["selected_fee_basis"] == "PERFORMANCE_COMPENSATION"
    assert entry["net_earnings_after_css_fee"] == Decimal("85")
    assert entry["invoice_id"] == "INV-123"


def test_history_entries_are_sorted_by_period_start(base_history_entry):
    later = {**base_history_entry, "period_start": "2026-11-01T00:00:00Z", "period_end": "2026-12-01T00:00:00Z"}
    earlier = {**base_history_entry, "period_start": "2026-09-01T00:00:00Z", "period_end": "2026-10-01T00:00:00Z"}

    history = build_client_earnings_history((earlier, later))

    assert history[0]["period_start"] == "2026-09-01T00:00:00Z"
    assert history[1]["period_start"] == "2026-11-01T00:00:00Z"
