from dataclasses import FrozenInstanceError, replace
from decimal import Decimal, localcontext
import json
from pathlib import Path
import sqlite3

import pytest

import backend.app.persistence.repositories.base_repository as base_repository
import backend.app.persistence.migrations.runner as migration_runner
from backend.app.persistence.services.persistence_service import PersistenceService
from backend.commercialization.platform_access_fee_terms import (
    CommercialPlatformAccessFeeTerms, PlatformAccessBillingFrequency,
)
from backend.commercialization.performance_accounting import PerformanceAccountState, PerformanceAccountingTransition
from backend.commercialization.performance_compensation import PerformanceCompensationTerms, build_shadow_compensation_entitlement
from backend.commercialization.performance_crystallization import (
    PerformanceCompensationLifecyclePolicy, CrystallizationFrequency,
    CrystallizationStatus, build_crystallization_assessment,
)
from backend.commercialization.fx_conversion import build_fx_conversion_evidence
from backend.commercialization.final_fee_selection import build_final_fee_selection, FinalFeeBasis
from backend.commercialization.final_fee_settlement_readiness import (
    CommercialFinalFeeSettlementReadiness, build_final_fee_settlement_readiness,
)
from backend.commercialization.settlement_readiness import SettlementReadinessStatus, build_settlement_readiness
from backend.commercialization.billable_obligation import BillableObligationStatus, build_billable_obligation
from backend.commercialization.billing_profile import (
    BillingPartyType, PaymentTermsStatus, TaxTreatmentStatus, build_commercial_billing_profile,
)
from backend.commercialization.invoice_candidate import InvoiceCandidateStatus, build_invoice_candidate
from backend.commercialization.invoice_identity import build_invoice_identity_allocation
from backend.commercialization.invoice_issued import build_invoice_issued_record
from backend.commercialization.receivable_recognition import build_receivable_recognition
from backend.commercialization.invoice_correction import InvoiceCorrectionType, build_invoice_correction
from backend.commercialization.receivable_reversal import build_receivable_reversal
from backend.commercialization.receivable_economic_residual import build_receivable_economic_residual_projection


START = "2026-09-01T00:00:00Z"
END = "2026-10-01T00:00:00Z"
AT = "2026-10-02T12:00:00.123456+00:00"
REFS = ("contract:approved", "review:commercial")


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


def upstream(service, amount="0", currency="USD", rate="0.75", access_changes=None):
    access = CommercialPlatformAccessFeeTerms(
        "ACCESS-A", "USD", Decimal("29.99"), PlatformAccessBillingFrequency.MONTHLY,
        START, REFS, True, END,
    )
    if access_changes:
        access = replace(access, **access_changes)
    terms = PerformanceCompensationTerms("TERMS-A", currency, Decimal("0.20"), START, REFS, True)
    policy = PerformanceCompensationLifecyclePolicy(
        "POLICY-A", "TERMS-A", currency, CrystallizationFrequency.MONTHLY, START, REFS,
    )
    with localcontext() as context:
        context.prec = 128
        gain = Decimal(amount) * Decimal("5")
        transition = PerformanceAccountingTransition(
            "TRADE-A", PerformanceAccountState(currency),
            PerformanceAccountState(currency, gain, gain, Decimal("0")),
            gain, Decimal("0"), gain,
        )
        entitlement = build_shadow_compensation_entitlement(transition, terms, AT)
        assessment = build_crystallization_assessment(
            policy, (entitlement,), START, END, AT, CrystallizationStatus.ELIGIBLE, REFS,
        )
    conversion = None
    if currency != "USD":
        conversion = build_fx_conversion_evidence(
            fx_conversion_id="FX-A", source_currency=currency, target_currency="USD",
            source_amount=assessment.crystallizable_amount, fx_rate=Decimal(rate),
            rate_effective_at=AT, rate_source_reference="daily:approved", evidence_refs=REFS,
        )
    selection = build_final_fee_selection(
        access, terms, assessment, fee_selection_id="FEE-A", period_start=START,
        period_end=END, selected_at=AT, evidence_refs=REFS, fx_conversion=conversion,
    )
    service.platform_access_fee_terms.create_terms(access)
    service.performance_compensation_terms.create_terms(terms)
    service.performance_compensation_lifecycle_policies.create_policy(policy)
    service.crystallization_assessments.create_assessment(assessment)
    if conversion is not None:
        service.fx_conversion_evidence.create_conversion(conversion)
    service.final_fee_selections.create_selection(selection)
    return selection, assessment


def ready_and_billable(service, selection):
    readiness = build_final_fee_settlement_readiness(selection, SettlementReadinessStatus.READY, AT, REFS)
    service.settlement_readiness.create_readiness(readiness)
    obligation = build_billable_obligation(readiness, BillableObligationStatus.BILLABLE, AT, REFS)
    service.billable_obligations.create_obligation(obligation)
    return readiness, obligation


