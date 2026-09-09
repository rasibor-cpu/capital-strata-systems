from dataclasses import FrozenInstanceError, replace
from decimal import Decimal, localcontext

import pytest

from backend.commercialization.receivable_economic_residual import (
    build_receivable_economic_residual_projection as project,
    ReceivableEconomicResidualIneligibleError,
)
from backend.commercialization.receivable_recognition import CommercialReceivableRecognitionRecord
from backend.commercialization.receivable_reversal import CommercialReceivableReversalRecord
from backend.commercialization.receivable_payment_allocation import CommercialReceivablePaymentAllocationRecord
from backend.commercialization.receivable_credit import CommercialReceivableCreditRecord
from backend.commercialization.receivable_writeoff import CommercialReceivableWriteOffRecord


AS_OF = "2026-04-15T12:00:00+00:00"


def recognition(amount="100"):
    return CommercialReceivableRecognitionRecord(
        "REC-A", "INV-A", "BP-A", "CAD", Decimal(amount), AS_OF, ("recognition:A",),
    )


def event(kind, amount="10", event_id="EVENT-A"):
    common = dict(receivable_id="REC-A", invoice_id="INV-A", currency="CAD",
                  evidence_refs=("event:A",))
    if kind == "allocations":
        return CommercialReceivablePaymentAllocationRecord(
            **common, allocation_id=event_id, payment_id="PAY-A",
            allocated_amount=Decimal(amount), allocated_at=AS_OF,
        )
    if kind == "credits":
        return CommercialReceivableCreditRecord(
            **common, credit_id=event_id, credit_amount=Decimal(amount),
            credited_at=AS_OF, reason_reference="reason:A",
        )
    return CommercialReceivableWriteOffRecord(
        **common, writeoff_id=event_id, writeoff_amount=Decimal(amount),
        written_off_at=AS_OF, reason_reference="reason:A",
    )


def reversal():
    return CommercialReceivableReversalRecord(
        "REV-A", "REC-A", "INV-A", "COR-A", "CAD", Decimal("100"),
        AS_OF, "reason:A", ("reversal:A",),
    )


KINDS = ("allocations", "credits", "writeoffs")
TOTALS = dict(allocations="allocated_amount", credits="credited_amount",
              writeoffs="written_off_amount")


def test_recognition_only():
    result = project(recognition(), as_of=AS_OF)
    assert result.economic_residual_amount == Decimal("100")
    assert result.recognized_amount == Decimal("100")
    assert result.reversed_amount == Decimal("0")
    assert (result.receivable_id, result.invoice_id, result.currency, result.as_of) == (
        "REC-A", "INV-A", "CAD", AS_OF,
    )
    for name in TOTALS.values():
        assert getattr(result, name) == Decimal("0")
    for name in ("payment_events_included", "credit_events_included",
                 "writeoff_events_included", "is_complete_economic_residual"):
        assert getattr(result, name) is True
        with pytest.raises(ValueError, match=name):
            replace(result, **{name: False})
    for name in dir(result):
        if name.endswith("_allowed") or name == "execution_authority":
            assert getattr(result, name) is False


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("count", (1, 3))
def test_single_and_multiple_reductions(kind, count):
    result = project(recognition(), as_of=AS_OF,
                     **{kind: tuple(event(kind, event_id=str(i)) for i in range(count))})
    assert getattr(result, TOTALS[kind]) == Decimal(10 * count)
    assert result.economic_residual_amount == Decimal(100 - 10 * count)


@pytest.mark.parametrize("amount,expected", [("10", "70"), ("0", "100"), ("100", "0")])
def test_mixed_and_zero_residual(amount, expected):
    snapshots = {kind: (event(kind, amount if i == 0 or amount != "100" else "0"),)
                 for i, kind in enumerate(KINDS)}
    assert project(recognition(), as_of=AS_OF, **snapshots).economic_residual_amount == Decimal(expected)


@pytest.mark.parametrize("kind", KINDS)
def test_excess_reductions(kind):
    with pytest.raises(ReceivableEconomicResidualIneligibleError, match="exceed"):
        project(recognition(), as_of=AS_OF, **{kind: (event(kind, "101"),)})


def test_combined_excess():
    with pytest.raises(ReceivableEconomicResidualIneligibleError, match="exceed"):
        project(recognition(), as_of=AS_OF, **{kind: (event(kind, "40"),) for kind in KINDS})


