from dataclasses import FrozenInstanceError

import pytest

from backend.commercialization.billing_profile import (
    BillingPartyType,
    CommercialBillingProfile,
    PaymentTermsStatus,
    TaxTreatmentStatus,
    build_commercial_billing_profile,
)


EFFECTIVE_FROM = "2026-01-01T00:00:00+00:00"
EFFECTIVE_TO = "2026-12-31T00:00:00+00:00"


def _profile(
    *,
    billing_profile_id: str = "BP-001",
    terms_id: str = "TERMS-001",
    party_type: BillingPartyType = BillingPartyType.ORGANIZATION,
    bill_to_name: str = "Acme Capital Ltd",
    bill_to_reference: str = "BILLTO-ACME-1",
    seller_reference: str = "SELLER-CSS-1",
    tax_treatment_status: TaxTreatmentStatus = (
        TaxTreatmentStatus.OUT_OF_SCOPE
    ),
    payment_terms_status: PaymentTermsStatus = (
        PaymentTermsStatus.DEFINED_EXTERNALLY
    ),
    effective_from: str = EFFECTIVE_FROM,
    evidence_refs: tuple[str, ...] = ("profile:BP-001",),
    effective_to: str | None = None,
) -> CommercialBillingProfile:
    return build_commercial_billing_profile(
        billing_profile_id=billing_profile_id,
        terms_id=terms_id,
        party_type=party_type,
        bill_to_name=bill_to_name,
        bill_to_reference=bill_to_reference,
        seller_reference=seller_reference,
        tax_treatment_status=tax_treatment_status,
        payment_terms_status=payment_terms_status,
        effective_from=effective_from,
        evidence_refs=evidence_refs,
        effective_to=effective_to,
    )


def test_valid_individual_profile():
    profile = _profile(
        party_type=BillingPartyType.INDIVIDUAL,
        bill_to_name="Jane Doe",
        bill_to_reference="BILLTO-JD-1",
    )

    assert profile.party_type is BillingPartyType.INDIVIDUAL
    assert profile.billing_profile_id == "BP-001"
    assert profile.terms_id == "TERMS-001"
    assert profile.bill_to_name == "Jane Doe"


def test_valid_organization_profile():
    profile = _profile(party_type=BillingPartyType.ORGANIZATION)

    assert profile.party_type is BillingPartyType.ORGANIZATION
    assert profile.seller_reference == "SELLER-CSS-1"


def test_blank_billing_profile_id_rejected():
    with pytest.raises(ValueError, match="billing_profile_id"):
        _profile(billing_profile_id=" ")


def test_blank_terms_id_rejected():
    with pytest.raises(ValueError, match="terms_id"):
        _profile(terms_id="")


def test_blank_bill_to_name_rejected():
    with pytest.raises(ValueError, match="bill_to_name"):
        _profile(bill_to_name="")


def test_blank_bill_to_reference_rejected():
    with pytest.raises(ValueError, match="bill_to_reference"):
        _profile(bill_to_reference=" ")


def test_blank_seller_reference_rejected():
    with pytest.raises(ValueError, match="seller_reference"):
        _profile(seller_reference="")


def test_invalid_party_type_rejected():
    with pytest.raises(TypeError, match="BillingPartyType"):
        CommercialBillingProfile(
            billing_profile_id="BP-001",
            terms_id="TERMS-001",
            party_type="ORGANIZATION",  # type: ignore[arg-type]
            bill_to_name="Acme Capital Ltd",
            bill_to_reference="BILLTO-ACME-1",
            seller_reference="SELLER-CSS-1",
            tax_treatment_status=TaxTreatmentStatus.OUT_OF_SCOPE,
            payment_terms_status=PaymentTermsStatus.NOT_REQUIRED,
            effective_from=EFFECTIVE_FROM,
            evidence_refs=("profile:BP-001",),
        )


def test_invalid_tax_status_rejected():
    with pytest.raises(TypeError, match="TaxTreatmentStatus"):
        CommercialBillingProfile(
            billing_profile_id="BP-001",
            terms_id="TERMS-001",
            party_type=BillingPartyType.ORGANIZATION,
            bill_to_name="Acme Capital Ltd",
            bill_to_reference="BILLTO-ACME-1",
            seller_reference="SELLER-CSS-1",
            tax_treatment_status="EXEMPT",  # type: ignore[arg-type]
            payment_terms_status=PaymentTermsStatus.NOT_REQUIRED,
            effective_from=EFFECTIVE_FROM,
            evidence_refs=("profile:BP-001",),
        )


def test_invalid_payment_terms_status_rejected():
    with pytest.raises(TypeError, match="PaymentTermsStatus"):
        CommercialBillingProfile(
            billing_profile_id="BP-001",
            terms_id="TERMS-001",
            party_type=BillingPartyType.ORGANIZATION,
            bill_to_name="Acme Capital Ltd",
            bill_to_reference="BILLTO-ACME-1",
            seller_reference="SELLER-CSS-1",
            tax_treatment_status=TaxTreatmentStatus.OUT_OF_SCOPE,
            payment_terms_status="NET_30",  # type: ignore[arg-type]
            effective_from=EFFECTIVE_FROM,
            evidence_refs=("profile:BP-001",),
        )


def test_missing_evidence_rejected():
    with pytest.raises(ValueError, match="evidence_refs"):
        _profile(evidence_refs=())