def profile():
    return build_commercial_billing_profile(
        billing_profile_id="BP-A", terms_id="TERMS-A", party_type=BillingPartyType.ORGANIZATION,
        bill_to_name="Example", bill_to_reference="bill-to:A", seller_reference="seller:CSS",
        tax_treatment_status=TaxTreatmentStatus.OUT_OF_SCOPE,
        payment_terms_status=PaymentTermsStatus.DEFINED_EXTERNALLY,
        effective_from=START, effective_to=END, evidence_refs=REFS,
    )


def invoice_and_receivable(service, obligation):
    billing = profile()
    service.billing_profiles.create_profile(billing)
    candidate = build_invoice_candidate(obligation, billing, InvoiceCandidateStatus.READY, AT, REFS)
    service.invoice_candidates.create_candidate(candidate)
    identity = build_invoice_identity_allocation(
        candidate, invoice_id="INV-A", invoice_number="CSS-001", allocated_at=AT, evidence_refs=REFS,
    )
    service.invoice_identity_allocations.create_allocation(identity)
    issued = build_invoice_issued_record(identity, issued_at=AT, evidence_refs=REFS)
    service.invoice_issued_records.create_issued_record(issued)
    receivable = build_receivable_recognition(issued, receivable_id="REC-A", recognized_at=AT, evidence_refs=REFS)
    service.receivable_recognitions.create_recognition(receivable)
    return candidate, identity, issued, receivable


@pytest.mark.parametrize("amount,currency,rate,expected", [
    ("0", "USD", "1", "29.99"), ("20.00", "USD", "1", "29.99"),
    ("29.99", "USD", "1", "29.99"), ("150.00", "USD", "1", "150.00"),
    ("100", "CAD", "0.75", "75"), ("20", "CAD", "0.75", "29.99"),
    ("20", "EUR", "1.10", "29.99"), ("150", "EUR", "1.10", "165"),
    ("100000", "NGN", "0.00065", "65"),
    ("150.12345678901234567890123456789", "USD", "1", "150.12345678901234567890123456789"),
])
def test_final_selection_flows_exactly_through_persisted_chain(service, amount, currency, rate, expected):
    selection, assessment = upstream(service, amount, currency, rate)
    before = repr(selection)
    readiness, obligation = ready_and_billable(service, selection)
    candidate, identity, issued, receivable = invoice_and_receivable(service, obligation)
    assert selection.selected_fee_amount == Decimal(expected)
    for value in (readiness.selected_fee_amount, obligation.billable_amount,
                  candidate.candidate_amount, identity.invoice_amount, issued.invoice_amount,
                  receivable.receivable_amount):
        # Structural provenance: no downstream arithmetic creates a new amount.
        assert value is selection.selected_fee_amount
    for record in (readiness, obligation, candidate, identity, issued, receivable):
        assert record.currency == "USD"
    for record in (readiness, obligation, candidate, identity, issued):
        assert (record.policy_id, record.terms_id, record.period_start, record.period_end) == (
            selection.policy_id, selection.terms_id, START, END,
        )
    if Decimal(amount) > 0:
        with localcontext() as context:
            context.prec = 128
            assert issued.invoice_amount != selection.platform_access_fee_amount + selection.performance_fee_billing_currency_amount
    if amount == "29.99":
        assert selection.selected_fee_basis is FinalFeeBasis.PERFORMANCE_COMPENSATION
    assert repr(selection) == before
    stored = service.settlement_readiness.get_by_period("POLICY-A", START, END)
    assert stored["final_fee_selection_id"] == "FEE-A"
    assert "crystallizable_amount" not in stored
    assert Decimal(stored["selected_fee_amount"]).as_tuple() == selection.selected_fee_amount.as_tuple()
    assert stored["assessed_at"] == AT
    assert tuple(json.loads(stored["evidence_refs_json"])) == REFS
    for table, column in (("commercial_billable_obligations", "billable_amount"),
                          ("commercial_invoice_candidates", "candidate_amount"),
                          ("commercial_invoice_identity_allocations", "invoice_amount"),
                          ("commercial_invoice_issued_records", "invoice_amount"),
                          ("commercial_receivable_recognitions", "receivable_amount")):
        row = service.settlement_readiness.fetch_one(f"SELECT {column}, currency FROM {table}")
        assert row[column] == str(selection.selected_fee_amount)
        assert row["currency"] == "USD"
    trace = service.settlement_readiness.fetch_one("""
        SELECT f.fee_selection_id, f.access_terms_id, f.terms_id, f.fx_conversion_id,
               a.access_fee_amount, i.invoice_id, r.receivable_id
        FROM commercial_receivable_recognitions r
        JOIN commercial_invoice_issued_records i ON i.invoice_id = r.invoice_id
        JOIN commercial_invoice_identity_allocations n ON n.invoice_id = i.invoice_id
        JOIN commercial_invoice_candidates c ON c.policy_id = n.policy_id
            AND c.period_start = n.period_start AND c.period_end = n.period_end
        JOIN commercial_billable_obligations b ON b.policy_id = c.policy_id
            AND b.period_start = c.period_start AND b.period_end = c.period_end
        JOIN commercial_settlement_readiness s ON s.policy_id = b.policy_id
            AND s.period_start = b.period_start AND s.period_end = b.period_end
        JOIN commercial_final_fee_selections f ON f.fee_selection_id = s.final_fee_selection_id
        JOIN platform_access_fee_terms a ON a.access_terms_id = f.access_terms_id
        WHERE r.receivable_id = 'REC-A'
    """)
    assert trace["fee_selection_id"] == "FEE-A"
    assert trace["access_terms_id"] == "ACCESS-A"
    assert trace["terms_id"] == "TERMS-A"
    assert trace["fx_conversion_id"] == (None if currency == "USD" else "FX-A")


