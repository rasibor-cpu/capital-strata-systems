from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.persistence.services.trial_contract_enrollment_service import (
    TrialContractEnrollmentService,
)
from backend.app.persistence.services.trial_conversion_assessment_service import (
    TrialConversionAssessmentService,
)
from backend.commercialization.trial_contract import TrialContractError


class TrialEnrollmentRequest(BaseModel):
    customer_id: str = Field(min_length=1)
    account_reference: str = Field(min_length=1)
    agreement_id: str = Field(min_length=1)
    agreement_version: str = Field(min_length=1)
    accepted_at: str = Field(min_length=1)
    displayed_pricing_summary: str = Field(min_length=1)
    displayed_conversion_disclosure: str = Field(min_length=1)
    acceptance_audit_reference: str = Field(min_length=1)
    evidence_refs: list[str] = Field(min_length=1)


class TrialCancellationRequest(BaseModel):
    customer_id: str = Field(min_length=1)
    account_reference: str = Field(min_length=1)
    canceled_at: str = Field(min_length=1)
    cancellation_audit_reference: str = Field(min_length=1)
    evidence_refs: list[str] = Field(min_length=1)


def create_trial_contract_router() -> APIRouter:
    router = APIRouter()

    @router.get("/api/v1/commercial-trial/agreement")
    def read_trial_agreement(
        agreement_id: str = Query(...),
        agreement_version: str = Query(...),
    ) -> dict[str, Any]:
        try:
            agreement = TrialContractEnrollmentService().load_agreement(
                agreement_id,
                agreement_version,
            )
        except TrialContractError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {
            "agreement_id": agreement.agreement_id,
            "agreement_version": agreement.agreement_version,
            "jurisdiction_code": agreement.jurisdiction_code,
            "pricing_plan_id": agreement.pricing_plan_id,
            "pricing_summary": agreement.pricing_summary,
            "trial_duration_days": agreement.trial_duration_days,
            "automatic_conversion_disclosure": (
                agreement.automatic_conversion_disclosure
            ),
            "effective_from": agreement.effective_from,
            "evidence_refs": list(agreement.evidence_refs),
            "payment_execution_allowed": False,
            "money_movement_allowed": False,
            "execution_authority": False,
        }

    @router.post("/api/v1/commercial-trial/enroll")
    def enroll_trial(request: TrialEnrollmentRequest) -> dict[str, Any]:
        try:
            enrollment = TrialContractEnrollmentService().enroll(
                customer_id=request.customer_id,
                account_reference=request.account_reference,
                agreement_id=request.agreement_id,
                agreement_version=request.agreement_version,
                accepted_at=request.accepted_at,
                displayed_pricing_summary=request.displayed_pricing_summary,
                displayed_conversion_disclosure=(
                    request.displayed_conversion_disclosure
                ),
                acceptance_audit_reference=request.acceptance_audit_reference,
                evidence_refs=tuple(request.evidence_refs),
            )
        except (TrialContractError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        return {
            "customer_id": enrollment.customer_id,
            "account_reference": enrollment.account_reference,
            "agreement_id": enrollment.agreement_id,
            "agreement_version": enrollment.agreement_version,
            "pricing_plan_id": enrollment.pricing_plan_id,
            "accepted_at": enrollment.accepted_at,
            "trial_start_at": enrollment.trial_start_at,
            "trial_expires_at": enrollment.trial_expires_at,
            "acceptance_audit_reference": enrollment.acceptance_audit_reference,
            "automatic_payment_started": False,
            "payment_execution_allowed": False,
            "money_movement_allowed": False,
            "execution_authority": False,
        }

    @router.post("/api/v1/commercial-trial/cancel")
    def cancel_trial(request: TrialCancellationRequest) -> dict[str, Any]:
        try:
            cancellation = TrialContractEnrollmentService().cancel(
                customer_id=request.customer_id,
                account_reference=request.account_reference,
                canceled_at=request.canceled_at,
                cancellation_audit_reference=request.cancellation_audit_reference,
                evidence_refs=tuple(request.evidence_refs),
            )
        except (TrialContractError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        return {
            "customer_id": cancellation.customer_id,
            "account_reference": cancellation.account_reference,
            "canceled_at": cancellation.canceled_at,
            "cancellation_audit_reference": (
                cancellation.cancellation_audit_reference
            ),
            "automatic_conversion_blocked_if_pre_expiry": True,
            "payment_execution_allowed": False,
            "money_movement_allowed": False,
            "execution_authority": False,
        }

    @router.get("/api/v1/commercial-trial/status")
    def read_trial_status(
        customer_id: str = Query(...),
        account_reference: str = Query(...),
        agreement_id: str = Query(...),
        agreement_version: str = Query(...),
        assessed_at: str = Query(...),
    ) -> dict[str, Any]:
        try:
            assessment = TrialConversionAssessmentService().assess(
                customer_id=customer_id,
                account_reference=account_reference,
                agreement_id=agreement_id,
                agreement_version=agreement_version,
                assessed_at=assessed_at,
            )
        except TrialContractError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        return {
            "status": assessment.status.value,
            "assessed_at": assessment.assessed_at,
            "agreement_id": assessment.agreement_id,
            "agreement_version": assessment.agreement_version,
            "pricing_plan_id": assessment.pricing_plan_id,
            "reason": assessment.reason,
            "automatic_conversion_allowed": (
                assessment.automatic_conversion_allowed
            ),
            "payment_execution_allowed": False,
            "money_movement_allowed": False,
            "execution_authority": False,
        }

    return router