def test_blank_evidence_ref_rejected():
    with pytest.raises(ValueError, match="evidence refs"):
        _profile(evidence_refs=(" ",))


def test_naive_effective_from_rejected():
    with pytest.raises(ValueError, match="timezone-aware UTC"):
        _profile(effective_from="2026-01-01T00:00:00")


def test_non_utc_effective_from_rejected():
    with pytest.raises(ValueError, match="UTC"):
        _profile(effective_from="2026-01-01T00:00:00-05:00")


def test_invalid_effective_to_ordering_rejected():
    with pytest.raises(ValueError, match="effective_to must be after"):
        _profile(
            effective_from=EFFECTIVE_FROM,
            effective_to=EFFECTIVE_FROM,
        )


def test_valid_effective_to_supported():
    profile = _profile(effective_to=EFFECTIVE_TO)

    assert profile.effective_to == EFFECTIVE_TO


def test_object_immutable():
    profile = _profile()

    with pytest.raises(FrozenInstanceError):
        profile.bill_to_name = "Other"


def test_out_of_scope_tax_ready():
    profile = _profile(
        tax_treatment_status=TaxTreatmentStatus.OUT_OF_SCOPE
    )

    assert profile.tax_ready is True


def test_exempt_tax_ready():
    profile = _profile(tax_treatment_status=TaxTreatmentStatus.EXEMPT)

    assert profile.tax_ready is True


def test_undetermined_tax_not_ready():
    profile = _profile(
        tax_treatment_status=TaxTreatmentStatus.UNDETERMINED
    )

    assert profile.tax_ready is False


def test_requires_determination_tax_not_ready():
    profile = _profile(
        tax_treatment_status=TaxTreatmentStatus.REQUIRES_DETERMINATION
    )

    assert profile.tax_ready is False


def test_not_required_payment_terms_ready():
    profile = _profile(
        payment_terms_status=PaymentTermsStatus.NOT_REQUIRED
    )

    assert profile.payment_terms_ready is True


def test_defined_externally_payment_terms_ready():
    profile = _profile(
        payment_terms_status=PaymentTermsStatus.DEFINED_EXTERNALLY
    )

    assert profile.payment_terms_ready is True


def test_undetermined_payment_terms_not_ready():
    profile = _profile(
        payment_terms_status=PaymentTermsStatus.UNDETERMINED
    )

    assert profile.payment_terms_ready is False


def test_requires_definition_payment_terms_not_ready():
    profile = _profile(
        payment_terms_status=PaymentTermsStatus.REQUIRES_DEFINITION
    )

    assert profile.payment_terms_ready is False


def test_complete_identity_invoice_identity_ready():
    profile = _profile()

    assert profile.invoice_identity_ready is True


def test_invoice_candidate_ready_when_all_gates_pass():
    profile = _profile(
        tax_treatment_status=TaxTreatmentStatus.OUT_OF_SCOPE,
        payment_terms_status=PaymentTermsStatus.DEFINED_EXTERNALLY,
    )

    assert profile.invoice_identity_ready is True
    assert profile.tax_ready is True
    assert profile.payment_terms_ready is True
    assert profile.invoice_candidate_ready is True
    assert profile.invoice_creation_allowed is False
    assert profile.receivable_recognition_allowed is False
    assert profile.ledger_posting_allowed is False
    assert profile.tax_calculation_allowed is False
    assert profile.payment_initiation_allowed is False
    assert profile.money_movement_allowed is False


def test_invoice_candidate_ready_false_when_tax_unresolved():
    profile = _profile(
        tax_treatment_status=TaxTreatmentStatus.UNDETERMINED,
        payment_terms_status=PaymentTermsStatus.DEFINED_EXTERNALLY,
    )

    assert profile.invoice_candidate_ready is False


def test_invoice_candidate_ready_false_when_payment_terms_unresolved():
    profile = _profile(
        tax_treatment_status=TaxTreatmentStatus.EXEMPT,
        payment_terms_status=PaymentTermsStatus.REQUIRES_DEFINITION,
    )

    assert profile.invoice_candidate_ready is False


def test_no_invoice_creation_authority():
    assert _profile().invoice_creation_allowed is False


def test_no_receivable_recognition_authority():
    assert _profile().receivable_recognition_allowed is False


def test_no_ledger_posting_authority():
    assert _profile().ledger_posting_allowed is False


def test_no_revenue_recognition_authority():
    assert _profile().revenue_recognition_allowed is False


def test_no_tax_calculation_authority():
    assert _profile().tax_calculation_allowed is False


def test_no_due_balance_creation_authority():
    assert _profile().due_balance_creation_allowed is False


def test_no_fee_collection_authority():
    assert _profile().real_fee_collection_allowed is False


def test_no_client_funds_deduction_authority():
    assert _profile().client_funds_deduction_allowed is False


def test_no_automatic_debit_authority():
    assert _profile().automatic_debit_allowed is False


def test_no_invoice_settlement_authority():
    assert _profile().invoice_settlement_allowed is False


def test_no_payment_initiation_authority():
    assert _profile().payment_initiation_allowed is False


def test_no_money_movement_authority():
    assert _profile().money_movement_allowed is False


def test_no_broker_withdrawal_authority():
    assert _profile().broker_withdrawal_allowed is False


def test_no_execution_authority():
    assert _profile().execution_authority is False
