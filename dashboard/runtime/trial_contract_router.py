from __future__ import annotations

from dataclasses import asdict
from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from backend.app.persistence.services.trial_contract_enrollment_service import (
    TrialContractEnrollmentService,
)
from backend.app.persistence.services.trial_conversion_assessment_service import (
    TrialConversionAssessmentService,
)
from backend.commercialization.trial_contract import TrialContractError
from backend.app.auth.session_dependency import authorization_for_commercial_route
from dashboard.runtime.commercial_governance_router import token_store_session_resolver
from engine.commercial.commercial_authorization import (
    BearerSessionResolver,
    CommercialAuthorizer,
    actor_from_bearer,
)
from engine.commercial.commercial_controls import (
    CommercialControls,
    ControlledActionConflict,
    ControlledActionError,
)


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
    affirm_terms_acceptance: Literal[True]
    affirm_automatic_conversion_disclosure: Literal[True]
    idempotency_key: str = Field(min_length=1, max_length=200)


class TrialCancellationRequest(BaseModel):
    customer_id: str = Field(min_length=1)
    account_reference: str = Field(min_length=1)
    canceled_at: str = Field(min_length=1)
    cancellation_audit_reference: str = Field(min_length=1)
    evidence_refs: list[str] = Field(min_length=1)
    idempotency_key: str = Field(min_length=1, max_length=200)


def create_trial_contract_router(
    *,
    session_resolver: BearerSessionResolver = token_store_session_resolver,
    authorizer: Optional[CommercialAuthorizer] = None,
    controls: Optional[CommercialControls] = None,
) -> APIRouter:
    router = APIRouter()
    authorizer_ = authorizer or CommercialAuthorizer()

    def actor_for(authorization: Optional[str], permission: str):
        return actor_from_bearer(
            authorization, permission,
            session_resolver=session_resolver, authorizer=authorizer_,
        )

    @router.get("/api/v1/commercial-trial/agreement")
    def read_trial_agreement(
        http_request: Request,
        agreement_id: str = Query(...),
        agreement_version: str = Query(...),
    ) -> dict[str, Any]:
        actor_for(authorization_for_commercial_route(http_request, mutating=False), "commercial_view_obligations")
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

    @router.post("/api/v1/commercial-trial/enroll", status_code=201)
    def enroll_trial(
        http_request: Request,
        request: TrialEnrollmentRequest,
    ) -> dict[str, Any]:
        maker = actor_for(authorization_for_commercial_route(http_request, mutating=True), "commercial_trial_enroll")
        if controls is None:
            raise HTTPException(status_code=503, detail="commercial governance not configured")
        object_ref = f"trial_enrollment:{request.customer_id}:{request.account_reference}"
        try:
            action = controls.request(
                maker,
                action_type="ENROLL_TRIAL",
                object_ref=object_ref,
                payload=request.model_dump(exclude={"idempotency_key"}),
                idempotency_key=request.idempotency_key,
            )
        except ControlledActionConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ControlledActionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return {
            "controlled_action": asdict(action),
            "automatic_payment_started": False,
            "payment_execution_allowed": False,
            "money_movement_allowed": False,
            "execution_authority": False,
        }

    @router.post("/api/v1/commercial-trial/cancel", status_code=201)
    def cancel_trial(
        http_request: Request,
        request: TrialCancellationRequest,
    ) -> dict[str, Any]:
        maker = actor_for(authorization_for_commercial_route(http_request, mutating=True), "commercial_trial_cancel")
        if controls is None:
            raise HTTPException(status_code=503, detail="commercial governance not configured")
        object_ref = f"trial_cancellation:{request.customer_id}:{request.account_reference}"
        try:
            action = controls.request(
                maker,
                action_type="CANCEL_TRIAL",
                object_ref=object_ref,
                payload=request.model_dump(exclude={"idempotency_key"}),
                idempotency_key=request.idempotency_key,
            )
        except ControlledActionConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ControlledActionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return {
            "controlled_action": asdict(action),
            "automatic_conversion_blocked_if_pre_expiry": True,
            "payment_execution_allowed": False,
            "money_movement_allowed": False,
            "execution_authority": False,
        }

    @router.get("/api/v1/commercial-trial/status")
    def read_trial_status(
        http_request: Request,
        customer_id: str = Query(...),
        account_reference: str = Query(...),
        agreement_id: str = Query(...),
        agreement_version: str = Query(...),
        assessed_at: str = Query(...),
    ) -> dict[str, Any]:
        actor_for(authorization_for_commercial_route(http_request, mutating=False), "commercial_view_obligations")
        service = TrialConversionAssessmentService()
        try:
            assessment = service.assess(
                customer_id=customer_id,
                account_reference=account_reference,
                agreement_id=agreement_id,
                agreement_version=agreement_version,
                assessed_at=assessed_at,
            )
        except TrialContractError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            # e.g. a malformed assessed_at: a client input error, never a 500.
            raise HTTPException(status_code=422, detail=f"invalid status request: {exc}") from exc
        enrollment = service.enrollment_details(
            customer_id=customer_id,
            account_reference=account_reference,
            agreement_id=agreement_id,
            agreement_version=agreement_version,
        ) or {}

        return {
            # Read-only: assessing status never executes, enrolls, cancels or charges anything.
            "customer_id": customer_id,
            "account_reference": account_reference,
            "trial_start_at": enrollment.get("trial_start_at"),
            "trial_expires_at": enrollment.get("trial_expires_at"),
            "cancellation_recorded": bool(enrollment.get("cancellation_recorded")),
            "canceled_at": enrollment.get("canceled_at"),
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