@pytest.mark.parametrize("field,value", [("policy_id", "OTHER"), ("terms_id", "OTHER"),
    ("period_start", "2026-09-02T00:00:00Z"), ("period_end", "2026-10-02T00:00:00Z"),
    ("fee_selection_id", "MISSING")])
def test_inconsistent_selection_snapshot_rejected_before_billable(service, field, value):
    selection, _ = upstream(service)
    readiness = build_final_fee_settlement_readiness(replace(selection, **{field: value}),
                    SettlementReadinessStatus.READY, AT, REFS)
    with pytest.raises(ValueError):
        service.settlement_readiness.create_readiness(readiness)
    assert service.billable_obligations.list_all() == []
    assert service.settlement_readiness.list_all() == []


def test_inconsistent_selected_amount_rejected(service):
    selection, _ = upstream(service)
    forged = replace(selection, platform_access_fee_amount=Decimal("40"), selected_fee_amount=Decimal("40"))
    with pytest.raises(ValueError, match="amount"):
        service.settlement_readiness.create_readiness(build_final_fee_settlement_readiness(
            forged, SettlementReadinessStatus.READY, AT, REFS))


@pytest.mark.parametrize("field,value", [("currency", "CAD"), ("terms_id", "OTHER"),
                                        ("billable_amount", Decimal("100"))])
def test_billable_persistence_rejects_inconsistent_final_source(service, field, value):
    selection, _ = upstream(service)
    readiness = build_final_fee_settlement_readiness(selection, SettlementReadinessStatus.READY, AT, REFS)
    service.settlement_readiness.create_readiness(readiness)
    obligation = build_billable_obligation(readiness, BillableObligationStatus.BILLABLE, AT, REFS)
    with pytest.raises(ValueError, match="mismatch"):
        service.billable_obligations.create_obligation(replace(obligation, **{field: value}))
    assert service.billable_obligations.list_all() == []


def test_ineffective_access_prevents_downstream(service):
    with pytest.raises(ValueError, match="cover period"):
        upstream(service, access_changes={"effective_from": "2026-09-02T00:00:00Z"})
    assert service.billable_obligations.list_all() == []


def test_blocked_profile_never_produces_ready_candidate(service):
    selection, _ = upstream(service)
    _, obligation = ready_and_billable(service, selection)
    blocked = replace(profile(), payment_terms_status=PaymentTermsStatus.UNDETERMINED)
    with pytest.raises(ValueError, match="invoice-ready"):
        build_invoice_candidate(obligation, blocked, InvoiceCandidateStatus.READY, AT, REFS)
    assert service.invoice_candidates.list_all() == []


@pytest.mark.parametrize("status", [SettlementReadinessStatus.NOT_READY,
    SettlementReadinessStatus.PENDING_APPROVAL, SettlementReadinessStatus.BLOCKED,
    SettlementReadinessStatus.EXPIRED])
def test_nonready_final_fee_cannot_be_billable(service, status):
    selection, _ = upstream(service)
    readiness = build_final_fee_settlement_readiness(selection, status, AT, REFS)
    service.settlement_readiness.create_readiness(readiness)
    with pytest.raises(ValueError, match="READY"):
        build_billable_obligation(readiness, BillableObligationStatus.BILLABLE, AT, REFS)
    blocked = build_billable_obligation(readiness, BillableObligationStatus.BLOCKED, AT, REFS)
    with pytest.raises(ValueError, match="READY"):
        service.billable_obligations.create_obligation(replace(blocked, status=BillableObligationStatus.BILLABLE))


