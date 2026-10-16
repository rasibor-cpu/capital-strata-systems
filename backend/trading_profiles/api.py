"""HTTP API for trading profiles, onboarding and risk acceptance (mounted on the mobile app).

Every endpoint needs an authenticated user. Identity (user and session) always comes from
the server-side session, never from the request body, so a user can only see or change
their own records. No endpoint can place an order or enable live trading.

Risk-enabling actions (activating or changing settings, resuming, reauthorizing) require
a valid acceptance of the current CSS User Operating Manual. Risk-reducing actions
(pause, mandate revocation) never do.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from fastapi import APIRouter, Body, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from backend.trading_profiles.consent import ConsentError
from backend.trading_profiles.copy_engine import ProposalError
from backend.trading_profiles.limits import LimitsError
from backend.trading_profiles.mandates import MandateError
from backend.trading_profiles.manual import ManualIntegrityError, render_html
from backend.trading_profiles.onboarding_page import onboarding_html
from backend.trading_profiles.preferences import PreferencesError
from backend.trading_profiles.service import TradingProfileService

UserResolver = Callable[[Request], Mapping[str, Any] | None]
PREFIX = "/api/v1/trading-profiles"
ONBOARDING_PATH = "/trading-profiles/onboarding"


def _error(status: int, reason: str) -> JSONResponse:
    return JSONResponse({"ok": False, "reason": reason}, status_code=status)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_trading_profiles_router(
    *,
    user_resolver: UserResolver,
    service_factory: Callable[[], TradingProfileService],
) -> APIRouter:
    router = APIRouter(tags=["trading-profiles"])

    def _identity(request: Request) -> tuple[str, str] | None:
        try:
            ident = user_resolver(request) or {}
        except Exception:
            return None
        user_id, session_id = str(ident.get("user_id") or ""), str(ident.get("session_id") or "")
        return (user_id, session_id) if user_id and session_id else None

    def _guard(request: Request, action: Callable[[TradingProfileService, str, str], Any]) -> Any:
        ident = _identity(request)
        if ident is None:
            return _error(401, "authentication_required")
        try:
            result = action(service_factory(), *ident)
        except ManualIntegrityError as exc:
            return _error(503, f"manual_integrity_failed:{exc}")
        except (ConsentError, PreferencesError, MandateError, ProposalError, LimitsError, ValueError, KeyError) as exc:
            reason = str(exc).strip("'")
            if "signing_key" in reason or "manual_integrity" in reason:
                return _error(503, reason)
            if reason.endswith("not_found") or reason == "page_not_found":
                return _error(404, reason)
            return _error(400, reason)
        if isinstance(result, Response):
            return result
        return {"ok": True, **(result if isinstance(result, dict) else {"result": result})}

    # -- reference -------------------------------------------------------------
    @router.get(PREFIX + "/catalog")
    def catalog(request: Request) -> Any:
        return _guard(request, lambda svc, uid, sid: svc.catalog())

    @router.get(PREFIX + "/me")
    def me(request: Request) -> Any:
        return _guard(request, lambda svc, uid, sid: svc.startup_state(uid, session_id=sid))

    @router.get(PREFIX + "/manual")
    def manual(request: Request) -> Any:
        return _guard(request, lambda svc, uid, sid: svc.manual_provider().describe())

    @router.get(PREFIX + "/manual/pages/{page_id}")
    def manual_page(request: Request, page_id: str) -> Any:
        """Revisit any page at any time (reference only; does not count toward a review)."""
        def action(svc, uid, sid):
            page = svc.manual_provider().page(page_id)
            return {"page_id": page.page_id, "title": page.title, "markdown": page.markdown,
                    "html": render_html(page.markdown), "sha256": page.sha256}
        return _guard(request, action)

    @router.get(PREFIX + "/manual/download")
    def manual_download(request: Request, format: str = "md") -> Any:
        def action(svc, uid, sid):
            m = svc.manual_provider()
            media = "text/markdown" if format == "md" else "text/plain"
            ext = "md" if format == "md" else "txt"
            return Response(m.text, media_type=f"{media}; charset=utf-8", headers={
                "Content-Disposition": f'attachment; filename="CSS_User_Operating_Manual_v{m.version}.{ext}"',
                "X-CSS-Document-Version": m.version, "X-CSS-Document-SHA256": m.sha256})
        return _guard(request, action)

    # -- onboarding / consent ----------------------------------------------------
    @router.post(PREFIX + "/changes")
    def propose(request: Request, payload: dict = Body(...)) -> Any:
        return _guard(request, lambda svc, uid, sid: svc.propose(uid, payload))

    @router.get(PREFIX + "/changes/{change_id}")
    def get_change(request: Request, change_id: str) -> Any:
        return _guard(request, lambda svc, uid, sid: {"change": svc.consent.pending_change(uid, change_id)})

    @router.post(PREFIX + "/consent/reviews")
    def open_review(request: Request, payload: dict = Body(...)) -> Any:
        def action(svc, uid, sid):
            review = svc.consent.open_review(uid, auth_session_hash=sid, change_id=str(payload.get("change_id") or ""),
                                             now=_now())
            m = svc.manual_provider()
            return {"review_id": review.review_id, "manual_version": review.manual_version,
                    "manual_sha256": review.manual_sha256, "expires_at_utc": review.expires_at_utc,
                    "pages": [{"page_id": p.page_id, "title": p.title} for p in m.pages]}
        return _guard(request, action)

    @router.get(PREFIX + "/consent/reviews/{review_id}/pages/{page_id}")
    def present_page(request: Request, review_id: str, page_id: str) -> Any:
        def action(svc, uid, sid):
            page = svc.consent.present_page(uid, auth_session_hash=sid, review_id=review_id, page_id=page_id, now=_now())
            return {**page, "html": render_html(page["markdown"])}
        return _guard(request, action)

    @router.post(PREFIX + "/consent/reviews/{review_id}/pages/{page_id}/reviewed")
    def mark_reviewed(request: Request, review_id: str, page_id: str, payload: dict = Body(...)) -> Any:
        return _guard(request, lambda svc, uid, sid: svc.consent.mark_reviewed(
            uid, auth_session_hash=sid, review_id=review_id, page_id=page_id,
            method=str(payload.get("method") or ""), page_sha256=str(payload.get("page_sha256") or ""), now=_now()))

    @router.post(PREFIX + "/consent/reviews/{review_id}/accept")
    def accept(request: Request, review_id: str, payload: dict = Body(...)) -> Any:
        return _guard(request, lambda svc, uid, sid: {"receipt": svc.consent.accept(
            uid, auth_session_hash=sid, review_id=review_id,
            acknowledgement_checked=payload.get("acknowledgement_checked"),
            acknowledgement_sha256=str(payload.get("acknowledgement_sha256") or ""),
            manual_version=str(payload.get("manual_version") or ""),
            manual_sha256=str(payload.get("manual_sha256") or ""),
            policy_hash_shown=str(payload.get("policy_hash") or ""), now=_now())})

    @router.get(PREFIX + "/consent/receipts")
    def receipts(request: Request) -> Any:
        return _guard(request, lambda svc, uid, sid: {"receipts": svc.consent.receipts(uid),
                                                       "document_history": list(svc.manual_provider().history)})

    @router.get(PREFIX + "/consent/receipts/{receipt_id}/download")
    def receipt_download(request: Request, receipt_id: str) -> Any:
        def action(svc, uid, sid):
            receipt = next((r for r in svc.consent.receipts(uid) if r["receipt_id"] == receipt_id), None)
            if receipt is None:
                raise ConsentError("receipt_not_found")
            return Response(json.dumps(receipt, indent=2), media_type="application/json", headers={
                "Content-Disposition": f'attachment; filename="CSS_acceptance_receipt_{receipt_id}.json"'})
        return _guard(request, action)

    # -- emergency risk reduction (never gated by consent) -------------------------
    @router.post(PREFIX + "/emergency/pause")
    def pause(request: Request) -> Any:
        return _guard(request, lambda svc, uid, sid: svc.pause(uid))

    @router.post(PREFIX + "/mandates/{mandate_id}/revoke")
    def revoke(request: Request, mandate_id: str, payload: dict = Body(default={})) -> Any:
        return _guard(request, lambda svc, uid, sid: svc.revoke_mandate(
            uid, mandate_id, str(payload.get("reason") or "user_revoked")))

    # -- risk-enabling (consent required) ------------------------------------------
    @router.post(PREFIX + "/resume")
    def resume(request: Request) -> Any:
        return _guard(request, lambda svc, uid, sid: svc.resume(uid))

    @router.post(PREFIX + "/mandates/{mandate_id}/reauthorize")
    def reauthorize(request: Request, mandate_id: str) -> Any:
        return _guard(request, lambda svc, uid, sid: svc.reauthorize_mandate(uid, mandate_id, sid))

    @router.get(PREFIX + "/statement")
    def statement(request: Request) -> Any:
        return _guard(request, lambda svc, uid, sid: svc.statement(uid))

    # -- onboarding UI -------------------------------------------------------------
    @router.get(ONBOARDING_PATH, response_class=HTMLResponse)
    def onboarding(request: Request) -> Any:
        if _identity(request) is None:
            return HTMLResponse("<!doctype html><title>Sign in required</title><p>Please sign in to continue.</p>",
                                status_code=401)
        return HTMLResponse(onboarding_html(api_prefix=PREFIX))

    return router
