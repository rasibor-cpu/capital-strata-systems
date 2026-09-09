from dataclasses import FrozenInstanceError, fields, replace
from decimal import Decimal, localcontext
import json
import sqlite3

import pytest

import backend.app.persistence.repositories.base_repository as base_repository
import backend.app.persistence.migrations.runner as migration_runner
from backend.app.persistence.services.persistence_service import PersistenceService
from backend.commercialization.fx_conversion import (
    CommercialFxConversionEvidence, build_fx_conversion_evidence,
)
from backend.commercialization.final_fee_selection import (
    CommercialFinalFeeSelection, FinalFeeBasis, build_final_fee_selection,
)
from backend.commercialization.platform_access_fee_terms import (
    CommercialPlatformAccessFeeTerms, PlatformAccessBillingFrequency,
)
from backend.commercialization.performance_compensation import (
    PerformanceCompensationTerms, build_shadow_compensation_entitlement,
)
from backend.commercialization.performance_accounting import (
    PerformanceAccountState, PerformanceAccountingTransition,
)
from backend.commercialization.performance_crystallization import (
    CrystallizationAssessment, CrystallizationStatus, CrystallizationFrequency,
    PerformanceCompensationLifecyclePolicy, build_crystallization_assessment,
)


START = "2026-09-01T00:00:00Z"
END = "2026-10-01T00:00:00Z"
AT = "2026-10-01T12:00:00.123456+00:00"
REFS = ("decision:review", "evidence:approved")


def access():
    return CommercialPlatformAccessFeeTerms(
        "ACCESS-A", "USD", Decimal("29.99"), PlatformAccessBillingFrequency.MONTHLY,
        START, REFS, True, END,
    )


def performance_terms(currency="USD"):
    return PerformanceCompensationTerms(
        "TERMS-A", currency, Decimal("0.20"), START, REFS, True,
    )


def assessment(amount="10", currency="USD"):
    return CrystallizationAssessment(
        "POLICY-A", "TERMS-A", currency, START, END, AT,
        Decimal(amount), Decimal(amount), CrystallizationStatus.ELIGIBLE, REFS,
    )


def fx(currency="CAD", amount="100", rate="0.75", **changes):
    args = dict(fx_conversion_id="FX-A", source_currency=currency, target_currency="USD",
                source_amount=Decimal(amount), fx_rate=Decimal(rate), rate_effective_at=AT,
                rate_source_reference="daily-rate:caller-approved", evidence_refs=REFS)
    args.update(changes)
    return build_fx_conversion_evidence(**args)


def select(amount="10", currency="USD", conversion=None, **changes):
    args = dict(access_terms=access(), performance_terms=performance_terms(currency),
                performance=assessment(amount, currency), fee_selection_id="FEE-A",
                period_start=START, period_end=END, selected_at=AT,
                evidence_refs=REFS, fx_conversion=conversion)
    args.update(changes)
    return build_final_fee_selection(**args)


@pytest.mark.parametrize("currency,rate,expected", [("CAD", "0.75", "75"),
                          ("EUR", "1.1", "110"), ("NGN", "0.00065", "0.065")])
def test_supported_fx_examples(currency, rate, expected):
    record = fx(currency, rate=rate)
    assert record.converted_amount == Decimal(expected)
    assert record.fx_rate == Decimal(rate)
    assert record.rate_source_reference == "daily-rate:caller-approved"
    assert record.evidence_refs == REFS
    assert record.rate_effective_at == AT


@pytest.mark.parametrize("field", ["source_amount", "converted_amount", "fx_rate"])
@pytest.mark.parametrize("value", [0.75, "0.75", Decimal("NaN"), Decimal("Infinity"), Decimal("-1")])
def test_invalid_fx_amounts(field, value):
    with pytest.raises((TypeError, ValueError)):
        replace(fx(), **{field: value})


def test_zero_rate_rejected_but_zero_amount_supported():
    with pytest.raises(ValueError, match="positive"):
        fx(rate="0")
    assert fx(amount="0").converted_amount == Decimal("0")


@pytest.mark.parametrize("field", ["source_currency", "target_currency"])
@pytest.mark.parametrize("value", ["", " ", "usd", "US", "USDD", "123", " USD"])
def test_invalid_currency_codes(field, value):
    with pytest.raises(ValueError):
        replace(fx(), **{field: value})


