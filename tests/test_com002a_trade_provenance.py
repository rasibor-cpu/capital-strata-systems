from dataclasses import FrozenInstanceError

import pytest

from backend.commercialization.trade_provenance import (
    AttributionClass,
    MandateCompliance,
    TradeProvenance,
    attribution_reason,
)


def _accepted_css_trade() -> TradeProvenance:
    return TradeProvenance(
        trade_id="TRADE-001",
        advice_id="ADVICE-001",
        attribution_class=AttributionClass.CSS_ADVISED_ACCEPTED,
        mandate_compliance=MandateCompliance.COMPLIANT,
        recommendation_timestamp="2026-09-08T18:00:00Z",
        acceptance_timestamp="2026-09-08T18:01:00Z",
        evidence_refs=("trade-card:ADVICE-001",),
    )


def test_compliant_accepted_css_advice_is_attributable():
    record = _accepted_css_trade()

    assert record.css_performance_attributable is True
    assert record.shadow_fee_attribution_eligible is True
    assert record.customer_directed is False

    assert (
        attribution_reason(record)
        == "css_advice_accepted_and_mandate_compliant"
    )


def test_css_advice_without_acceptance_is_not_attributable():
    record = TradeProvenance(
        trade_id="TRADE-002",
        advice_id="ADVICE-002",
        attribution_class=AttributionClass.CSS_ADVISED,
        mandate_compliance=MandateCompliance.UNVERIFIED,
        recommendation_timestamp="2026-09-08T18:00:00Z",
        evidence_refs=("trade-card:ADVICE-002",),
    )

    assert record.css_performance_attributable is False
    assert record.shadow_fee_attribution_eligible is False

    assert (
        attribution_reason(record)
        == "css_advice_not_yet_authoritatively_accepted"
    )


def test_customer_directed_trade_never_enters_css_performance_book():
    record = TradeProvenance(
        trade_id="TRADE-003",
        attribution_class=AttributionClass.CUSTOMER_DIRECTED,
        mandate_compliance=MandateCompliance.OUTSIDE_CSS,
        evidence_refs=("customer-order:TRADE-003",),
    )

    assert record.css_performance_attributable is False
    assert record.shadow_fee_attribution_eligible is False
    assert record.customer_directed is True

    assert attribution_reason(record) == "customer_originated_trade"


def test_materially_modified_css_trade_is_customer_directed():
    record = TradeProvenance(
        trade_id="TRADE-004",
        advice_id="ADVICE-004",
        attribution_class=AttributionClass.CSS_MODIFIED,
        mandate_compliance=MandateCompliance.MODIFIED,
        recommendation_timestamp="2026-09-08T18:00:00Z",
        acceptance_timestamp="2026-09-08T18:01:00Z",
        evidence_refs=(
            "trade-card:ADVICE-004",
            "customer-modification:TRADE-004",
        ),
    )

    assert record.css_performance_attributable is False
    assert record.customer_directed is True

    assert (
        attribution_reason(record)
        == "customer_materially_modified_css_advice"
    )


def test_external_trade_is_not_css_performance_attributable():
    record = TradeProvenance(
        trade_id="TRADE-005",
        attribution_class=AttributionClass.EXTERNAL,
        mandate_compliance=MandateCompliance.OUTSIDE_CSS,
        evidence_refs=("broker-import:TRADE-005",),
    )

    assert record.css_performance_attributable is False
    assert record.customer_directed is True
    assert attribution_reason(record) == "activity_outside_css"


def test_accepted_css_trade_requires_advice_id():
    with pytest.raises(
        ValueError,
        match="CSS_ADVISED_ACCEPTED requires advice_id",
    ):
        TradeProvenance(
            trade_id="TRADE-006",
            attribution_class=AttributionClass.CSS_ADVISED_ACCEPTED,
            mandate_compliance=MandateCompliance.COMPLIANT,
            acceptance_timestamp="2026-09-08T18:01:00Z",
            evidence_refs=("acceptance:TRADE-006",),
        )


def test_accepted_css_trade_requires_compliant_mandate():
    with pytest.raises(
        ValueError,
        match="CSS_ADVISED_ACCEPTED requires COMPLIANT mandate",
    ):
        TradeProvenance(
            trade_id="TRADE-007",
            advice_id="ADVICE-007",
            attribution_class=AttributionClass.CSS_ADVISED_ACCEPTED,
            mandate_compliance=MandateCompliance.MODIFIED,
            acceptance_timestamp="2026-09-08T18:01:00Z",
            evidence_refs=("acceptance:TRADE-007",),
        )


def test_accepted_css_trade_requires_acceptance_evidence():
    with pytest.raises(
        ValueError,
        match="requires acceptance_timestamp",
    ):
        TradeProvenance(
            trade_id="TRADE-008",
            advice_id="ADVICE-008",
            attribution_class=AttributionClass.CSS_ADVISED_ACCEPTED,
            mandate_compliance=MandateCompliance.COMPLIANT,
            evidence_refs=("trade-card:ADVICE-008",),
        )

    with pytest.raises(
        ValueError,
        match="requires evidence",
    ):
        TradeProvenance(
            trade_id="TRADE-009",
            advice_id="ADVICE-009",
            attribution_class=AttributionClass.CSS_ADVISED_ACCEPTED,
            mandate_compliance=MandateCompliance.COMPLIANT,
            acceptance_timestamp="2026-09-08T18:01:00Z",
        )


def test_provenance_is_immutable():
    record = _accepted_css_trade()

    with pytest.raises(FrozenInstanceError):
        record.trade_id = "CHANGED"


def test_com002a_can_never_authorize_money_movement_or_execution():
    record = _accepted_css_trade()

    assert record.real_fee_collection_allowed is False
    assert record.client_funds_deduction_allowed is False
    assert record.execution_authority is False
