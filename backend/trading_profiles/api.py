"""HTTP API for trading profiles, onboarding and risk acceptance (mounted on the mobile app).

Every endpoint needs an authenticated user. Identity (user and session) always comes from
the server-side session, never from the request body, so a user can only see or change
their own records. No endpoint can place an order or enable live trading.

Risk-enabling actions (activating or changing settings, resuming, reauthorizing) require
a valid acceptance of the current CSS User Operating Manual. Risk-reducing actions
(pause, mandate revocation) never do.

When a `router_factory` is supplied, paper-routing endpoints are added: the user's paper
book, CSS-Assisted proposals and decisions, manual paper orders (all through
TradingRouter -> CopyTradeEngine, which revalidates acceptance at every decision), the
SUPER_USER trader-registry administration (dual control enforced by the registry), and
the trader signal feed, which is authenticated by the trader's Ed25519 signature rather
than a user session.
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
from backend.trading_profiles.trader_registry import TraderRegistryError

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
    router_factory: Callable[[], Any] | None = None,
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

    # -- paper routing (optional) ------------------------------------------------------
    if router_factory is not None:
        _add_routing_endpoints(router, user_resolver, router_factory)

    # -- onboarding UI -------------------------------------------------------------
    @router.get(ONBOARDING_PATH, response_class=HTMLResponse)
    def onboarding(request: Request) -> Any:
        if _identity(request) is None:
            return HTMLResponse("<!doctype html><title>Sign in required</title><p>Please sign in to continue.</p>",
                                status_code=401)
        return HTMLResponse(onboarding_html(api_prefix=PREFIX))

    return router


def _add_routing_endpoints(router: APIRouter, user_resolver: UserResolver, router_factory: Callable[[], Any]) -> None:
    from backend.trading_profiles.router import PaperBookError
    from backend.trading_profiles.signal_feed import SignalFeedError

    def _ctx(request: Request) -> dict[str, Any] | None:
        try:
            ident = dict(user_resolver(request) or {})
        except Exception:
            return None
        if not ident.get("user_id") or not ident.get("session_id"):
            return None
        return ident

    def _run(request: Request, action: Callable[[Any, dict[str, Any]], Any], *, admin: bool = False) -> Any:
        ctx = _ctx(request)
        if ctx is None:
            return _error(401, "authentication_required")
        if admin and str(ctx.get("role") or "").upper() != "SUPER_USER":
            return _error(403, "super_user_required")
        try:
            result = action(router_factory(), ctx)
        except (ProposalError, TraderRegistryError, PaperBookError, ConsentError, ValueError, KeyError, TypeError) as exc:
            reason = str(exc).strip("'")
            if reason.endswith("not_found"):
                return _error(404, reason)
            if reason == "super_user_required":
                return _error(403, reason)
            return _error(400, reason)
        return {"ok": True, **result}

    def _session(ctx: dict[str, Any]) -> tuple[str, float]:
        return str(ctx["session_id"]), float(ctx.get("session_created") or 0.0)

    def _decision(d: Any) -> dict[str, Any]:
        return {"decision": {k: getattr(d, k) for k in ("signal_id", "outcome", "stage", "reason", "operating_mode",
                                                       "personality", "notional", "proposal_id", "position_id",
                                                       "pipeline_status")}}

    @router.get(PREFIX + "/paper/book")
    def paper_book(request: Request) -> Any:
        def action(r, ctx):
            uid = ctx["user_id"]
            return {"account": r.book.account(uid, _now()),
                    "positions": [{**p.__dict__, "opened_at": p.opened_at.isoformat()} for p in r.book.positions(uid)],
                    "live_trading": False}
        return _run(request, action)

    @router.get(PREFIX + "/paper/fees")
    def paper_fees(request: Request) -> Any:
        """The caller's own commercial accrual statement (accounting only; no money moves)."""
        def action(r, ctx):
            ledger = getattr(r, "fee_ledger", None)
            if ledger is None:
                return {"statement": None, "reason": "fee_ledger_not_configured", "money_moved": False}
            from backend.commercial.fee_ledger import FeeLedgerError
            try:
                return {"statement": ledger.statement(ctx["user_id"]), "money_moved": False}
            except FeeLedgerError as exc:
                return {"statement": None, "reason": str(exc), "money_moved": False}
        return _run(request, action)

    @router.get(PREFIX + "/market-data/status")
    def market_data_status(request: Request) -> Any:
        """Static market-data readiness (credentials / jurisdiction / blocked feeds). No network, no secrets."""
        def action(_r, _ctx):
            from backend.signals.market_data import provider_matrix
            return {"providers": provider_matrix(), "live_probe": "tools/css_market_data_matrix.py --probe",
                    "live_trading": False}
        return _run(request, action)

    @router.get(PREFIX + "/proposals")
    def proposals(request: Request) -> Any:
        return _run(request, lambda r, ctx: {"proposals": r.engine.pending_proposals(ctx["user_id"])})

    @router.post(PREFIX + "/proposals/{proposal_id}/decision")
    def decide(request: Request, proposal_id: str, payload: dict = Body(...)) -> Any:
        approve = payload.get("approve")
        if type(approve) is not bool:
            return _error(400, "approve_must_be_boolean")
        return _run(request, lambda r, ctx: _decision(r.decide_proposal(
            ctx["user_id"], _session(ctx), proposal_id, approve=approve, now=_now())))

    @router.post(PREFIX + "/orders")
    def manual_order(request: Request, payload: dict = Body(...)) -> Any:
        return _run(request, lambda r, ctx: _decision(r.submit_manual_order(
            ctx["user_id"], _session(ctx), payload, now=_now())))

    # -- trader registry administration (SUPER_USER; dual control in the registry) ----
    @router.get(PREFIX + "/admin/traders")
    def traders(request: Request) -> Any:
        return _run(request, lambda r, ctx: {"traders": [t.summary() for t in r.engine.trader_registry.list()]},
                    admin=True)

    @router.post(PREFIX + "/admin/traders")
    def propose_trader(request: Request, payload: dict = Body(...)) -> Any:
        return _run(request, lambda r, ctx: {"trader": r.engine.trader_registry.propose(
            trader_id=str(payload.get("trader_id") or ""), display_name=str(payload.get("display_name") or ""),
            public_key_b64=str(payload.get("public_key_b64") or ""),
            asset_classes=list(payload.get("asset_classes") or []), actor_ctx=ctx).summary()}, admin=True)

    @router.post(PREFIX + "/admin/traders/{trader_id}/{action_name}")
    def govern_trader(request: Request, trader_id: str, action_name: str, payload: dict = Body(default={})) -> Any:
        if action_name not in {"approve", "suspend", "revoke", "reinstate"}:
            return _error(404, "action_not_found")

        def action(r, ctx):
            reg = r.engine.trader_registry
            if action_name == "approve":
                trader = reg.approve(trader_id, actor_ctx=ctx)
            else:
                trader = getattr(reg, action_name)(trader_id, actor_ctx=ctx, reason=str(payload.get("reason") or ""))
            return {"trader": trader.summary()}
        return _run(request, action, admin=True)

    # -- trader signal feed: authenticated by the trader's signature, not a session ------
    @router.post(PREFIX + "/feed/signals")
    def ingest_signal(payload: dict = Body(...)) -> Any:
        try:
            result = router_factory().on_trader_signal(payload, now=_now())
        except SignalFeedError as exc:
            return _error(400, str(exc))
        if not result.accepted:
            status = 403 if result.reason.startswith(("signature", "trader_not_authorized")) else 400
            return _error(status, result.reason)
        return {"ok": True, "signal_id": result.signal_id, "followers_evaluated": len(result.decisions),
                "copied": sum(1 for d in result.decisions if d.copied)}