def test_identity_and_non_usd_target_rejected():
    with pytest.raises(ValueError, match="same-currency"):
        fx(currency="USD")
    with pytest.raises(ValueError, match="target_currency"):
        fx(target_currency="EUR")


def test_converted_amount_mismatch_rejected():
    with pytest.raises(ValueError, match="exactly"):
        replace(fx(), converted_amount=Decimal("75.01"))


@pytest.mark.parametrize("timestamp", ["2026-10-01T12:00:00", "2026-10-01T12:00:00+01:00"])
def test_fx_time_policy(timestamp):
    with pytest.raises(ValueError, match="UTC"):
        fx(rate_effective_at=timestamp)


@pytest.mark.parametrize("field,value", [("fx_conversion_id", ""),
                 ("rate_source_reference", ""), ("evidence_refs", ()),
                 ("evidence_refs", (" padded",)), ("evidence_refs", ["mutable"])])
def test_fx_evidence_validation(field, value):
    with pytest.raises((ValueError, TypeError)):
        fx(**{field: value})


def test_exact_product_under_low_precision():
    with localcontext() as context:
        context.prec = 3
        record = fx(amount="12345678901234567890.123456789", rate="0.123456789")
        assert context.prec == 3
    assert record.converted_amount == Decimal("1524157875171467887.517146788750190521")
    with pytest.raises(FrozenInstanceError):
        record.fx_rate = Decimal("2")


@pytest.mark.parametrize("amount,expected,basis", [
    ("0", "29.99", FinalFeeBasis.PLATFORM_ACCESS),
    ("10", "29.99", FinalFeeBasis.PLATFORM_ACCESS),
    ("29.98", "29.99", FinalFeeBasis.PLATFORM_ACCESS),
    ("29.99", "29.99", FinalFeeBasis.PERFORMANCE_COMPENSATION),
    ("30", "30", FinalFeeBasis.PERFORMANCE_COMPENSATION),
    ("300", "300", FinalFeeBasis.PERFORMANCE_COMPENSATION),
])
def test_maximum_never_additive(amount, expected, basis):
    result = select(amount)
    assert result.selected_fee_amount == Decimal(expected)
    assert result.selected_fee_basis is basis
    assert result.selected_fee_amount in (result.platform_access_fee_amount,
                                         result.performance_fee_billing_currency_amount)
    if Decimal(amount) > 0:
        assert result.selected_fee_amount != Decimal("29.99") + Decimal(amount)
    assert result.fx_conversion_id is None
    assert result.performance_fee_source_amount == result.performance_fee_billing_currency_amount


@pytest.mark.parametrize("currency,amount,rate,expected", [
    ("CAD", "10", "0.75", "29.99"), ("CAD", "100", "0.75", "75"),
    ("EUR", "100", "1.1", "110"), ("NGN", "100000", "0.00065", "65"),
])
def test_fx_normalized_selection(currency, amount, rate, expected):
    conversion = fx(currency, amount, rate)
    result = select(amount, currency, conversion)
    assert result.selected_fee_amount == Decimal(expected)
    assert result.fx_conversion_id == conversion.fx_conversion_id
    assert result.performance_fee_billing_currency_amount == conversion.converted_amount
    assert result.billing_currency == "USD"


def test_zero_zero_tie():
    result = select("0", access_terms=replace(access(), access_fee_amount=Decimal("0")))
    assert result.selected_fee_amount == 0
    assert result.selected_fee_basis is FinalFeeBasis.PERFORMANCE_COMPENSATION


def test_missing_fx_rejected():
    with pytest.raises(ValueError, match="requires FX"):
        select("100", "CAD")


@pytest.mark.parametrize("conversion", [fx("EUR"), fx(amount="90")])
def test_fx_source_mismatch(conversion):
    with pytest.raises(ValueError, match="mismatch"):
        select("100", "CAD", conversion)


def test_usd_rejects_unnecessary_fx():
    with pytest.raises(ValueError, match="bypass"):
        select("100", conversion=fx())