@pytest.mark.parametrize("historical", (False, True))
def test_full_reversal_preserves_all_history(historical):
    snapshots = {kind: (event(kind, "120"),) for kind in KINDS} if historical else {}
    result = project(recognition(), as_of=AS_OF, reversal=reversal(), **snapshots)
    assert result.reversed_amount == Decimal("100")
    assert result.economic_residual_amount == Decimal("0")
    for name in TOTALS.values():
        assert getattr(result, name) == Decimal("120" if historical else "0")


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("field,value", [("receivable_id", "OTHER"), ("invoice_id", "OTHER"), ("currency", "USD")])
@pytest.mark.parametrize("reversed", (False, True))
def test_snapshot_mismatch(kind, field, value, reversed):
    with pytest.raises(ReceivableEconomicResidualIneligibleError, match=field):
        project(recognition(), as_of=AS_OF, reversal=reversal() if reversed else None,
                **{kind: (replace(event(kind), **{field: value}),)})


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("reversed", (False, True))
def test_duplicate_ids(kind, reversed):
    with pytest.raises(ReceivableEconomicResidualIneligibleError, match="duplicate"):
        project(recognition(), as_of=AS_OF, reversal=reversal() if reversed else None,
                **{kind: (event(kind), event(kind, "20"))})


@pytest.mark.parametrize("field,value", [("receivable_id", "OTHER"), ("invoice_id", "OTHER"),
                                         ("currency", "USD"), ("reversal_amount", Decimal("99"))])
def test_reversal_mismatch(field, value):
    with pytest.raises(ReceivableEconomicResidualIneligibleError, match=field):
        project(recognition(), as_of=AS_OF, reversal=replace(reversal(), **{field: value}))


@pytest.mark.parametrize("as_of", ["2026-04-15T12:00:00", "2026-04-15T12:00:00+01:00"])
def test_invalid_time(as_of):
    with pytest.raises(ValueError, match="UTC"):
        project(recognition(), as_of=as_of)


def test_caller_snapshot_not_filtered_and_inputs_immutable():
    rec = recognition()
    rev = reversal()
    snapshots = {kind: [event(kind)] for kind in KINDS}
    before = repr((rec, rev, snapshots))
    result = project(rec, as_of="2020-01-01T00:00:00Z", reversal=rev, **snapshots)
    assert all(getattr(result, name) == Decimal("10") for name in TOTALS.values())
    assert repr((rec, rev, snapshots)) == before
    with pytest.raises(FrozenInstanceError):
        result.economic_residual_amount = Decimal("1")


def test_exact_decimal_independent_of_context():
    rec = recognition("123456789012345678901234567890.123456789")
    with localcontext() as context:
        context.prec = 5
        result = project(rec, as_of=AS_OF,
                         allocations=(event("allocations", "0.000000001"),),
                         credits=(event("credits", "0.000000002"),),
                         writeoffs=(event("writeoffs", "0.000000003"),))
        assert context.prec == 5
    assert result.economic_residual_amount == Decimal("123456789012345678901234567890.123456783")
    assert all(isinstance(getattr(result, name), Decimal) for name in
               (*TOTALS.values(), "recognized_amount", "reversed_amount", "economic_residual_amount"))


@pytest.mark.parametrize("kind", KINDS)
def test_aggregate_exact_decimal(kind):
    result = project(recognition("200000000000000000000000000000"), as_of=AS_OF,
                     **{kind: (event(kind, "100000000000000000000000000000"),
                               event(kind, "0.000000001", "EVENT-B"))})
    assert getattr(result, TOTALS[kind]) == Decimal("100000000000000000000000000000.000000001")
    assert result.economic_residual_amount == Decimal("99999999999999999999999999999.999999999")


@pytest.mark.parametrize("kind", KINDS)
def test_invalid_event_type(kind):
    with pytest.raises(TypeError, match="snapshot"):
        project(recognition(), as_of=AS_OF, **{kind: (object(),)})


def test_invalid_recognition_and_reversal_types():
    with pytest.raises(TypeError, match="recognition"):
        project(object(), as_of=AS_OF)
    with pytest.raises(TypeError, match="reversal"):
        project(recognition(), as_of=AS_OF, reversal=object())