def test_correction_reversal_and_residual_remain_documentary(service):
    selection, _ = upstream(service, "150", "CAD")
    _, obligation = ready_and_billable(service, selection)
    _, _, issued, receivable = invoice_and_receivable(service, obligation)
    before = service.invoice_issued_records.get_by_invoice_id("INV-A")
    correction = build_invoice_correction(issued, correction_id="COR-A",
        correction_type=InvoiceCorrectionType.VOID, corrected_at=AT,
        reason_reference="reason:void", evidence_refs=REFS)
    service.invoice_corrections.create_correction(correction)
    with pytest.raises(ValueError, match="blocks receivable"):
        build_receivable_recognition(issued, receivable_id="REC-B", recognized_at=AT,
                                    evidence_refs=REFS, corrections=(correction,))
    reversal = build_receivable_reversal(receivable, correction, reversal_id="REV-A",
                    reversed_at=AT, reason_reference="reason:reversal", evidence_refs=REFS)
    service.receivable_reversals.create_reversal(reversal)
    assert reversal.reversal_amount == selection.selected_fee_amount
    residual = build_receivable_economic_residual_projection(receivable, reversal=reversal, as_of=AT)
    assert residual.economic_residual_amount == 0
    assert service.invoice_issued_records.get_by_invoice_id("INV-A") == before
    assert receivable.receivable_amount == selection.selected_fee_amount


def test_readiness_is_immutable_and_has_no_crystallization_amount(service):
    selection, _ = upstream(service)
    record = build_final_fee_settlement_readiness(selection, SettlementReadinessStatus.READY, AT, REFS)
    assert not hasattr(record, "crystallizable_amount")
    with pytest.raises(FrozenInstanceError):
        record.selection = selection
    for name in dir(record):
        if name.endswith("_allowed") or name == "execution_authority":
            assert getattr(record, name) is False


@pytest.mark.parametrize("changes", [dict(status="READY"), dict(assessed_at="2026-10-02"),
    dict(assessed_at="2026-10-02T00:00:00+01:00"), dict(evidence_refs=()), dict(evidence_refs=["mutable"])])
def test_readiness_validation(service, changes):
    selection, _ = upstream(service)
    with pytest.raises((TypeError, ValueError)):
        replace(CommercialFinalFeeSettlementReadiness(selection, SettlementReadinessStatus.READY, AT, REFS), **changes)


def test_duplicate_readiness_does_not_overwrite(service):
    selection, _ = upstream(service)
    readiness, _ = ready_and_billable(service, selection)
    before = service.settlement_readiness.get_by_period("POLICY-A", START, END)
    with pytest.raises(sqlite3.IntegrityError):
        service.settlement_readiness.create_readiness(readiness)
    assert service.settlement_readiness.get_by_period("POLICY-A", START, END) == before


def test_migration_preserves_legacy_rows_and_repository_contract(service):
    # Exercise a real pre-027 schema with an existing legacy readiness and
    # downstream obligation, then apply only the additive/rename migration.
    conn = service.settlement_readiness.connection
    conn.execute("ALTER TABLE commercial_settlement_readiness RENAME COLUMN economic_amount TO crystallizable_amount")
    conn.execute("DROP INDEX idx_settlement_readiness_final_selection")
    conn.execute("ALTER TABLE commercial_settlement_readiness DROP COLUMN final_fee_selection_id")
    selection, assessment = upstream(service, "20")
    legacy = build_settlement_readiness(assessment, SettlementReadinessStatus.READY, AT, REFS)
    service.settlement_readiness.create_readiness(legacy)
    obligation = build_billable_obligation(legacy, BillableObligationStatus.BILLABLE, AT, REFS)
    service.billable_obligations.create_obligation(obligation)
    before = service.settlement_readiness.get_by_period("POLICY-A", START, END)
    conn.executescript(Path("backend/app/persistence/migrations/sql/027_final_fee_readiness.sql").read_text())
    assert service.settlement_readiness.get_by_period("POLICY-A", START, END) == before
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert service.billable_obligations.get_by_period("POLICY-A", START, END)["billable_amount"] == str(assessment.crystallizable_amount)
    # Existing period uniqueness prevents billing both the legacy and final fee.
    with pytest.raises(sqlite3.IntegrityError):
        service.settlement_readiness.create_readiness(build_final_fee_settlement_readiness(
            selection, SettlementReadinessStatus.READY, AT, REFS))


@pytest.mark.parametrize("field,value", [("access_terms_id", "OTHER-ACCESS"),
    ("evidence_refs", ("different:source",)), ("selected_at", "2026-10-03T00:00:00Z")])
def test_readiness_checks_complete_source_snapshot(service, field, value):
    selection, _ = upstream(service)
    readiness = build_final_fee_settlement_readiness(replace(selection, **{field: value}),
                    SettlementReadinessStatus.READY, AT, REFS)
    with pytest.raises(ValueError, match="persisted source"):
        service.settlement_readiness.create_readiness(readiness)
    assert service.settlement_readiness.list_all() == []