@pytest.mark.parametrize("field,value", [("period_start", "2026-09-02T00:00:00Z"),
    ("period_end", "2026-10-02T00:00:00Z"),
    ("period_start", "2026-09-01T00:00:00+00:00")])
def test_period_identity_mismatch(field, value):
    with pytest.raises(ValueError, match="period mismatch"):
        select(**{field: value})


@pytest.mark.parametrize("change", [dict(effective_from="2026-09-02T00:00:00Z"),
                                    dict(effective_to="2026-09-30T00:00:00Z")])
def test_access_must_cover_entire_period(change):
    with pytest.raises(ValueError, match="cover period"):
        select(access_terms=replace(access(), **change))


def test_open_ended_access_covers_period():
    assert select(access_terms=replace(access(), effective_to=None)).selected_fee_amount == Decimal("29.99")


@pytest.mark.parametrize("which", ["access", "performance"])
def test_unaccepted_terms_rejected(which):
    kwargs = {"access_terms": replace(access(), accepted=False)} if which == "access" else {
        "performance_terms": replace(performance_terms(), accepted=False)}
    with pytest.raises(ValueError, match="accepted"):
        select(**kwargs)


@pytest.mark.parametrize("change", [dict(terms_id="OTHER"), dict(currency="CAD")])
def test_performance_terms_mismatch(change):
    with pytest.raises(ValueError, match="mismatch"):
        select(performance_terms=replace(performance_terms(), **change))


@pytest.mark.parametrize("status", [CrystallizationStatus.BLOCKED,
                                   CrystallizationStatus.NOT_DUE, CrystallizationStatus.EXPIRED])
def test_noneligible_assessment_rejected(status):
    with pytest.raises(ValueError, match="ELIGIBLE"):
        select(performance=replace(assessment(), status=status))


@pytest.mark.parametrize("field,value", [("billing_currency", "CAD"),
    ("selected_fee_amount", Decimal("39.99")),
    ("selected_fee_basis", FinalFeeBasis.PERFORMANCE_COMPENSATION),
    ("performance_fee_billing_currency_amount", Decimal("11")),
    ("selected_at", "2026-10-01T12:00:00"), ("selected_at", "2026-10-01T12:00:00+01:00"),
    ("period_start", "2026-09-01"), ("period_end", START),
    ("selected_fee_amount", 29.99), ("evidence_refs", ()), ("fee_selection_id", "")])
def test_selection_record_rejects_invalid_values(field, value):
    with pytest.raises((ValueError, TypeError)):
        replace(select(), **{field: value})


def test_selection_immutable_exact_and_inputs_unchanged():
    amount = "300.12345678901234567890123456789"
    inputs = (access(), performance_terms(), assessment(amount))
    before = repr(inputs)
    with localcontext() as context:
        context.prec = 3
        result = build_final_fee_selection(*inputs, fee_selection_id="FEE-A",
                    period_start=START, period_end=END, selected_at=AT, evidence_refs=REFS)
    assert result.selected_fee_amount.as_tuple() == Decimal(amount).as_tuple()
    assert repr(inputs) == before
    with pytest.raises(FrozenInstanceError):
        result.selected_fee_amount = Decimal("0")


def test_uses_compensation_after_loss_recovery_and_rate():
    terms = performance_terms()
    previous = PerformanceAccountState("USD", Decimal("80"), Decimal("100"), Decimal("20"))
    current = PerformanceAccountState("USD", Decimal("150"), Decimal("150"), Decimal("0"))
    transition = PerformanceAccountingTransition("TRADE-A", previous, current,
                    Decimal("70"), Decimal("20"), Decimal("50"))
    entitlement = build_shadow_compensation_entitlement(transition, terms, AT)
    policy = PerformanceCompensationLifecyclePolicy("POLICY-A", "TERMS-A", "USD",
                    CrystallizationFrequency.MONTHLY, START, REFS)
    period = build_crystallization_assessment(policy, (entitlement,), START, END, AT,
                    CrystallizationStatus.ELIGIBLE, REFS)
    result = select(performance=period)
    assert result.performance_fee_source_amount == Decimal("10")
    assert result.selected_fee_amount == Decimal("29.99")


@pytest.fixture
def service(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    monkeypatch.setattr(base_repository, "get_connection", lambda: conn)
    monkeypatch.setattr(migration_runner, "get_connection", lambda: conn)
    try:
        yield PersistenceService()
    finally:
        conn.close()


def seed(service, amount="100", currency="CAD", conversion=None):
    service.platform_access_fee_terms.create_terms(access())
    service.performance_compensation_terms.create_terms(performance_terms(currency))
    service.performance_compensation_lifecycle_policies.create_policy(
        PerformanceCompensationLifecyclePolicy("POLICY-A", "TERMS-A", currency,
                    CrystallizationFrequency.MONTHLY, START, REFS))
    service.crystallization_assessments.create_assessment(assessment(amount, currency))
    if conversion is not None:
        service.fx_conversion_evidence.create_conversion(conversion)


def assert_row_round_trip(record, row):
    for field in fields(record):
        value = getattr(record, field.name)
        if field.name == "evidence_refs":
            assert tuple(json.loads(row["evidence_refs_json"])) == value
        elif isinstance(value, Decimal):
            assert Decimal(row[field.name]).as_tuple() == value.as_tuple()
        elif isinstance(value, FinalFeeBasis):
            assert row[field.name] == value.value
        else:
            assert row[field.name] == value


def test_fx_persistence_and_duplicate(service):
    record = fx(amount="123.1234567890123456789", rate="0.750000000001")
    repo = service.fx_conversion_evidence
    repo.create_conversion(record)
    before = repo.get_by_fx_conversion_id("FX-A")
    assert_row_round_trip(record, before)
    with pytest.raises(sqlite3.IntegrityError):
        repo.create_conversion(fx(amount="999"))
    assert repo.get_by_fx_conversion_id("FX-A") == before
    assert repo.get_by_fx_conversion_id("missing") is None
    assert len(repo.list_all()) == 1


@pytest.mark.parametrize("currency", ["USD", "CAD", "EUR", "NGN"])
def test_selection_persistence_and_duplicate(service, currency):
    conversion = fx(currency) if currency != "USD" else None
    seed(service, currency=currency, conversion=conversion)
    record = select("100", currency, conversion)
    repo = service.final_fee_selections
    repo.create_selection(record)
    before = repo.get_by_fee_selection_id("FEE-A")
    assert_row_round_trip(record, before)
    with pytest.raises(sqlite3.IntegrityError):
        repo.create_selection(record)
    assert repo.get_by_fee_selection_id("FEE-A") == before
    assert len(repo.list_all()) == 1
    assert repo.get_by_fee_selection_id("missing") is None


@pytest.mark.parametrize("field,value", [("access_terms_id", "MISSING"),
                  ("terms_id", "MISSING"), ("policy_id", "MISSING"), ("fx_conversion_id", "MISSING")])
def test_stale_reference_rejected(service, field, value):
    conversion = fx()
    seed(service, conversion=conversion)
    with pytest.raises(ValueError, match="missing persisted"):
        service.final_fee_selections.create_selection(replace(select("100", "CAD", conversion), **{field: value}))
    assert service.final_fee_selections.list_all() == []


def test_persisted_fx_snapshot_mismatch(service):
    seed(service, conversion=fx(rate="0.8"))
    record = select("100", "CAD", fx())
    with pytest.raises(ValueError, match="snapshot"):
        service.final_fee_selections.create_selection(record)


def test_persisted_access_snapshot_mismatch(service):
    seed(service, amount="10", currency="USD")
    record = select(access_terms=replace(access(), access_fee_amount=Decimal("40")))
    with pytest.raises(ValueError, match="snapshot"):
        service.final_fee_selections.create_selection(record)


def test_persisted_performance_snapshot_mismatch(service):
    seed(service, amount="100", currency="USD")
    with pytest.raises(ValueError, match="snapshot"):
        service.final_fee_selections.create_selection(select("90"))


def test_service_migrations_idempotent(service):
    again = PersistenceService()
    health = again.healthcheck()["repositories"]
    assert health["fx_conversion_evidence"] and health["final_fee_selections"]
    versions = migration_runner.get_applied_versions()
    assert {"025_fx_conversion", "026_final_fee_selection"} <= versions
    assert not hasattr(service.final_fee_selections, "update_selection")
    assert not hasattr(service.fx_conversion_evidence, "delete_conversion")
