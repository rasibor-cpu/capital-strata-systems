from __future__ import annotations

import html
import json
import os
import secrets
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse

from dashboard.auth.css_sign_on import (
    AuthFailure,
    PasswordChangeRequired,
    PasswordValidationError,
    PROJECT_ROOT,
    authenticate_credentials,
    available_roles,
    can_manage_users,
    change_password,
    create_user,
    list_user_summaries,
    load_users,
    save_users,
)
from backend.security.permissions import PermissionEngine
from dashboard.runtime.broker_credential_check import _load_coinbase_credentials, load_local_env
from dashboard.runtime.broker_balance_reconciliation import (
    build_broker_reconciliation_payload,
)
from dashboard.runtime.audit_trail_viewer import (
    AUDIT_CATEGORY_OPTIONS,
    export_audit_events,
    filter_audit_events,
    load_mobile_trade_audit_events,
    summarize_audit_events,
)
from dashboard.runtime.trade_replay_harness import replay_mobile_trade_event_file
from dashboard.runtime.dashboard_hydration_coordinator import DashboardHydrationCoordinator
from dashboard.runtime.runtime_bootstrap import DashboardRuntimeBootstrap
from engine.execution.live_order_kill_switch import evaluate_live_order_kill_switch
from backend.app.persistence.services.session_runtime_service import SessionRuntimeService
from backend.app.persistence.services.pnl_runtime_service import PnlRuntimeService
from backend.app.persistence.services.trade_runtime_service import TradeRuntimeService


SESSION_COOKIE = "css_mobile_session"
PASSWORD_CHANGE_COOKIE = "css_mobile_pw_change"
SESSION_MAX_SECONDS = int(os.getenv("CSS_MOBILE_SESSION_SECONDS", "28800") or 28800)
PASSWORD_CHANGE_SECONDS = int(os.getenv("CSS_MOBILE_PASSWORD_CHANGE_SECONDS", "600") or 600)
MOBILE_EVENTS_FILE = PROJECT_ROOT / "artifacts" / "css_mobile_trade_events.jsonl"
MOBILE_CONTROL_FILE = PROJECT_ROOT / "artifacts" / "css_mobile_controls.json"
DEFAULT_COINBASE_MAX_LIVE_ORDER_USD = 1.00
ENGINE_MODES = ("SAFE", "CONSERVATIVE", "BALANCED", "AGGRESSIVE")
DEFAULT_MOBILE_CONTROLS = {
    "mobile_trading_mode": "MOBILE_READ_ONLY",
    "engine_mode": "SAFE",
    "live_order_kill_switch": False,
}

app = FastAPI(title="Capital Strata Systems Mobile", version="0.1.0")

_SESSIONS: Dict[str, Dict[str, Any]] = {}
_PASSWORD_CHANGES: Dict[str, Dict[str, Any]] = {}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if _get_session(request):
        return RedirectResponse("/dashboard", status_code=303)
    return RedirectResponse("/login", status_code=303)


@app.get("/login", response_class=HTMLResponse)
async def login_screen(request: Request):
    if _get_session(request):
        return RedirectResponse("/dashboard", status_code=303)
    return HTMLResponse(_login_page())


@app.post("/login", response_class=HTMLResponse)
async def login_submit(request: Request):
    form = await _read_form(request)
    user_id = form.get("user_id", "")
    password = form.get("password", "")
    users = load_users()

    try:
        user_ctx = authenticate_credentials(users, user_id, password)
        save_users(users)
    except PasswordChangeRequired as required:
        save_users(users)
        token = _create_password_change_token(required.user_id)
        response = HTMLResponse(_password_change_page())
        response.set_cookie(
            PASSWORD_CHANGE_COOKIE,
            token,
            httponly=True,
            samesite="lax",
            max_age=PASSWORD_CHANGE_SECONDS,
        )
        return response
    except AuthFailure as exc:
        save_users(users)
        return HTMLResponse(_login_page(message=exc.message, status="error"), status_code=401)

    return _login_success_response(user_ctx)


@app.get("/password-change", response_class=HTMLResponse)
async def password_change_screen(request: Request):
    token_record = _get_password_change_record(request)
    if not token_record:
        return RedirectResponse("/login", status_code=303)
    return HTMLResponse(_password_change_page())


@app.post("/password-change", response_class=HTMLResponse)
async def password_change_submit(request: Request):
    token_record = _get_password_change_record(request)
    if not token_record:
        return HTMLResponse(
            _login_page(message="Password-change session expired. Sign on again.", status="error"),
            status_code=401,
        )

    form = await _read_form(request)
    users = load_users()

    try:
        user_ctx = change_password(
            users,
            str(token_record.get("user_id", "")),
            str(form.get("new_password", "")),
            str(form.get("confirm_password", "")),
        )
        save_users(users)
    except PasswordValidationError as exc:
        return HTMLResponse(_password_change_page(message=str(exc), status="error"), status_code=400)

    token = request.cookies.get(PASSWORD_CHANGE_COOKIE)
    if token:
        _PASSWORD_CHANGES.pop(token, None)

    response = _login_success_response(user_ctx)
    response.delete_cookie(PASSWORD_CHANGE_COOKIE)
    return response


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    session = _get_session(request)
    if not session:
        return RedirectResponse("/login", status_code=303)

    user_ctx = session["user_ctx"]
    return HTMLResponse(_dashboard_page(user_ctx=user_ctx, session=session))


@app.get("/positions", response_class=HTMLResponse)
async def positions_screen(request: Request):
    session = _get_session(request)
    if not session:
        return RedirectResponse("/login", status_code=303)

    return HTMLResponse(_positions_page(session["user_ctx"], session))


@app.get("/history", response_class=HTMLResponse)
async def history_screen(request: Request):
    session = _get_session(request)
    if not session:
        return RedirectResponse("/login", status_code=303)

    return HTMLResponse(_history_page(session["user_ctx"], session))


@app.get("/risk", response_class=HTMLResponse)
async def risk_screen(request: Request):
    session = _get_session(request)
    if not session:
        return RedirectResponse("/login", status_code=303)

    return HTMLResponse(_risk_page(session["user_ctx"], session))


@app.get("/governance", response_class=HTMLResponse)
async def governance_screen(request: Request):
    session = _get_session(request)
    if not session:
        return RedirectResponse("/login", status_code=303)

    return HTMLResponse(_governance_page(session["user_ctx"], session))


@app.get("/opportunities", response_class=HTMLResponse)
async def opportunities_screen(request: Request):
    session = _get_session(request)
    if not session:
        return RedirectResponse("/login", status_code=303)

    return HTMLResponse(_opportunities_page(session["user_ctx"], session))


@app.get("/market", response_class=HTMLResponse)
async def market_screen(request: Request):
    session = _get_session(request)
    if not session:
        return RedirectResponse("/login", status_code=303)

    return HTMLResponse(_market_page(session["user_ctx"], session))


@app.get("/broker", response_class=HTMLResponse)
async def broker_screen(request: Request):
    session = _get_session(request)
    if not session:
        return RedirectResponse("/login", status_code=303)

    return HTMLResponse(_broker_page(session["user_ctx"], session))


@app.get("/margin", response_class=HTMLResponse)
async def margin_screen(request: Request):
    session = _get_session(request)
    if not session:
        return RedirectResponse("/login", status_code=303)

    return HTMLResponse(_margin_page(session["user_ctx"], session))


@app.get("/api/margin-snapshot")
async def margin_api(request: Request):
    session = _get_session(request)
    if not session:
        return JSONResponse({"ok": False, "status": "AUTH_REQUIRED"})
    
    try:
        from dashboard.runtime.broker_credential_check import load_local_env
        load_local_env()
    except Exception:
        pass

    user_ctx = session["user_ctx"]
    try:
        payload = _mobile_dashboard_payload(user_ctx, session)
        def _m(v):
            return v if isinstance(v, dict) else {}
        broker_summary = _m(payload.get("broker_summary"))
        broker = str(broker_summary.get("selected_broker", "NONE")).upper()
        mode = str(broker_summary.get("broker_mode", "SIMULATED")).upper()
    except Exception:
        broker = "NONE"
        mode = "SIMULATED"
    
    snapshot = None
    try:
        if broker == "OANDA":
            from engine.risk.oanda_margin_adapter import OandaMarginAdapter
            snapshot = OandaMarginAdapter(mode=mode).get_margin_snapshot()
        elif broker == "COINBASE":
            from engine.risk.coinbase_margin_adapter import CoinbaseMarginAdapter
            snapshot = CoinbaseMarginAdapter(mode=mode).get_margin_snapshot()
    except Exception:
        pass

    if not snapshot:
        return JSONResponse({"ok": False, "status": "DATA_UNAVAILABLE"})

    margin_state_val = getattr(snapshot, "margin_state", "UNKNOWN")
    if hasattr(margin_state_val, "value"):
        margin_state_val = margin_state_val.value
    else:
        margin_state_val = str(margin_state_val)

    return JSONResponse({
        "ok": True,
        "broker": str(getattr(snapshot, "broker", "UNKNOWN")),
        "account_id": str(getattr(snapshot, "account_id", "UNKNOWN")),
        "equity": float(getattr(snapshot, "equity", 0.0)),
        "cash": float(getattr(snapshot, "cash", 0.0)),
        "buying_power": float(getattr(snapshot, "buying_power", 0.0)),
        "maintenance_margin": float(getattr(snapshot, "maintenance_margin", 0.0)),
        "initial_margin": float(getattr(snapshot, "initial_margin", 0.0)),
        "margin_used": float(getattr(snapshot, "margin_used", 0.0)),
        "margin_available": float(getattr(snapshot, "margin_available", 0.0)),
        "margin_ratio": float(getattr(snapshot, "margin_ratio", 0.0)),
        "margin_state": margin_state_val,
        "timestamp": str(getattr(snapshot, "timestamp", "UNKNOWN")),
    })



@app.get("/audit", response_class=HTMLResponse)
async def audit_screen(request: Request):
    session = _get_session(request)
    if not session:
        return RedirectResponse("/login", status_code=303)

    user_ctx = session["user_ctx"]
    if not _can_view_audit_logs(user_ctx):
        return HTMLResponse(
            _access_denied_page(user_ctx, "Audit trail access requires audit authority."),
            status_code=403,
        )

    return HTMLResponse(_audit_page(user_ctx, **_audit_query_filters(request)))


@app.post("/logout")
async def logout(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        _SESSIONS.pop(token, None)
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/trade-status", response_class=HTMLResponse)
async def trade_status_screen(request: Request):
    session = _get_session(request)
    if not session:
        return RedirectResponse("/login", status_code=303)

    return HTMLResponse(_trade_status_page(session["user_ctx"], session))


@app.get("/api/status")
async def status(request: Request):
    session = _get_session(request)
    system_status = _system_status(session["user_ctx"] if session else None)
    return JSONResponse(
        {
            "ok": True,
            "authenticated": bool(session),
            "mode": "mobile-full-access",
            "system_mode": system_status["runtime_mode"],
            "orders_enabled": system_status["orders_enabled"],
            "engine_mode": system_status["engine_mode"],
            "broker_live_gate": system_status["broker_live_gate"],
            "live_order_kill_switch": system_status["live_order_kill_switch"],
            "live_orders_enabled": system_status["live_orders_enabled"],
        }
    )


@app.get("/api/audit/export")
async def audit_export(request: Request):
    session = _get_session(request)
    if not session:
        return JSONResponse({"ok": False, "error": "AUTH_REQUIRED"}, status_code=401)

    user_ctx = session["user_ctx"]
    if not _can_view_audit_logs(user_ctx):
        return JSONResponse({"ok": False, "error": "AUDIT_AUTH_REQUIRED"}, status_code=403)

    filters = _audit_query_filters(request)
    events = load_mobile_trade_audit_events(MOBILE_EVENTS_FILE, limit=250)
    filtered = filter_audit_events(events, **filters)
    return JSONResponse({"ok": True, **export_audit_events(filtered)})


@app.get("/api/audit/replay")
async def audit_replay(request: Request):
    session = _get_session(request)
    if not session:
        return JSONResponse({"ok": False, "error": "AUTH_REQUIRED"}, status_code=401)

    user_ctx = session["user_ctx"]
    if not _can_view_audit_logs(user_ctx):
        return JSONResponse({"ok": False, "error": "AUDIT_AUTH_REQUIRED"}, status_code=403)

    limit = min(250, max(1, _safe_int(request.query_params.get("limit"), 100)))
    report = replay_mobile_trade_event_file(
        MOBILE_EVENTS_FILE,
        session_id=str(request.query_params.get("session_id", "MOBILE-AUDIT")),
        limit=limit,
    )
    return JSONResponse({"ok": True, **report.as_dict()})


@app.get("/controls", response_class=HTMLResponse)
async def controls_screen(request: Request):
    session = _get_session(request)
    if not session:
        return RedirectResponse("/login", status_code=303)

    return HTMLResponse(_controls_page(session["user_ctx"]))


@app.post("/controls", response_class=HTMLResponse)
async def controls_submit(request: Request):
    session = _get_session(request)
    if not session:
        return RedirectResponse("/login", status_code=303)

    user_ctx = session["user_ctx"]
    if not _can_manage_mobile_controls(user_ctx):
        return HTMLResponse(
            _controls_page(
                user_ctx,
                message="Your CSS role cannot change system controls.",
                status="error",
            ),
            status_code=403,
        )

    form = await _read_form(request)
    if form.get("mobile_trading_mode") == "MOBILE_LIVE_TRADING_ARMED" and form.get("legal_acceptance") != "on":
        return HTMLResponse(
            _controls_page(
                user_ctx,
                message="Live trading blocked. You must explicitly acknowledge the live capital warning.",
                status="error",
            ),
            status_code=400,
        )
        
    if form.get("mobile_trading_mode") == "MOBILE_LIVE_TRADING_ARMED" and form.get("legal_acceptance") == "on":
        audit_event = {
            "event_type": "LEGAL_ACCEPTANCE",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": str(user_ctx.get("user_id")),
            "role": str(user_ctx.get("role")),
            "version": "v1.0",
            "session_id": str(session.get("session_id", "MOBILE-SESSION"))
        }
        with open(PROJECT_ROOT / "artifacts" / "legal_acceptance_audit.jsonl", "a") as f:
            f.write(json.dumps(audit_event) + "\n")

    controls = _update_mobile_controls(form)
    return HTMLResponse(
        _controls_page(
            user_ctx,
            message=(
                f"Controls saved: {controls['mobile_trading_mode']}, "
                f"engine {controls['engine_mode']}."
            ),
            status="success",
        )
    )


@app.get("/trade", response_class=HTMLResponse)
async def trade_ticket_screen(request: Request):
    session = _get_session(request)
    if not session:
        return RedirectResponse("/login", status_code=303)

    return HTMLResponse(_trade_ticket_page(session["user_ctx"]))


@app.get("/trade-summary", response_class=HTMLResponse)
async def trade_summary_screen(request: Request):
    session = _get_session(request)
    if not session:
        return RedirectResponse("/login", status_code=303)

    return HTMLResponse(_trade_summary_page(session["user_ctx"], session))


@app.post("/trade", response_class=HTMLResponse)
async def trade_ticket_submit(request: Request):
    session = _get_session(request)
    if not session:
        return RedirectResponse("/login", status_code=303)

    form = await _read_form(request)
    result = execute_mobile_trade_ticket(session["user_ctx"], form)
    status = "success" if result.get("ok") else "error"
    return HTMLResponse(_trade_ticket_page(session["user_ctx"], result=result, status=status))


@app.get("/users", response_class=HTMLResponse)
async def users_screen(request: Request):
    session = _get_session(request)
    if not session:
        return RedirectResponse("/login", status_code=303)

    user_ctx = session["user_ctx"]
    if not can_manage_users(user_ctx):
        return HTMLResponse(
            _access_denied_page(user_ctx, "User administration requires SUPER_USER authority."),
            status_code=403,
        )

    return HTMLResponse(_users_page(user_ctx))


@app.post("/users", response_class=HTMLResponse)
async def users_submit(request: Request):
    session = _get_session(request)
    if not session:
        return RedirectResponse("/login", status_code=303)

    user_ctx = session["user_ctx"]
    if not can_manage_users(user_ctx):
        return HTMLResponse(
            _access_denied_page(user_ctx, "User administration requires SUPER_USER authority."),
            status_code=403,
        )

    form = await _read_form(request)
    users = load_users()
    try:
        created = create_user(
            users,
            user_ctx,
            user_id=form.get("user_id", ""),
            display_name=form.get("display_name", ""),
            role=form.get("role", "VIEWER"),
            initial_password=form.get("initial_password", ""),
            unit_code=form.get("unit_code", "CORE"),
            home_branch=form.get("home_branch", "HQ"),
            must_change_password=form.get("must_change_password", "on") == "on",
        )
        save_users(users)
    except (AuthFailure, PasswordValidationError, ValueError) as exc:
        save_users(users)
        return HTMLResponse(
            _users_page(user_ctx, message=str(exc), status="error"),
            status_code=400,
        )

    return HTMLResponse(
        _users_page(
            user_ctx,
            message=f"User {created['user_id']} created with role {created['role']}.",
            status="success",
        )
    )


@app.get("/manifest.webmanifest")
async def manifest():
    return JSONResponse(
        {
            "name": "Capital Strata Systems",
            "short_name": "CSS",
            "description": "Capital Strata Systems mobile dashboard",
            "start_url": "/login",
            "scope": "/",
            "display": "standalone",
            "background_color": "#f4f7f8",
            "theme_color": "#10202a",
            "icons": [
                {
                    "src": "/icon.svg",
                    "sizes": "any",
                    "type": "image/svg+xml",
                    "purpose": "any maskable",
                }
            ],
        }
    )


@app.get("/service-worker.js")
async def service_worker():
    script = """
const CACHE_NAME = "css-mobile-shell-v1";
const SHELL_URLS = ["/login", "/manifest.webmanifest", "/icon.svg"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_URLS)));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
    )
  );
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
});
""".strip()
    return PlainTextResponse(script, media_type="application/javascript")


@app.get("/icon.svg")
async def icon():
    svg = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="88" fill="#10202a"/>
  <circle cx="256" cy="256" r="172" fill="none" stroke="#1d8a8a" stroke-width="24"/>
  <circle cx="256" cy="256" r="118" fill="none" stroke="#c9861a" stroke-width="12"/>
  <path d="M126 322 L214 214 L286 270 L388 158" fill="none" stroke="#e8fbfb" stroke-width="26" stroke-linecap="round" stroke-linejoin="round"/>
  <text x="256" y="300" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="92" font-weight="700" fill="#ffffff">CSS</text>
</svg>
""".strip()
    return PlainTextResponse(svg, media_type="image/svg+xml")


def _login_success_response(user_ctx: Dict[str, Any]) -> RedirectResponse:
    token = _create_session(user_ctx)
    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        max_age=SESSION_MAX_SECONDS,
    )
    return response


def _create_session(user_ctx: Dict[str, Any]) -> str:
    token = secrets.token_urlsafe(32)
    now = time.time()
    _SESSIONS[token] = {
        "created": now,
        "last_activity": now,
        "user_ctx": dict(user_ctx),
    }
    return token


def _get_session(request: Request) -> Optional[Dict[str, Any]]:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None

    session = _SESSIONS.get(token)
    if not session:
        return None

    now = time.time()
    if now - float(session.get("created", now)) > SESSION_MAX_SECONDS:
        _SESSIONS.pop(token, None)
        return None

    session["last_activity"] = now
    return session


def _create_password_change_token(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    _PASSWORD_CHANGES[token] = {
        "user_id": user_id,
        "created": time.time(),
    }
    return token


def _get_password_change_record(request: Request) -> Optional[Dict[str, Any]]:
    token = request.cookies.get(PASSWORD_CHANGE_COOKIE)
    if not token:
        return None

    record = _PASSWORD_CHANGES.get(token)
    if not record:
        return None

    if time.time() - float(record.get("created", 0)) > PASSWORD_CHANGE_SECONDS:
        _PASSWORD_CHANGES.pop(token, None)
        return None

    return record


async def _read_form(request: Request) -> Dict[str, str]:
    raw = (await request.body()).decode("utf-8", errors="replace")
    parsed = urllib.parse.parse_qs(raw, keep_blank_values=True)
    return {key: values[-1] if values else "" for key, values in parsed.items()}


def load_mobile_controls() -> Dict[str, Any]:
    controls = dict(DEFAULT_MOBILE_CONTROLS)
    try:
        raw = MOBILE_CONTROL_FILE.read_text(encoding="utf-8").strip()
        data = json.loads(raw) if raw else {}
        if isinstance(data, dict):
            controls.update(data)
    except FileNotFoundError:
        pass
    except Exception:
        controls = dict(DEFAULT_MOBILE_CONTROLS)

    mode = str(controls.get("mobile_trading_mode", "MOBILE_READ_ONLY")).strip().upper()
    controls["mobile_trading_mode"] = mode if mode in {"MOBILE_READ_ONLY", "MOBILE_PAPER_TRADING", "MOBILE_LIVE_TRADING_ARMED"} else "MOBILE_READ_ONLY"

    # Backward compatibility mappings
    controls["runtime_mode"] = "live" if mode == "MOBILE_LIVE_TRADING_ARMED" else "paper"
    controls["orders_enabled"] = mode != "MOBILE_READ_ONLY"

    engine_mode = str(controls.get("engine_mode", "SAFE")).strip().upper()
    controls["engine_mode"] = engine_mode if engine_mode in ENGINE_MODES else "SAFE"
    controls["live_order_kill_switch"] = bool(
        controls.get("live_order_kill_switch", False)
    )
    return controls

def save_mobile_controls(controls: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(DEFAULT_MOBILE_CONTROLS)
    normalized.update(controls)
    mode = str(normalized.get("mobile_trading_mode", "MOBILE_READ_ONLY")).strip().upper()
    normalized["mobile_trading_mode"] = mode if mode in {"MOBILE_READ_ONLY", "MOBILE_PAPER_TRADING", "MOBILE_LIVE_TRADING_ARMED"} else "MOBILE_READ_ONLY"
    normalized["runtime_mode"] = "live" if mode == "MOBILE_LIVE_TRADING_ARMED" else "paper"
    normalized["orders_enabled"] = mode != "MOBILE_READ_ONLY"
    engine_mode = str(normalized.get("engine_mode", "SAFE")).strip().upper()
    normalized["engine_mode"] = engine_mode if engine_mode in ENGINE_MODES else "SAFE"
    normalized["live_order_kill_switch"] = bool(
        normalized.get("live_order_kill_switch", False)
    )
    normalized["updated_utc"] = datetime.now(timezone.utc).isoformat()

    MOBILE_CONTROL_FILE.parent.mkdir(parents=True, exist_ok=True)
    MOBILE_CONTROL_FILE.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
    return normalized

def _update_mobile_controls(form: Dict[str, str]) -> Dict[str, Any]:
    return save_mobile_controls(
        {
            "mobile_trading_mode": form.get("mobile_trading_mode", "MOBILE_READ_ONLY"),
            "engine_mode": form.get("engine_mode", "SAFE"),
            "live_order_kill_switch": (
                form.get("live_order_kill_switch", "off") == "on"
            ),
        }
    )



def _system_status(user_ctx: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    controls = load_mobile_controls()
    broker_ready = controls.get("mobile_trading_mode") == "MOBILE_LIVE_TRADING_ARMED"

    kill_switch = evaluate_live_order_kill_switch(controls)
    return {
        "runtime_mode": controls["runtime_mode"],
        "system_live": controls["runtime_mode"] == "live",
        "orders_enabled": bool(controls["orders_enabled"]),
        "engine_mode": controls["engine_mode"],
        "mobile_trading_mode": controls["mobile_trading_mode"],
        "live_order_kill_switch": kill_switch.blocked,
        "live_order_kill_switch_reason": kill_switch.reason,
        "broker_live_ready": broker_ready,
        "broker_live_gate": "READY" if broker_ready else "OFF",
        "live_orders_enabled": broker_ready and not kill_switch.blocked,
        "can_trade": _can_submit_trade(user_ctx or {}),
        "can_manage_controls": _can_manage_mobile_controls(user_ctx or {}),
        "can_manage_users": can_manage_users(user_ctx or {}),
        "can_view_audit": _can_view_audit_logs(user_ctx or {}),
    }


def _status_strip(user_ctx: Optional[Dict[str, Any]] = None) -> str:
    status = _system_status(user_ctx)
    role = html.escape(str((user_ctx or {}).get("role", "SIGNED_OUT")))
    system_mode = status.get("mobile_trading_mode", "READ_ONLY").replace("MOBILE_", "").replace("_", " ")
    order_state = "ENABLED" if status["orders_enabled"] else "DISABLED"
    kill_state = "ON" if status["live_order_kill_switch"] else "OFF"
    trade_state = "TRADE AUTH" if status["can_trade"] else "VIEW AUTH"
    return f"""
      <section class="system-strip" aria-label="CSS system status">
        <span>System {system_mode}</span>
        <span>Engine {html.escape(str(status['engine_mode']))}</span>
        <span>Orders {order_state}</span>
        <span>Kill Switch {kill_state}</span>
        <span>Broker Gate {html.escape(str(status['broker_live_gate']))}</span>
        <span>{role}</span>
        <span>{trade_state}</span>
      </section>
    """


def _top_nav(user_ctx: Dict[str, Any], active: str) -> str:
    links = []
    if active != "dashboard":
        links.append('<a class="button-link" href="/dashboard">Dashboard</a>')
    for key, label, href in (
        ("positions", "Positions", "/positions"),
        ("history", "History", "/history"),
        ("risk", "Risk", "/risk"),
        ("governance", "Governance", "/governance"),
        ("opportunities", "Opportunities", "/opportunities"),
        ("market", "Market", "/market"),
        ("broker", "Broker", "/broker"),
        ("trade-status", "Trade Status", "/trade-status"),
        ("trade-summary", "Trade Summary", "/trade-summary"),
    
        ("margin", "Margin", "/margin"),):
        if active != key:
            links.append(
                f'<a class="button-link quiet" href="{href}">{label}</a>'
            )
    if active != "audit" and _can_view_audit_logs(user_ctx):
        links.append('<a class="button-link quiet" href="/audit">Audit</a>')
    if active != "trade" and _can_submit_trade(user_ctx):
        links.append('<a class="button-link" href="/trade">Trade</a>')
    if active != "controls" and _can_manage_mobile_controls(user_ctx):
        links.append('<a class="button-link" href="/controls">Controls</a>')
    if active != "users" and can_manage_users(user_ctx):
        links.append('<a class="button-link" href="/users">Users</a>')
    links.append(
        '<form method="post" action="/logout"><button class="ghost" type="submit">Logout</button></form>'
    )
    return "\n".join(links)


def _header(title: str, user_ctx: Dict[str, Any], active: str) -> str:
    return f"""
      <div style="background-color:#ffebee;color:#b71c1c;text-align:center;padding:8px;font-weight:bold;font-size:0.85em;border-bottom:1px solid #b71c1c;" aria-label="Risk Warning">
        Trading involves substantial risk. Loss of capital may occur. Past performance does not guarantee future results.
      </div>
      <header class="mobile-topbar">
        <div>
          <p class="eyebrow">Capital Strata Systems</p>
          <h1>{html.escape(title)}</h1>
        </div>
        <nav class="top-actions" aria-label="Mobile controls">
          {_top_nav(user_ctx, active)}
        </nav>
      </header>
      {_status_strip(user_ctx)}
    """


def _identity_strip(user_ctx: Dict[str, Any], extra: str = "") -> str:
    safe_name = html.escape(str(user_ctx.get("display_name", "CSS User")))
    safe_role = html.escape(str(user_ctx.get("role", "VIEWER")))
    safe_user_id = html.escape(str(user_ctx.get("user_id", "")))
    extra_markup = f"<span>{html.escape(extra)}</span>" if extra else ""
    return f"""
      <section class="identity-strip">
        <span>{safe_name}</span>
        <span>{safe_role}</span>
        <span>ID {safe_user_id}</span>
        {extra_markup}
      </section>
    """


def _can_submit_trade(user_ctx: Dict[str, Any]) -> bool:
    role = _normalize_role(user_ctx.get("role", ""))
    if role == "SUPER_USER":
        return True
    return _permission_allowed(role, "submit_trade") or _permission_allowed(role, "place_trade")


def _can_manage_mobile_controls(user_ctx: Dict[str, Any]) -> bool:
    role = _normalize_role(user_ctx.get("role", ""))
    return role == "SUPER_USER" or _permission_allowed(role, "manage_system")


def _can_view_audit_logs(user_ctx: Dict[str, Any]) -> bool:
    role = _normalize_role(user_ctx.get("role", ""))
    return role == "SUPER_USER" or _permission_allowed(role, "view_audit_logs")


def _permission_allowed(role: str, action: str) -> bool:
    try:
        return bool(PermissionEngine().check(role, action).allowed)
    except Exception:
        return False


def _normalize_role(value: Any) -> str:
    return str(value or "").strip().upper().replace(" ", "_").replace("-", "_")


def _selected(value: str, current: str) -> str:
    return " selected" if str(value).lower() == str(current).lower() else ""


def _checked(value: bool) -> str:
    return " checked" if value else ""


def _login_page(message: str = "", status: str = "info") -> str:
    return _page(
        "Sign On",
        f"""
        <main class="auth-shell">
          <section class="brand-panel" aria-label="Capital Strata Systems">
            <div class="brand-mark">
              <svg viewBox="0 0 120 120" role="img" aria-label="CSS">
                <circle cx="60" cy="60" r="50"></circle>
                <path d="M24 74 L48 46 L68 61 L96 33"></path>
                <text x="60" y="72">CSS</text>
              </svg>
            </div>
            <h1>Capital Strata Systems</h1>
            <p>Mobile dashboard access</p>
            <div class="policy-row">
              <span>Auth Required</span>
              <span>Timed Lockouts</span>
              <span>Role Authority</span>
            </div>
          </section>

          <section class="form-panel" aria-label="Sign on form">
            <h2>Sign On</h2>
            <p class="muted">Use your CSS user ID and password.</p>
            {_status_strip(None)}
            {_status_markup(message, status)}
            <form method="post" action="/login" autocomplete="on">
              <label for="user_id">User ID</label>
              <input id="user_id" name="user_id" inputmode="numeric" pattern="[0-9]*" autocomplete="username" required>

              <label for="password">Password</label>
              <input id="password" name="password" type="password" required>

              <button type="submit">Sign On</button>
            </form>
          </section>
        </main>
        """,
    )


def _password_change_page(message: str = "", status: str = "info") -> str:
    return _page(
        "Password Update",
        f"""
        <main class="auth-shell single">
          <section class="form-panel" aria-label="Password change form">
            <h2>Password Update</h2>
            <p class="muted">Initial or expired passwords must be changed now.</p>
            {_status_strip(None)}
            {_status_markup(message, status)}
            <form method="post" action="/password-change" autocomplete="off">
              <label for="new_password">New Password</label>
              <input id="new_password" name="new_password" type="password" required>

              <label for="confirm_password">Confirm Password</label>
              <input id="confirm_password" name="confirm_password" type="password" required>

              <button type="submit">Update Password</button>
            </form>
          </section>
        </main>
        """,
    )


def _dashboard_page(user_ctx: Dict[str, Any], session: Dict[str, Any]) -> str:
    dashboard_text = _mobile_dashboard_text(user_ctx, session)
    dashboard_payload = _mobile_dashboard_payload(user_ctx, session)
    status = _system_status(user_ctx)
    system_mode = "Live" if status["system_live"] else "Paper"
    order_state = "Enabled" if status["orders_enabled"] else "Disabled"
    broker_gate = "Ready" if status["broker_live_ready"] else "Off"

    return _page(
        "Dashboard",
        f"""
        <main class="dashboard-shell">
          {_header("Dashboard", user_ctx, "dashboard")}
          {_identity_strip(user_ctx, "Mobile Role Access")}

          <section class="metric-grid" aria-label="Dashboard summary">
            <article><strong>System</strong><span>{system_mode}</span></article>
            <article><strong>Engine</strong><span>{html.escape(str(status['engine_mode']))}</span></article>
            <article><strong>Orders</strong><span>{order_state}</span></article>
            <article><strong>Broker Gate</strong><span>{broker_gate}</span></article>
          </section>

          {_account_summary_cards(dashboard_payload)}
          {_command_center_panel(user_ctx)}
          {_recent_tickets_panel()}

          <section class="terminal-panel" aria-label="Dashboard output">
            <pre>{html.escape(dashboard_text)}</pre>
          </section>
        </main>
        """,
    )


def _mobile_dashboard_text(user_ctx: Dict[str, Any], session: Dict[str, Any]) -> str:
    return DashboardRuntimeBootstrap().run(
        **_mobile_runtime_payloads(user_ctx, session)
    )


def _mobile_dashboard_payload(
    user_ctx: Dict[str, Any],
    session: Dict[str, Any],
) -> Dict[str, Any]:
    state = DashboardHydrationCoordinator().hydrate(
        **_mobile_runtime_payloads(user_ctx, session)
    )
    return state.to_dict()


def _trade_summary_page(user_ctx: Dict[str, Any], session: Dict[str, Any]) -> str:
    try:
        from analytics.trade_outcome_ledger import TradeOutcomeLedger
        trades = TradeOutcomeLedger().list_trades()
        # newest first
        trades = sorted(trades, key=lambda t: t.exit_timestamp, reverse=True)[:20]
    except Exception:
        trades = []

    if not trades:
        content = '<div class="card"><p class="muted">No closed trades recorded yet.</p></div>'
    else:
        cards = []
        for t in trades:
            pnl = t.realized_pnl
            if pnl > 0:
                pnl_class = "pnl-green"
                pnl_str = f"+{pnl:.2f}"
            elif pnl < 0:
                pnl_class = "pnl-red"
                pnl_str = f"{pnl:.2f}"
            else:
                pnl_class = "muted"
                pnl_str = "0.00"

            cards.append(f"""
            <div class="card" style="margin-bottom: 1rem; padding: 1rem; border: 1px solid #ccc; border-radius: 4px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
                    <strong>{html.escape(t.symbol)}</strong>
                    <span class="{pnl_class}"><strong>{pnl_str}</strong></span>
                </div>
                <div style="font-size: 0.9em; line-height: 1.4;">
                    <div><span class="muted">Date:</span> {html.escape(t.exit_timestamp)}</div>
                    <div><span class="muted">Class:</span> {html.escape(t.asset_class)}</div>
                    <div><span class="muted">Side:</span> {html.escape(getattr(t, 'side', 'UNKNOWN'))}</div>
                    <div><span class="muted">Qty:</span> {getattr(t, 'quantity', 0.0)}</div>
                    <div><span class="muted">Amt Traded:</span> {getattr(t, 'amount_traded', 0.0):.2f}</div>
                    <div><span class="muted">W/L:</span> {html.escape(t.win_loss)}</div>
                    <div><span class="muted">Cum Bal:</span> {getattr(t, 'cumulative_account_balance', 0.0):.2f}</div>
                    <div><span class="muted">Exit Reason:</span> {html.escape(t.exit_reason)}</div>
                </div>
            </div>
            """)
        content = "".join(cards)

    return _page(
        "CSS Trade Summary",
        f"""
        <main class="dashboard-shell">
          {_header("CSS Trade Summary", user_ctx, "trade-summary")}
          <section class="metric-grid" aria-label="Trade Summary" style="display: block;">
            {content}
          </section>
        </main>
        """
    )


def _mobile_runtime_payloads(
    user_ctx: Dict[str, Any],
    session: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    controls = load_mobile_controls()
    runtime_mode = str(controls["runtime_mode"])
    engine_mode = str(controls["engine_mode"])
    orders_enabled = bool(controls["orders_enabled"])
    return {
        "account_payload": {
            "cash_balance": 10000.00,
            "total_equity": 10250.00,
            "buying_power": 5000.00,
            "margin_used": 0.00,
            "available_margin": 5000.00,
            "currency": "USD",
            "broker": "MOBILE",
            "account_mode": runtime_mode,
        },
        "positions_payload": {
            "positions": [
                {
                    "symbol": "BTC-USD",
                    "asset_class": "CRYPTO",
                    "side": "LONG",
                    "qty": 0.05,
                    "entry_price": 65000.00,
                    "current_price": 65500.00,
                    "unrealized_pnl": 25.00,
                    "realized_pnl": 0.00,
                },
                {
                    "symbol": "EUR_USD",
                    "asset_class": "FX",
                    "side": "SHORT",
                    "qty": 1000,
                    "entry_price": 1.0900,
                    "current_price": 1.0875,
                    "unrealized_pnl": 2.50,
                    "realized_pnl": 0.00,
                },
            ]
        },
        "market_payload": {
            "trend_state": "UPTREND",
            "volatility_state": "NORMAL",
            "liquidity_state": "HEALTHY",
            "mean_reversion_state": "NEUTRAL",
            "probability_state": "FAVORABLE",
            "velocity_state": "RISING",
            "vwap_state": "ABOVE_VWAP",
            "vwap_distance": 0.0125,
            "vwap_elasticity": 0.8300,
            "momentum_state": "POSITIVE",
            "pressure_state": "BUY_PRESSURE",
            "acceleration_state": "STABLE",
            "regime_state": f"MOBILE_{runtime_mode.upper()}",
            "spread_state": "TIGHT",
            "execution_cost_state": "MOBILE_GOVERNED",
            "signal_confluence_state": "CONFIRMED",
        },
        "governance_payload": {
            "governance_enabled": True,
            "session_locked": False,
            "defensive_mode_active": False,
            "unified_trade_gate_active": True,
            "audit_enabled": True,
            "last_governance_event": (
                f"Mobile dashboard authenticated; mode={runtime_mode}; "
                f"orders={'enabled' if orders_enabled else 'disabled'}"
            ),
        },
        "risk_payload": {
            "risk_state": "AUTHENTICATED",
            "gate_status": f"MOBILE_{runtime_mode.upper()}_ACCESS",
            "current_drawdown_pct": 0.35,
            "max_drawdown_pct": 2.00,
            "daily_loss_limit": 500.00,
            "position_limit": 10,
            "exposure_limit": 25000.00,
            "risk_limits_breached": [],
        },
        "execution_payload": {
            "execution_state": "AUTHORIZED_MOBILE" if orders_enabled else "MOBILE_ORDERS_DISABLED",
            "accepted_trade_count": 0,
            "rejected_trade_count": 0,
            "pending_trade_count": 0,
            "total_execution_cost": 0.00,
            "slippage_cost": 0.00,
            "spread_cost": 0.00,
            "fee_cost": 0.00,
            "avg_slippage_bps": 0.00,
            "avg_spread_bps": 0.00,
            "execution_cost_state": "GOVERNED_BY_CSS",
            "last_execution_event": "Phone dashboard is governed by mobile runtime controls",
        },
        "session_payload": {
            "session_id": "MOBILE-SESSION",
            "user_id": str(user_ctx.get("user_id", "mobile_user")),
            "role": str(user_ctx.get("role", "VIEWER")),
            "cycle_number": 1,
            "engine_mode": engine_mode,
            "live_or_paper": runtime_mode,
        },
        "diagnostics_payload": {
            "message": f"Mobile session created={int(float(session.get('created', 0)))}"
        },
    }


def _account_summary_cards(dashboard_payload: Dict[str, Any]) -> str:
    account = _mapping(dashboard_payload.get("account_summary"))
    pnl = _mapping(dashboard_payload.get("pnl_summary"))
    open_positions = _mapping(dashboard_payload.get("open_positions"))

    return f"""
      <section class="data-panel" aria-label="Institutional account summary">
        <h2>Account Summary</h2>
        <div class="metric-grid account-grid">
          <article><strong>Cash</strong><span>{_money(account.get("cash_balance"))}</span></article>
          <article><strong>Total Equity</strong><span>{_money(account.get("total_equity"))}</span></article>
          <article><strong>Net PnL</strong><span>{_money(pnl.get("net_pnl"))}</span></article>
          <article><strong>Open Positions</strong><span>{html.escape(str(open_positions.get("total", 0)))}</span></article>
          <article><strong>Buying Power</strong><span>{_money(account.get("buying_power"))}</span></article>
          <article><strong>Margin Used</strong><span>{_money(account.get("margin_used"))}</span></article>
          <article><strong>Available Margin</strong><span>{_money(account.get("available_margin"))}</span></article>
          <article><strong>Exposure</strong><span>{_money(pnl.get("total_exposure"))}</span></article>
        </div>
      </section>
    """


def _command_center_panel(user_ctx: Dict[str, Any]) -> str:
    cards = [
        ("Positions", "Open position inventory and asset counts.", "/positions"),
        ("History", "Trade ticket and execution outcome log.", "/history"),
        ("Risk", "Drawdown, exposure, limits, and breaches.", "/risk"),
        ("Governance", "Session gate, audit, and authority state.", "/governance"),
        ("Opportunities", "Current monitor queue and watchlist posture.", "/opportunities"),
        ("Market", "Regime, VWAP, liquidity, and pressure state.", "/market"),
        ("Broker", "Broker readiness and live-order gate posture.", "/broker"),
    ]
    if _can_view_audit_logs(user_ctx):
        cards.append(("Audit", "Filter, export, and review governed event trails.", "/audit"))
    if _can_submit_trade(user_ctx):
        cards.append(("Trade", "Submit governed paper/live tickets.", "/trade"))
    if _can_manage_mobile_controls(user_ctx):
        cards.append(("Controls", "Change mobile mode and order state.", "/controls"))
    if can_manage_users(user_ctx):
        cards.append(("Users", "Create users and assign authority.", "/users"))

    links = "\n".join(
        f"""
        <a class="command-card" href="{href}">
          <strong>{html.escape(title)}</strong>
          <span>{html.escape(description)}</span>
        </a>
        """
        for title, description, href in cards
    )
    return f"""
      <section class="data-panel" aria-label="CSS command center">
        <h2>Command Center</h2>
        <div class="command-grid">
          {links}
        </div>
      </section>
    """


def _positions_page(user_ctx: Dict[str, Any], session: Dict[str, Any]) -> str:
    payloads = _mobile_runtime_payloads(user_ctx, session)
    dashboard_payload = _mobile_dashboard_payload(user_ctx, session)
    positions = payloads["positions_payload"].get("positions", [])
    rows = "\n".join(_position_row_markup(position) for position in positions)
    if not rows:
        rows = '<div class="ops-row"><span>No open positions.</span></div>'
    open_positions = _mapping(dashboard_payload.get("open_positions"))
    by_asset = _mapping(open_positions.get("by_asset"))

    return _page(
        "Positions",
        f"""
        <main class="dashboard-shell">
          {_header("Positions", user_ctx, "positions")}
          {_identity_strip(user_ctx, "Position Inventory")}
          <section class="metric-grid" aria-label="Position summary">
            <article><strong>Total Open</strong><span>{html.escape(str(open_positions.get("total", 0)))}</span></article>
            <article><strong>Crypto</strong><span>{html.escape(str(by_asset.get("CRYPTO", 0)))}</span></article>
            <article><strong>FX</strong><span>{html.escape(str(by_asset.get("FX", 0)))}</span></article>
            <article><strong>Source</strong><span>Runtime</span></article>
          </section>
          <section class="data-panel" aria-label="Positions screen">
            <h2>Positions Screen</h2>
            <div class="ops-table positions-table">
              <div class="ops-row ops-head">
                <span>Symbol</span><span>Asset</span><span>Side</span><span>Qty</span><span>Entry</span><span>Mark</span><span>Unrealized</span>
              </div>
              {rows}
            </div>
          </section>
        </main>
        """,
    )


def _history_page(user_ctx: Dict[str, Any], session: Dict[str, Any]) -> str:
    events = _recent_mobile_events(25)
    rows = "\n".join(_history_row_markup(event) for event in events)
    if not rows:
        rows = '<div class="ops-row"><span>No mobile execution events yet.</span></div>'

    return _page(
        "Trade History",
        f"""
        <main class="dashboard-shell">
          {_header("Trade / Execution History", user_ctx, "history")}
          {_identity_strip(user_ctx, "Audit Trail")}
          <section class="metric-grid" aria-label="History summary">
            <article><strong>Visible Events</strong><span>{len(events)}</span></article>
            <article><strong>Audit Source</strong><span>JSONL</span></article>
            <article><strong>Secrets</strong><span>Redacted</span></article>
            <article><strong>Mode</strong><span>{html.escape(str(load_mobile_controls()["runtime_mode"]).title())}</span></article>
          </section>
          <section class="data-panel" aria-label="Trade and execution history">
            <h2>Trade / Execution History</h2>
            <div class="ops-table history-table">
              <div class="ops-row ops-head">
                <span>Recorded</span><span>Status</span><span>Mode</span><span>Broker</span><span>Symbol</span><span>Side</span><span>Amount</span>
              </div>
              {rows}
            </div>
          </section>
        </main>
        """,
    )


def _risk_page(user_ctx: Dict[str, Any], session: Dict[str, Any]) -> str:
    risk = _mapping(_mobile_dashboard_payload(user_ctx, session).get("risk_summary"))
    breaches = risk.get("risk_limits_breached")
    breach_items = breaches if isinstance(breaches, list) and breaches else ["NONE"]
    breach_markup = "\n".join(
        f"<li>{html.escape(str(item))}</li>" for item in breach_items
    )

    return _page(
        "Risk",
        f"""
        <main class="dashboard-shell">
          {_header("Risk Control Center", user_ctx, "risk")}
          {_identity_strip(user_ctx, "Risk Oversight")}
          <section class="metric-grid" aria-label="Risk control center">
            <article><strong>Risk State</strong><span>{html.escape(str(risk.get("risk_state", "NORMAL")))}</span></article>
            <article><strong>Gate</strong><span>{html.escape(str(risk.get("gate_status", "OPEN")))}</span></article>
            <article><strong>Drawdown</strong><span>{_percent(risk.get("current_drawdown_pct"))}</span></article>
            <article><strong>Max Drawdown</strong><span>{_percent(risk.get("max_drawdown_pct"))}</span></article>
            <article><strong>Exposure</strong><span>{_money(risk.get("total_exposure"))}</span></article>
            <article><strong>Exposure Util.</strong><span>{_percent(risk.get("exposure_utilization_pct"))}</span></article>
            <article><strong>Daily Loss Limit</strong><span>{_money(risk.get("daily_loss_limit"))}</span></article>
            <article><strong>Position Limit</strong><span>{html.escape(str(risk.get("position_limit", 0)))}</span></article>
          </section>
          <section class="data-panel" aria-label="Risk breaches">
            <h2>Risk Limit Breaches</h2>
            <ul class="compact-list">{breach_markup}</ul>
          </section>
        </main>
        """,
    )


def _governance_page(user_ctx: Dict[str, Any], session: Dict[str, Any]) -> str:
    governance = _mapping(
        _mobile_dashboard_payload(user_ctx, session).get("governance_summary")
    )
    authority = {
        "Submit Trades": _can_submit_trade(user_ctx),
        "Manage Controls": _can_manage_mobile_controls(user_ctx),
        "Manage Users": can_manage_users(user_ctx),
    }
    authority_cards = "\n".join(
        f"<article><strong>{html.escape(label)}</strong><span>{_yes_no(value)}</span></article>"
        for label, value in authority.items()
    )

    return _page(
        "Governance",
        f"""
        <main class="dashboard-shell">
          {_header("Governance Center", user_ctx, "governance")}
          {_identity_strip(user_ctx, "Authority And Audit")}
          <section class="metric-grid" aria-label="Governance center">
            <article><strong>Governance</strong><span>{_yes_no(governance.get("governance_enabled"))}</span></article>
            <article><strong>Session Locked</strong><span>{_yes_no(governance.get("session_locked"))}</span></article>
            <article><strong>Defensive Mode</strong><span>{_yes_no(governance.get("defensive_mode_active"))}</span></article>
            <article><strong>Unified Gate</strong><span>{_yes_no(governance.get("unified_trade_gate_active"))}</span></article>
            <article><strong>Audit</strong><span>{_yes_no(governance.get("audit_enabled"))}</span></article>
            {authority_cards}
          </section>
          <section class="data-panel" aria-label="Governance event">
            <h2>Last Governance Event</h2>
            <p>{html.escape(str(governance.get("last_governance_event", "NONE") or "NONE"))}</p>
          </section>
        </main>
        """,
    )


def _opportunities_page(user_ctx: Dict[str, Any], session: Dict[str, Any]) -> str:
    opportunities = _opportunity_rows(user_ctx, session)
    rows = "\n".join(_opportunity_row_markup(item) for item in opportunities)

    return _page(
        "Opportunities",
        f"""
        <main class="dashboard-shell">
          {_header("Opportunity Monitor", user_ctx, "opportunities")}
          {_identity_strip(user_ctx, "Monitor Only")}
          <section class="data-panel" aria-label="Opportunity monitor">
            <h2>Opportunity Monitor</h2>
            <p class="muted">This screen is observational. Trade execution remains governed by CSS tickets, role authority, order controls, and broker gates.</p>
            <div class="ops-table opportunity-table">
              <div class="ops-row ops-head">
                <span>Symbol</span><span>Asset</span><span>Bias</span><span>State</span><span>Action</span>
              </div>
              {rows}
            </div>
          </section>
        </main>
        """,
    )


def _market_page(user_ctx: Dict[str, Any], session: Dict[str, Any]) -> str:
    market = _mapping(_mobile_dashboard_payload(user_ctx, session).get("market_summary"))

    return _page(
        "Market",
        f"""
        <main class="dashboard-shell">
          {_header("Market Regime Panel", user_ctx, "market")}
          {_identity_strip(user_ctx, "Regime And Microstructure")}
          <section class="metric-grid" aria-label="Market regime panel">
            <article><strong>Trend</strong><span>{html.escape(str(market.get("trend_state", "UNKNOWN")))}</span></article>
            <article><strong>Volatility</strong><span>{html.escape(str(market.get("volatility_state", "UNKNOWN")))}</span></article>
            <article><strong>Liquidity</strong><span>{html.escape(str(market.get("liquidity_state", "UNKNOWN")))}</span></article>
            <article><strong>Regime</strong><span>{html.escape(str(market.get("regime_state", "UNKNOWN")))}</span></article>
            <article><strong>VWAP</strong><span>{html.escape(str(market.get("vwap_state", "UNKNOWN")))}</span></article>
            <article><strong>VWAP Dist.</strong><span>{_number(market.get("vwap_distance"), 4)}</span></article>
            <article><strong>Momentum</strong><span>{html.escape(str(market.get("momentum_state", "UNKNOWN")))}</span></article>
            <article><strong>Pressure</strong><span>{html.escape(str(market.get("pressure_state", "UNKNOWN")))}</span></article>
          </section>
          <section class="data-panel" aria-label="Market details">
            <h2>Signal Context</h2>
            <div class="kv-grid">
              {_kv("Mean Reversion", market.get("mean_reversion_state"))}
              {_kv("Probability", market.get("probability_state"))}
              {_kv("Velocity", market.get("velocity_state"))}
              {_kv("Acceleration", market.get("acceleration_state"))}
              {_kv("Spread", market.get("spread_state"))}
              {_kv("Execution Cost", market.get("execution_cost_state"))}
              {_kv("Signal Confluence", market.get("signal_confluence_state"))}
            </div>
          </section>
        </main>
        """,
    )


def _broker_page(user_ctx: Dict[str, Any], session: Dict[str, Any]) -> str:
    load_local_env()
    dashboard_payload = _mobile_dashboard_payload(user_ctx, session)
    broker = _mapping(dashboard_payload.get("broker_summary"))
    reconciliation = build_broker_reconciliation_payload(dashboard_payload)
    status = _system_status(user_ctx)
    controls_link = (
        '<a class="button-link" href="/controls">Open Controls</a>'
        if _can_manage_mobile_controls(user_ctx)
        else ""
    )

    return _page(
        "Broker",
        f"""
        <main class="dashboard-shell">
          {_header("Broker Control Panel", user_ctx, "broker")}
          {_identity_strip(user_ctx, "Broker Readiness")}
          <section class="metric-grid" aria-label="Broker control panel">
            <article><strong>Selected</strong><span>{html.escape(str(broker.get("selected_broker", "MOBILE")))}</span></article>
            <article><strong>Mode</strong><span>{html.escape(str(status["runtime_mode"]).title())}</span></article>
            <article><strong>Broker Gate</strong><span>{html.escape(str(status["broker_live_gate"]))}</span></article>
            <article><strong>Orders</strong><span>{'Enabled' if status["orders_enabled"] else 'Disabled'}</span></article>
            <article><strong>Live Trading</strong><span>{_yes_no(status["broker_live_ready"])}</span></article>
            <article><strong>Reconciliation</strong><span>{html.escape(str(reconciliation.get("status", "UNKNOWN")))}</span></article>
            <article><strong>Safe Downgrade</strong><span>{_yes_no(reconciliation.get("safe_degradation_required"))}</span></article>
          </section>
          <section class="data-panel" aria-label="Broker controls">
            <h2>Broker Controls</h2>
            <p class="muted">Broker secrets are never displayed. Live orders still require CSS live mode, order enablement, broker readiness, role authority, and explicit EXECUTE confirmation.</p>
            {controls_link}
          </section>
        </main>
        """,
    )



def _margin_page(user_ctx: Dict[str, Any], session: Dict[str, Any]) -> str:
    return _page(
        "Margin",
        f"""
        <main class="dashboard-shell">
          {_header("Margin Visibility", user_ctx, "margin")}
          {_identity_strip(user_ctx, "Margin Read-Only")}
          
          <section class="data-panel" aria-label="Margin Snapshot">
            <h2 id="margin-state-header">State PENDING</h2>
            <p class="muted" id="margin-timestamp">Pending</p>
            <div id="margin-data-container" class="metric-grid">
              <article><strong>Broker</strong><span id="margin-broker">--</span></article>
              <article><strong>Account ID</strong><span id="margin-account-id">--</span></article>
              <article><strong>Equity</strong><span id="margin-equity">--</span></article>
              <article><strong>Cash</strong><span id="margin-cash">--</span></article>
              <article><strong>Buying Power</strong><span id="margin-buying-power">--</span></article>
              <article><strong>Margin Used</strong><span id="margin-margin-used">--</span></article>
              <article><strong>Margin Available</strong><span id="margin-margin-available">--</span></article>
              <article><strong>Maintenance Margin</strong><span id="margin-maintenance-margin">--</span></article>
              <article><strong>Initial Margin</strong><span id="margin-initial-margin">--</span></article>
              <article><strong>Margin Ratio</strong><span id="margin-margin-ratio">--</span></article>
              <article><strong>Margin State</strong><span id="margin-margin-state" style="font-weight:bold;">--</span></article>
            </div>
            <div id="margin-error" style="display:none; color:#ff4d4f; padding:20px; font-weight:bold; font-size:18px;">DATA UNAVAILABLE</div>
            <button type="button" data-refresh-margin style="margin-top:20px;">Refresh Margin</button>
          </section>
        </main>
        <script>
          function money(val) {{
            return new Intl.NumberFormat("en-US", {{style: "currency", currency: "USD"}}).format(Number(val||0));
          }}
          async function refreshMargin() {{
            try {{
              const response = await fetch("/api/margin-snapshot", {{ cache: "no-store" }});
              const data = await response.json();
              const container = document.getElementById("margin-data-container");
              const errorDiv = document.getElementById("margin-error");
              
              if (!data.ok) {{
                container.style.display = "none";
                errorDiv.style.display = "block";
                document.getElementById("margin-state-header").textContent = "DATA UNAVAILABLE";
                document.getElementById("margin-timestamp").textContent = "DATA UNAVAILABLE";
              }} else {{
                container.style.display = "grid";
                errorDiv.style.display = "none";
                document.getElementById("margin-broker").textContent = data.broker;
                document.getElementById("margin-account-id").textContent = data.account_id;
                document.getElementById("margin-equity").textContent = money(data.equity);
                document.getElementById("margin-cash").textContent = money(data.cash);
                document.getElementById("margin-buying-power").textContent = money(data.buying_power);
                document.getElementById("margin-margin-used").textContent = money(data.margin_used);
                document.getElementById("margin-margin-available").textContent = money(data.margin_available);
                document.getElementById("margin-maintenance-margin").textContent = money(data.maintenance_margin);
                document.getElementById("margin-initial-margin").textContent = money(data.initial_margin);
                document.getElementById("margin-margin-ratio").textContent = Number(data.margin_ratio).toFixed(4);
                
                const stateEl = document.getElementById("margin-margin-state");
                stateEl.textContent = data.margin_state;
                const stateColors = {{
                  "NORMAL": "#4caf50",
                  "WARNING": "#ff9800",
                  "RESTRICTED": "#ff5722",
                  "CRITICAL": "#f44336",
                  "LIQUIDATION_RISK": "#b71c1c"
                }};
                stateEl.style.color = stateColors[data.margin_state] || "inherit";
                
                document.getElementById("margin-state-header").textContent = `State ${{data.margin_state}}`;
                document.getElementById("margin-timestamp").textContent = data.timestamp;
              }}
            }} catch (err) {{
              document.getElementById("margin-data-container").style.display = "none";
              document.getElementById("margin-error").style.display = "block";
            }}
          }}
          document.querySelector("[data-refresh-margin]").addEventListener("click", refreshMargin);
          refreshMargin().catch(() => undefined);
        </script>
        """
    )


def _audit_page(
    user_ctx: Dict[str, Any],
    category: str = "",
    status: str = "",
    actor: str = "",
) -> str:
    events = load_mobile_trade_audit_events(MOBILE_EVENTS_FILE, limit=250)
    filtered = filter_audit_events(
        events,
        category=category,
        status=status,
        actor=actor,
    )
    summary = summarize_audit_events(filtered)
    rows = "\n".join(_audit_row_markup(event) for event in filtered)
    if not rows:
        rows = '<div class="ops-row"><span>No matching audit events.</span></div>'

    export_href = _audit_export_href(category=category, status=status, actor=actor)
    replay_href = _audit_replay_href()
    return _page(
        "Audit Trail",
        f"""
        <main class="dashboard-shell">
          {_header("Audit Trail Viewer", user_ctx, "audit")}
          {_identity_strip(user_ctx, "Read Only Audit")}

          <section class="metric-grid" aria-label="Audit summary">
            <article><strong>Visible Events</strong><span>{summary["event_count"]}</span></article>
            <article><strong>Replayable</strong><span>{summary["replayable_count"]}</span></article>
            <article><strong>Payload</strong><span>v1</span></article>
            <article><strong>Secrets</strong><span>Redacted</span></article>
          </section>

          <section class="form-panel trade-form-panel audit-filter-panel" aria-label="Audit filters">
            <h2>Filters</h2>
            <form method="get" action="/audit" autocomplete="off">
              <label for="category">Category</label>
              <select id="category" name="category">
                {_audit_category_options(category)}
              </select>

              <label for="status">Status Contains</label>
              <input id="status" name="status" value="{html.escape(status)}">

              <label for="actor">User ID Contains</label>
              <input id="actor" name="actor" value="{html.escape(actor)}">

              <button type="submit">Apply Filters</button>
              <a class="button-link quiet" href="{html.escape(export_href)}">Export JSON</a>
              <a class="button-link quiet" href="{html.escape(replay_href)}">Replay JSON</a>
            </form>
          </section>

          <section class="data-panel" aria-label="Institutional audit trail viewer">
            <h2>Audit Trail Viewer</h2>
            <p class="muted">Read-only operational trail sourced from CSS runtime events. Exports use the same redacted frontend-safe payload.</p>
            <div class="ops-table audit-table">
              <div class="ops-row ops-head">
                <span>Time</span><span>Category</span><span>Status</span><span>User</span><span>Source</span><span>Reason</span><span>Replay</span>
              </div>
              {rows}
            </div>
          </section>
        </main>
        """,
    )


def _audit_query_filters(request: Request) -> Dict[str, str]:
    query = request.query_params
    return {
        "category": str(query.get("category", ""))[:64],
        "status": str(query.get("status", ""))[:96],
        "actor": str(query.get("actor", ""))[:64],
    }


def _audit_category_options(current: str) -> str:
    options = ['<option value="">All Categories</option>']
    for category in AUDIT_CATEGORY_OPTIONS:
        selected = " selected" if category == current else ""
        label = category.replace("_", " ").title()
        options.append(
            f'<option value="{html.escape(category)}"{selected}>{html.escape(label)}</option>'
        )
    return "\n".join(options)


def _audit_export_href(category: str = "", status: str = "", actor: str = "") -> str:
    query = urllib.parse.urlencode(
        {
            key: value
            for key, value in {
                "category": category,
                "status": status,
                "actor": actor,
            }.items()
            if value
        }
    )
    return "/api/audit/export" if not query else f"/api/audit/export?{query}"


def _audit_replay_href() -> str:
    return "/api/audit/replay"


def _controls_page(
    user_ctx: Dict[str, Any],
    message: str = "",
    status: str = "info",
) -> str:
    controls = load_mobile_controls()
    can_manage = _can_manage_mobile_controls(user_ctx)
    disabled = "" if can_manage else " disabled"
    submit_markup = "<button type=\"submit\">Save Controls</button>" if can_manage else ""
    mobile_mode = str(controls["mobile_trading_mode"])
    kill_switch_value = "on" if controls["live_order_kill_switch"] else "off"
    engine_mode = str(controls["engine_mode"])
    system_status = _system_status(user_ctx)
    broker_gate = str(system_status["broker_live_gate"])
    kill_switch_state = "ENGAGED" if system_status["live_order_kill_switch"] else "CLEAR"
    return _page(
        "System Controls",
        f"""
        <main class="dashboard-shell">
          {_header("System Controls", user_ctx, "controls")}
          {_identity_strip(user_ctx, "Control Authority" if can_manage else "View Only")}
          {_status_markup(message, status)}

          <section class="form-panel trade-form-panel" aria-label="Mobile runtime controls">
            <h2>Runtime Controls</h2>
            <p class="muted">Mode and order state apply to all mobile trade tickets for authenticated users.</p>
            <form method="post" action="/controls" autocomplete="off">
              <label for="mobile_trading_mode">Mobile Trading Mode</label>
              <select id="mobile_trading_mode" name="mobile_trading_mode"{disabled}>
                <option value="MOBILE_READ_ONLY"{_selected("MOBILE_READ_ONLY", mobile_mode)}>READ ONLY</option>
                <option value="MOBILE_PAPER_TRADING"{_selected("MOBILE_PAPER_TRADING", mobile_mode)}>PAPER TRADING</option>
                <option value="MOBILE_LIVE_TRADING_ARMED"{_selected("MOBILE_LIVE_TRADING_ARMED", mobile_mode)}>LIVE TRADING ARMED</option>
              </select>

              <div id="live-warning-modal" style="display:none; border:2px solid red; padding: 10px; margin: 10px 0; background: #ffebee; color: #b71c1c;">
                <strong>LIVE CAPITAL WARNING: Real capital may be lost. Orders executed in LIVE mode may result in financial loss.</strong>
                <label style="display:block; margin-top:10px;"><input type="checkbox" id="legal_acceptance" name="legal_acceptance" value="on"> I explicitly acknowledge and accept these risks.</label>
              </div>
              <script>
                document.getElementById('mobile_trading_mode').addEventListener('change', function() {{
                  document.getElementById('live-warning-modal').style.display = this.value === 'MOBILE_LIVE_TRADING_ARMED' ? 'block' : 'none';
                }});
                if(document.getElementById('mobile_trading_mode').value === 'MOBILE_LIVE_TRADING_ARMED') {{
                  document.getElementById('live-warning-modal').style.display = 'block';
                }}
              </script>

              <label for="live_order_kill_switch">Live Order Kill Switch</label>
              <select id="live_order_kill_switch" name="live_order_kill_switch"{disabled}>
                <option value="off"{_selected("off", kill_switch_value)}>Clear</option>
                <option value="on"{_selected("on", kill_switch_value)}>Engaged</option>
              </select>

              <label for="engine_mode">Engine Mode</label>
              <select id="engine_mode" name="engine_mode"{disabled}>
                {_engine_mode_options(engine_mode)}
              </select>

              {submit_markup}
            </form>
          </section>

          <section class="metric-grid" aria-label="Control guardrails">
            <article><strong>Live Broker Gate</strong><span>{html.escape(broker_gate)}</span></article>
            <article><strong>Kill Switch</strong><span>{html.escape(kill_switch_state)}</span></article>
            <article><strong>Live Confirmation</strong><span>Required</span></article>
            <article><strong>User Gate</strong><span>{'Manage' if can_manage else 'View'}</span></article>
            <article><strong>Audit</strong><span>On</span></article>
          </section>
        </main>
        """,
    )


def _engine_mode_options(current: str) -> str:
    return "\n".join(
        f'<option value="{html.escape(mode)}"{_selected(mode, current)}>{html.escape(mode)}</option>'
        for mode in ENGINE_MODES
    )


def _users_page(
    user_ctx: Dict[str, Any],
    message: str = "",
    status: str = "info",
) -> str:
    users = load_users()
    rows = "\n".join(_user_row_markup(summary) for summary in list_user_summaries(users))
    role_options = "\n".join(
        f'<option value="{html.escape(role)}"{_selected(role, "VIEWER")}>{html.escape(role)}</option>'
        for role in available_roles()
    )
    return _page(
        "Users",
        f"""
        <main class="dashboard-shell">
          {_header("Users", user_ctx, "users")}
          {_identity_strip(user_ctx, "SUPER_USER Administration")}
          {_status_markup(message, status)}

          <section class="data-panel" aria-label="CSS users">
            <h2>CSS Users</h2>
            <div class="user-table" role="table" aria-label="Current CSS users">
              <div class="user-row user-head" role="row">
                <span>User ID</span><span>Name</span><span>Role</span><span>Unit</span><span>Status</span>
              </div>
              {rows}
            </div>
          </section>

          <section class="form-panel trade-form-panel" aria-label="Create CSS user form">
            <h2>Create User</h2>
            <p class="muted">New users sign on with their assigned user ID, then change the initial password.</p>
            <form method="post" action="/users" autocomplete="off">
              <label for="user_id">User ID</label>
              <input id="user_id" name="user_id" inputmode="numeric" pattern="[0-9]*" required>

              <label for="display_name">Display Name</label>
              <input id="display_name" name="display_name" required>

              <label for="role">Role</label>
              <select id="role" name="role">{role_options}</select>

              <label for="initial_password">Initial Password</label>
              <input id="initial_password" name="initial_password" type="password" required>

              <label for="unit_code">Unit Code</label>
              <input id="unit_code" name="unit_code" value="CORE" required>

              <label for="home_branch">Home Branch</label>
              <input id="home_branch" name="home_branch" value="HQ" required>

              <label class="checkbox-row">
                <input name="must_change_password" type="checkbox"{_checked(True)}>
                <span>Require password change at first sign-on</span>
              </label>

              <button type="submit">Create User</button>
            </form>
          </section>
        </main>
        """,
    )


def _recent_tickets_panel(limit: int = 5) -> str:
    events = _recent_mobile_events(limit)
    if not events:
        rows = '<div class="ticket-row"><span>No mobile tickets yet.</span></div>'
    else:
        rows = "\n".join(_ticket_row_markup(event) for event in events)

    return f"""
      <section class="data-panel" aria-label="Recent mobile tickets">
        <h2>Recent Mobile Tickets</h2>
        <div class="ticket-table">
          {rows}
        </div>
      </section>
    """


def _recent_mobile_events(limit: int = 5) -> tuple[Dict[str, Any], ...]:
    try:
        lines = MOBILE_EVENTS_FILE.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return ()
    except Exception:
        return ()

    events = []
    for line in reversed(lines):
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            events.append(item)
        if len(events) >= limit:
            break
    return tuple(events)


def _ticket_row_markup(event: Dict[str, Any]) -> str:
    ticket = event.get("ticket") if isinstance(event.get("ticket"), dict) else {}
    status = str(event.get("status", "UNKNOWN"))
    ok = bool(event.get("ok", False))
    css_class = "ok" if ok else "blocked"
    ticket_id = str(ticket.get("ticket_id", ""))[:8] or "N/A"
    mode = str(ticket.get("mode", "")).upper() or "N/A"
    broker = str(ticket.get("broker", "")) or "N/A"
    symbol = str(ticket.get("symbol", "")) or "N/A"
    side = str(ticket.get("side", "")) or "N/A"
    amount = ticket.get("amount", "")
    return f"""
      <div class="ticket-row {css_class}">
        <span>{html.escape(status)}</span>
        <span>{html.escape(mode)}</span>
        <span>{html.escape(broker)}</span>
        <span>{html.escape(symbol)}</span>
        <span>{html.escape(side)} {html.escape(str(amount))}</span>
        <span>{html.escape(ticket_id)}</span>
      </div>
    """


def _position_row_markup(position: Dict[str, Any]) -> str:
    return f"""
      <div class="ops-row">
        <span>{html.escape(str(position.get("symbol", "N/A")))}</span>
        <span>{html.escape(str(position.get("asset_class", "N/A")))}</span>
        <span>{html.escape(str(position.get("side", "N/A")))}</span>
        <span>{_number(position.get("qty"), 4)}</span>
        <span>{_number(position.get("entry_price"), 4)}</span>
        <span>{_number(position.get("current_price"), 4)}</span>
        <span>{_money(position.get("unrealized_pnl"))}</span>
      </div>
    """


def _history_row_markup(event: Dict[str, Any]) -> str:
    ticket = event.get("ticket") if isinstance(event.get("ticket"), dict) else {}
    return f"""
      <div class="ops-row">
        <span>{html.escape(str(event.get("recorded_utc", "N/A")))}</span>
        <span>{html.escape(str(event.get("status", "UNKNOWN")))}</span>
        <span>{html.escape(str(ticket.get("mode", "N/A")).upper())}</span>
        <span>{html.escape(str(ticket.get("broker", "N/A")))}</span>
        <span>{html.escape(str(ticket.get("symbol", "N/A")))}</span>
        <span>{html.escape(str(ticket.get("side", "N/A")))}</span>
        <span>{_money(ticket.get("amount"))}</span>
      </div>
    """


def _audit_row_markup(event: Any) -> str:
    css_class = "ok" if event.category in {"approval", "execution_attempt"} else "blocked"
    return f"""
      <div class="ops-row {css_class}">
        <span>{html.escape(str(event.timestamp_utc))}</span>
        <span>{html.escape(str(event.category).replace("_", " ").title())}</span>
        <span>{html.escape(str(event.status))}</span>
        <span>{html.escape(str(event.actor))}</span>
        <span>{html.escape(str(event.source))}</span>
        <span>{html.escape(str(event.reason))}</span>
        <span>{'YES' if event.replayable else 'NO'}</span>
      </div>
    """


def _opportunity_rows(
    user_ctx: Dict[str, Any],
    session: Dict[str, Any],
) -> tuple[Dict[str, Any], ...]:
    payloads = _mobile_runtime_payloads(user_ctx, session)
    market = payloads["market_payload"]
    positions = payloads["positions_payload"].get("positions", [])
    rows = [
        {
            "symbol": position.get("symbol", "N/A"),
            "asset_class": position.get("asset_class", "N/A"),
            "bias": position.get("side", "N/A"),
            "state": market.get("signal_confluence_state", "UNKNOWN"),
            "action": "Monitor open exposure",
        }
        for position in positions
        if isinstance(position, dict)
    ]
    rows.append(
        {
            "symbol": "CL",
            "asset_class": "FUTURES",
            "bias": "WATCH",
            "state": market.get("execution_cost_state", "UNKNOWN"),
            "action": "Await governed ticket",
        }
    )
    return tuple(rows)


def _opportunity_row_markup(item: Dict[str, Any]) -> str:
    return f"""
      <div class="ops-row">
        <span>{html.escape(str(item.get("symbol", "N/A")))}</span>
        <span>{html.escape(str(item.get("asset_class", "N/A")))}</span>
        <span>{html.escape(str(item.get("bias", "N/A")))}</span>
        <span>{html.escape(str(item.get("state", "UNKNOWN")))}</span>
        <span>{html.escape(str(item.get("action", "")))}</span>
      </div>
    """


def _kv(label: str, value: Any) -> str:
    return f"""
      <div>
        <strong>{html.escape(label)}</strong>
        <span>{html.escape(str(value if value not in (None, "") else "UNKNOWN"))}</span>
      </div>
    """


def _mapping(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _money(value: Any) -> str:
    return f"{_safe_float(value):,.2f}"


def _number(value: Any, precision: int = 2) -> str:
    return f"{_safe_float(value):,.{precision}f}"


def _percent(value: Any) -> str:
    return f"{_safe_float(value):,.2f}%"


def _yes_no(value: Any) -> str:
    return "YES" if bool(value) else "NO"


def _coinbase_credentials_present() -> bool:
    api_key, api_secret, _source = _load_coinbase_credentials()
    return bool(api_key and api_secret)


def _oanda_credentials_present() -> bool:
    return bool(
        (os.getenv("OANDA_API_KEY") or os.getenv("OANDA_API_TOKEN"))
        and (os.getenv("OANDA_ACCOUNT_ID") or os.getenv("OANDA_PRACTICE_ACCOUNT_ID"))
    )


def _user_row_markup(summary: Dict[str, Any]) -> str:
    locked = "Locked" if summary.get("locked") else "Active"
    password = "Password Change" if summary.get("must_change_password") else "Current"
    safe_user_id = html.escape(str(summary.get("user_id", "")))
    safe_name = html.escape(str(summary.get("display_name", "")))
    safe_role = html.escape(str(summary.get("role", "")))
    safe_unit = html.escape(str(summary.get("unit_code", "")))
    return f"""
      <div class="user-row" role="row">
        <span>{safe_user_id}</span>
        <span>{safe_name}</span>
        <span>{safe_role}</span>
        <span>{safe_unit}</span>
        <span>{locked} / {password}</span>
      </div>
    """


def _access_denied_page(user_ctx: Dict[str, Any], message: str) -> str:
    return _page(
        "Access Denied",
        f"""
        <main class="dashboard-shell">
          {_header("Access Denied", user_ctx, "access")}
          {_identity_strip(user_ctx, "Authority Restricted")}
          {_status_markup(message, "error")}
        </main>
        """,
    )


def _trade_readiness_panel(user_ctx: Dict[str, Any]) -> str:
    status = _system_status(user_ctx)
    messages = []
    kind = "success"

    if not status["can_trade"]:
        kind = "error"
        messages.append("Your CSS role can view this screen but cannot submit trade tickets.")

    if not status["orders_enabled"]:
        kind = "error"
        messages.append("Mobile order submission is disabled in CSS Controls.")

    if status["system_live"] and not status["broker_live_ready"]:
        kind = "error"
        messages.append(
            "System mode is LIVE, but the broker live gate is OFF. Coinbase requires COINBASE_ENABLE_LIVE_ORDERS=true; OANDA requires valid token and account settings."
        )

    if not status["system_live"]:
        kind = "info" if kind == "success" else kind
        messages.append("System mode is PAPER. Tickets will be recorded to the CSS paper ledger, not sent to a broker.")

    if not messages:
        messages.append("Live trade path is armed. A live ticket still requires the confirmation word EXECUTE.")

    body = " ".join(messages)
    return f'<section class="status {kind}"><strong>Trade Activation Status</strong><p>{html.escape(body)}</p></section>'


def _trade_result_markup(result: Dict[str, Any], status: str) -> str:
    safe_status = "success" if status == "success" else "error"
    code = str(result.get("status", "RESULT"))
    headline = _trade_status_headline(code)
    return (
        f'<section class="status trade-result {safe_status}">'
        f"<strong>{html.escape(headline)}</strong>"
        f"<p>{html.escape(_trade_status_detail(result))}</p>"
        f"<pre>{html.escape(json.dumps(_redact_result(result), indent=2))}</pre>"
        "</section>"
    )


def _trade_status_headline(code: str) -> str:
    labels = {
        "PAPER_TICKET_RECORDED": "Paper ticket recorded",
        "LIVE_CONFIRMATION_REQUIRED": "Live confirmation required",
        "GLOBAL_LIVE_ORDER_KILL_SWITCH_ENGAGED": "Live order kill switch engaged",
        "MOBILE_ORDERS_DISABLED": "Mobile orders are disabled",
        "MOBILE_AUTHORITY_DENIED": "Trading authority denied",
        "COINBASE_LIVE_ORDERS_FLAG_OFF": "Coinbase live orders are not enabled",
        "COINBASE_ORDER_SENT": "Coinbase order sent",
        "COINBASE_ORDER_FAILED": "Coinbase order failed",
        "COINBASE_ORDER_SIZE_BLOCKED": "Coinbase order size blocked",
        "COINBASE_NOT_CONFIGURED": "Coinbase credentials not configured",
        "OANDA_ORDER_SENT": "OANDA order sent",
        "OANDA_ORDER_FAILED": "OANDA order failed",
        "OANDA_NOT_CONFIGURED": "OANDA credentials not configured",
        "LIVE_BROKER_NOT_SUPPORTED": "Live broker not supported for this ticket",
    }
    return labels.get(code, code.replace("_", " ").title())


def _trade_status_detail(result: Dict[str, Any]) -> str:
    code = str(result.get("status", ""))
    if code == "PAPER_TICKET_RECORDED":
        return "The ticket was saved in CSS paper mode. No live broker order was sent."
    if code == "LIVE_CONFIRMATION_REQUIRED":
        return "Type MOBILE LIVE in the confirmation field and submit again while system mode is LIVE."
    if code == "GLOBAL_LIVE_ORDER_KILL_SWITCH_ENGAGED":
        return "The global live-order kill switch is engaged. Clear it from Controls before any live order can leave CSS."
    if code == "COINBASE_LIVE_ORDERS_FLAG_OFF":
        return "The Coinbase credential check may pass, but live orders remain blocked until the live-order flag is enabled in CSS environment controls."
    if code == "MOBILE_ORDERS_DISABLED":
        return "Open Controls as a super user and set Orders to Enabled."
    if code == "MOBILE_AUTHORITY_DENIED":
        return "Ask a super user to assign a trading role such as TRADER, TREASURY, HEAD_TREASURY, ADMIN, or SUPER_USER."
    if bool(result.get("ok")):
        return "CSS accepted the ticket and recorded the outcome below."
    return "CSS blocked the ticket. The detail below shows the governing reason."


def _trade_ticket_page(
    user_ctx: Dict[str, Any],
    result: Optional[Dict[str, Any]] = None,
    status: str = "info",
) -> str:
    result_markup = ""
    if result:
        result_markup = _trade_result_markup(result, status)

    controls = load_mobile_controls()
    system_mode = str(controls.get("mobile_trading_mode", "MOBILE_READ_ONLY"))
    orders_enabled = system_mode != "MOBILE_READ_ONLY"
    trade_allowed = _can_submit_trade(user_ctx)
    live_flag = "READY" if system_mode == "MOBILE_LIVE_TRADING_ARMED" else "OFF"
    if trade_allowed:
        trade_form_markup = f"""
          <section class="form-panel trade-form-panel" aria-label="Mobile trade ticket form">
            <h2>Submit Trade Ticket</h2>
            <p class="muted">Tickets use the current mobile system mode. Live tickets require broker credentials, CSS live flags, and confirmation.</p>
            <form method="post" action="/trade" autocomplete="off">
              <label for="mode_display">Mobile Mode</label>
              <input id="mode_display" value="{html.escape(system_mode.upper())}" disabled>
              <input name="mode" type="hidden" value="{html.escape(system_mode)}">

              <label for="broker">Broker</label>
              <select id="broker" name="broker">
                <option value="CSS_PAPER">CSS Paper</option>
                <option value="OANDA">OANDA</option>
                <option value="COINBASE">Coinbase</option>
              </select>

              <label for="asset_class">Asset Class</label>
              <select id="asset_class" name="asset_class">
                <option value="CRYPTO">Crypto</option>
                <option value="FX">FX</option>
                <option value="OPTIONS">Options</option>
                <option value="FUTURES">Futures</option>
              </select>

              <label for="symbol">Symbol</label>
              <input id="symbol" name="symbol" value="BTC-USD" required>

              <label for="side">Side</label>
              <select id="side" name="side">
                <option value="BUY">Buy</option>
                <option value="SELL">Sell</option>
              </select>

              <label for="amount">USD Amount / Notional</label>
              <input id="amount" name="amount" inputmode="decimal" value="1.00" required>

              <label for="qty">Quantity / Units</label>
              <input id="qty" name="qty" inputmode="decimal" value="1">

              <label for="confirm">Live Confirmation</label>
              <input id="confirm" name="confirm" placeholder="Type MOBILE LIVE for live orders">

              <button type="submit">Submit Ticket</button>
            </form>
          </section>
        """
    else:
        trade_form_markup = (
            '<section class="status error">'
            "<strong>Trading authority required.</strong>"
            "<p>Your current CSS role can view the system but cannot submit trade tickets.</p>"
            "</section>"
        )

    return _page(
        "Trade Ticket",
        f"""
        <main class="dashboard-shell">
          {_header("Trade Ticket", user_ctx, "trade")}
          {_identity_strip(user_ctx, f"Broker Gate {live_flag}")}

          {_trade_readiness_panel(user_ctx)}

          <section class="metric-grid" aria-label="Trade controls">
            <article><strong>Ticket Mode</strong><span>{html.escape(system_mode.title())}</span></article>
            <article><strong>Orders</strong><span>{'Enabled' if orders_enabled else 'Disabled'}</span></article>
            <article><strong>Authority</strong><span>{'Submit' if trade_allowed else 'View'}</span></article>
            <article><strong>Live Confirm</strong><span>EXECUTE</span></article>
          </section>

          {result_markup}

          {trade_form_markup}

          {_recent_tickets_panel()}
        </main>
        """,
    )


def execute_mobile_trade_ticket(user_ctx: Dict[str, Any], form: Dict[str, str]) -> Dict[str, Any]:
    load_local_env()

    controls = load_mobile_controls()
    ticket = _build_mobile_ticket(user_ctx, form, controls=controls)
    broker = ticket["broker"]
    mobile_mode = controls["mobile_trading_mode"]

    _record_mobile_event({
        "event_type": "mobile_order_requested",
        "ticket": ticket,
    })

    if not _can_submit_trade(user_ctx):
        result = {
            "ok": False,
            "status": "MOBILE_AUTHORITY_DENIED",
            "ticket": ticket,
            "broker_response": {
                "role": str(user_ctx.get("role", "")),
                "required": "submit_trade or place_trade",
            },
        }
        _record_mobile_event({"event_type": "mobile_order_rejected", **result})
        return result

    if mobile_mode == "MOBILE_READ_ONLY":
        result = {
            "ok": False,
            "status": "MOBILE_ORDERS_DISABLED",
            "ticket": ticket,
            "broker_response": {
                "mobile_orders_enabled": False,
                "required_control": "orders_enabled",
            },
        }
        _record_mobile_event({"event_type": "mobile_order_rejected", **result})
        return result

    is_live_request = mobile_mode == "MOBILE_LIVE_TRADING_ARMED" and broker != "CSS_PAPER"

    if is_live_request:
        kill_switch = evaluate_live_order_kill_switch(controls)
        if kill_switch.blocked:
            result = {
                "ok": False,
                "status": "GLOBAL_LIVE_ORDER_KILL_SWITCH_ENGAGED",
                "ticket": ticket,
                "broker_response": {
                    "live_order_sent": False,
                    "kill_switch_source": kill_switch.source,
                    "kill_switch_reason": kill_switch.reason,
                },
            }
            _record_mobile_event({"event_type": "mobile_order_rejected", **result})
            return result
    
    if is_live_request:
        if str(user_ctx.get("role", "")).upper() != "SUPER_USER":
            result = {
                "ok": False,
                "status": "MOBILE_LIVE_REQUIRES_SUPER_USER",
                "ticket": ticket,
                "broker_response": None,
            }
            _record_mobile_event({"event_type": "mobile_order_rejected", **result})
            return result

        if str(form.get("confirm", "")).strip().upper() != "MOBILE LIVE":
            result = {
                "ok": False,
                "status": "LIVE_CONFIRMATION_REQUIRED",
                "ticket": ticket,
                "broker_response": {
                    "required_confirmation": "MOBILE LIVE",
                    "confirmation_received": bool(str(form.get("confirm", "")).strip()),
                },
            }
            _record_mobile_event({"event_type": "mobile_order_rejected", **result})
            return result

    # --- CANONICAL PIPELINE EXECUTION ---
    try:
        from backend.intelligence.trade_decision_orchestrator import TradeDecisionOrchestrator
        from engine.execution.execution_gate import ExecutionGate
        from backend.app.persistence.services.trade_runtime_service import TradeRuntimeService
    except ImportError as e:
        result = {
            "ok": False,
            "status": "CANONICAL_PIPELINE_UNAVAILABLE",
            "ticket": ticket,
            "broker_response": {"error": str(e)},
        }
        _record_mobile_event({"event_type": "mobile_order_rejected", **result})
        return result

    orchestrator = TradeDecisionOrchestrator(
        mode="live" if is_live_request else "paper",
        broker_name=broker.lower(),
        broker_mode="live" if is_live_request else "paper",
    )
    
    # 1. Canonical Session and Equity
    session_svc = SessionRuntimeService()
    active_sessions = session_svc.get_active_sessions()
    if not active_sessions:
        result = {"ok": False, "status": "NO_ACTIVE_SESSION", "ticket": ticket, "broker_response": {"error": "No active session"}}
        _record_mobile_event({"event_type": "mobile_order_rejected", **result})
        return result
        
    session_id = active_sessions[0]["session_id"]
    pnl_svc = PnlRuntimeService()
    pnl_snapshot = pnl_svc.get_latest_snapshot(session_id)
    if not pnl_snapshot:
        result = {"ok": False, "status": "MISSING_PNL_SNAPSHOT", "ticket": ticket, "broker_response": {"error": "Canonical PnL snapshot unavailable"}}
        _record_mobile_event({"event_type": "mobile_order_rejected", **result})
        return result
        
    equity = float(pnl_snapshot.get("equity", 0.0))
    equity_peak = float(pnl_snapshot.get("equity_peak", 0.0))

    # 2. Canonical Margin Snapshot
    margin_snapshot = None
    broker_mode_str = "LIVE" if is_live_request else "SIMULATED"
    try:
        if broker == "OANDA":
            from engine.risk.oanda_margin_adapter import OandaMarginAdapter
            margin_adapter = OandaMarginAdapter(mode=broker_mode_str)
            margin_snapshot = margin_adapter.get_margin_snapshot()
        elif broker == "COINBASE":
            from engine.risk.coinbase_margin_adapter import CoinbaseMarginAdapter
            margin_adapter = CoinbaseMarginAdapter(mode=broker_mode_str)
            margin_snapshot = margin_adapter.get_margin_snapshot()
    except Exception:
        pass
        
    if not margin_snapshot:
        if not is_live_request:
            from engine.risk.margin_state import MarginState
            class PaperFallbackMarginSnapshot:
                def __init__(self):
                    self.margin_source = "SIMULATED"
                    self.broker_mode = "PAPER"
                    self.margin_state = MarginState.NORMAL
                    self.available_margin = 10000.00
                    self.required_margin = 0.00
                    self.utilization_pct = 0.00
                    self.trade_gate_allowed = True
                    self.reason = "PAPER_SIMULATED_MARGIN_FALLBACK"
                    self.buying_power = 10000.00
                    self.margin_ratio = 0.00
                    self.broker_name = broker
            margin_snapshot = PaperFallbackMarginSnapshot()
            _record_mobile_event({
                "event_type": "mobile_margin_fallback",
                "reason": "PAPER_SIMULATED_MARGIN_FALLBACK",
                "margin_source": "SIMULATED"
            })
        else:
            result = {"ok": False, "status": "MARGIN_SNAPSHOT_UNAVAILABLE", "ticket": ticket, "broker_response": {"error": "Failed to retrieve canonical margin state"}}
            _record_mobile_event({"event_type": "mobile_order_rejected", **result})
            return result

    # 3. Canonical Market Data
    # Fail closed if authoritative values are unavailable (no synthetic values)
    market_data = {
        "symbol": ticket["symbol"],
        "asset_class": ticket["asset_class"],
        "expected_value": None,
        "cost": None,
        "probability": None,
        "engine_mode": ticket["engine_mode"]
    }
    
    orchestrator_decision = orchestrator.evaluate_trade(market_data)
    
    if not orchestrator_decision.get("filters", {}).get("governance_approved", False):
        result = {
            "ok": False,
            "status": "ORCHESTRATOR_GATE_REJECTED",
            "ticket": ticket,
            "broker_response": {"reason": orchestrator_decision.get("filters", {}).get("governance_reason")}
        }
        _record_mobile_event({"event_type": "mobile_order_rejected", **result})
        return result

    exec_gate = ExecutionGate()
    gate_decision = exec_gate.evaluate_trade(
        instrument=ticket["symbol"],
        side=ticket["side"],
        notional=ticket["amount"],
        stop_distance_pct=0.02,
        equity=equity,
        equity_peak=equity_peak,
        regime_persistence=None,
        policy="core",
        volatility_state=None,
        regime_state=None,
        expected_move_bps=None,
        fee_bps=None,
        spread_bps=None,
        slippage_bps=None,
        margin_snapshot=margin_snapshot,
        broker_mode="live" if is_live_request else "paper"
    )

    if gate_decision.get("decision", {}).get("final") != "ALLOW":
        result = {
            "ok": False,
            "status": "EXECUTION_GATE_REJECTED",
            "ticket": ticket,
            "broker_response": {"reason": gate_decision.get("reason")}
        }
        _record_mobile_event({"event_type": "mobile_order_rejected", **result})
        return result

    # Persist via TradeRuntimeService
    try:
        from decimal import Decimal
        trade_service = TradeRuntimeService()
        trade_service.open_trade(
            trade_id=ticket["ticket_id"],
            session_id=orchestrator.session_id,
            broker_name=broker.lower(),
            broker_mode="live" if is_live_request else "paper",
            symbol=ticket["symbol"],
            direction=ticket["side"].lower(),
            order_type="market",
            quantity=Decimal(str(ticket["qty"])),
            filled_quantity=Decimal(str(ticket["qty"])),
            entry_price=Decimal("0.0"),
            raw_payload_json=json.dumps(ticket)
        )
    except Exception as e:
        result = {
            "ok": False,
            "status": "LEDGER_PERSISTENCE_FAILED",
            "ticket": ticket,
            "broker_response": {"error": str(e)}
        }
        _record_mobile_event({"event_type": "mobile_order_rejected", **result})
        return result

    result = {
        "ok": True,
        "status": "MOBILE_ORDER_APPROVED",
        "ticket": ticket,
        "broker_response": {
            "live_order_sent": is_live_request,
            "governance_decision": orchestrator_decision,
            "execution_gate_decision": gate_decision
        },
    }
    _record_mobile_event({"event_type": "mobile_order_approved", **result})
    return result

def _build_mobile_ticket(
    user_ctx: Dict[str, Any],
    form: Dict[str, str],
    controls: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    active_controls = controls if controls is not None else load_mobile_controls()
    mode = str(active_controls.get("runtime_mode", form.get("mode", "paper"))).strip().lower()
    if mode not in {"paper", "live"}:
        mode = "paper"

    broker = str(form.get("broker", "CSS_PAPER")).strip().upper()
    asset_class = str(form.get("asset_class", "CRYPTO")).strip().upper()
    symbol = str(form.get("symbol", "")).strip().upper()
    side = str(form.get("side", "BUY")).strip().upper()
    if side not in {"BUY", "SELL"}:
        side = "BUY"

    amount = _safe_float(form.get("amount"), 0.0)
    qty = _safe_float(form.get("qty"), 0.0)

    return {
        "ticket_id": secrets.token_hex(8).upper(),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "user_id": str(user_ctx.get("user_id", "")),
        "display_name": str(user_ctx.get("display_name", "")),
        "role": str(user_ctx.get("role", "")),
        "mode": mode,
        "broker": broker,
        "asset_class": asset_class,
        "symbol": symbol,
        "side": side,
        "amount": amount,
        "qty": qty,
        "engine_mode": str(active_controls.get("engine_mode", "SAFE")),
        "orders_enabled": bool(active_controls.get("orders_enabled", True)),
        "source": "CSS_MOBILE",
    }


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def _record_mobile_event(payload: Dict[str, Any]) -> None:
    MOBILE_EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    with MOBILE_EVENTS_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")


def _redact_result(result: Dict[str, Any]) -> Dict[str, Any]:
    redacted = json.loads(json.dumps(result, default=str))
    broker_response = redacted.get("broker_response")
    if isinstance(broker_response, dict):
        for key in list(broker_response):
            if "key" in key.lower() or "token" in key.lower() or "secret" in key.lower():
                broker_response[key] = "REDACTED"
    return redacted


def _status_markup(message: str, status: str) -> str:
    if not message:
        return ""
    safe_message = html.escape(message)
    safe_status = "error" if status == "error" else "info"
    return f'<p class="status {safe_status}">{safe_message}</p>'


def _page(title: str, body: str) -> str:
    safe_title = html.escape(title)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="#10202a">
  <title>CSS - {safe_title}</title>
  <link rel="manifest" href="/manifest.webmanifest">
  <style>{_css()}</style>
</head>
<body>
  {body}
  <script>
    if ("serviceWorker" in navigator) {{
      navigator.serviceWorker.register("/service-worker.js").catch(() => undefined);
    }}
  </script>
</body>
</html>"""


def _css() -> str:
    return """
:root {
  color-scheme: light;
  --ink: #0f1720;
  --muted: #60717a;
  --bg: #f4f7f8;
  --panel: #ffffff;
  --left: #10202a;
  --line: #d8e2e6;
  --teal: #1d8a8a;
  --teal-dark: #146767;
  --amber: #c9861a;
  --danger: #b42318;
  --success: #166534;
  --field: #eef4f5;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--ink);
  font-family: "Segoe UI", Arial, sans-serif;
}
.auth-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(280px, 0.85fr) minmax(320px, 1.15fr);
}
.auth-shell.single {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}
.brand-panel {
  background: var(--left);
  color: white;
  padding: 44px 34px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.brand-mark svg {
  width: 152px;
  max-width: 42vw;
  margin-bottom: 24px;
}
.brand-mark circle:first-child {
  fill: none;
  stroke: var(--teal);
  stroke-width: 5;
}
.brand-mark path {
  fill: none;
  stroke: #e8fbfb;
  stroke-width: 7;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.brand-mark text {
  fill: #fff;
  font-size: 24px;
  font-weight: 700;
  text-anchor: middle;
  font-family: "Segoe UI", Arial, sans-serif;
}
h1, h2, p { margin-top: 0; }
h1 { font-size: 34px; line-height: 1.05; margin-bottom: 14px; }
h2 { font-size: 28px; margin-bottom: 8px; }
.brand-panel p, .muted { color: var(--muted); }
.brand-panel p { color: #b7c7cc; }
.policy-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 24px;
}
.policy-row span {
  background: rgba(255,255,255,0.09);
  color: #e8fbfb;
  padding: 8px 10px;
  font-size: 12px;
  border: 1px solid rgba(255,255,255,0.16);
}
.form-panel {
  background: var(--panel);
  padding: 44px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.auth-shell.single .form-panel {
  width: min(100%, 520px);
  border: 1px solid var(--line);
}
form {
  display: grid;
  gap: 12px;
  margin-top: 24px;
}
label {
  color: var(--ink);
  font-size: 13px;
  font-weight: 700;
}
input {
  width: 100%;
  border: 1px solid var(--line);
  background: var(--field);
  color: var(--ink);
  font-size: 17px;
  padding: 14px 13px;
  border-radius: 0;
}
input[type="checkbox"] {
  width: auto;
  min-width: 18px;
  min-height: 18px;
  padding: 0;
}
input:disabled,
select:disabled {
  color: var(--muted);
  background: #f6f9fa;
}
select {
  width: 100%;
  border: 1px solid var(--line);
  background: var(--field);
  color: var(--ink);
  font-size: 17px;
  padding: 14px 13px;
  border-radius: 0;
}
input:focus {
  outline: 2px solid var(--teal);
  outline-offset: 1px;
}
select:focus {
  outline: 2px solid var(--teal);
  outline-offset: 1px;
}
button {
  border: 0;
  background: var(--teal);
  color: #fff;
  min-height: 48px;
  padding: 12px 18px;
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
}
a.button-link {
  display: inline-flex;
  min-height: 40px;
  align-items: center;
  justify-content: center;
  padding: 10px 16px;
  background: var(--teal);
  color: #fff;
  text-decoration: none;
  font-size: 15px;
  font-weight: 700;
}
a.button-link.quiet {
  background: #e7eef1;
  color: var(--ink);
}
button:active { background: var(--teal-dark); }
button.ghost {
  min-height: 40px;
  background: #e7eef1;
  color: var(--ink);
}
.status {
  padding: 12px 14px;
  border: 1px solid var(--line);
  margin: 18px 0 0;
}
.status.error {
  color: var(--danger);
  border-color: #f0b8b4;
  background: #fff1f0;
}
.status.info {
  color: #24515c;
  border-color: #b9d9df;
  background: #eef8fa;
}
.status p {
  margin: 8px 0 0;
}
.trade-result {
  margin-bottom: 14px;
}
.dashboard-shell {
  width: min(1120px, 100%);
  margin: 0 auto;
  padding: 20px;
}
.mobile-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 0;
}
.top-actions {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}
.top-actions form {
  margin: 0;
  display: block;
}
.eyebrow {
  margin-bottom: 3px;
  color: var(--muted);
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0;
}
.identity-strip {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  border: 1px solid var(--line);
  background: var(--panel);
  padding: 10px;
  margin-bottom: 14px;
}
.identity-strip span {
  padding: 8px 10px;
  background: var(--field);
  font-size: 13px;
  font-weight: 700;
}
.system-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  border: 1px solid var(--line);
  background: #edf6f7;
  padding: 10px;
  margin-bottom: 14px;
}
.system-strip span {
  padding: 7px 9px;
  background: #ffffff;
  color: var(--ink);
  font-size: 12px;
  font-weight: 700;
}
.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 14px;
}
.metric-grid article {
  background: var(--panel);
  border: 1px solid var(--line);
  padding: 14px;
}
.metric-grid strong {
  display: block;
  color: var(--muted);
  font-size: 12px;
  margin-bottom: 6px;
}
.metric-grid span {
  font-size: 18px;
  font-weight: 700;
}
.account-grid span {
  font-variant-numeric: tabular-nums;
}
.command-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}
.command-card {
  display: block;
  min-height: 94px;
  border: 1px solid var(--line);
  background: #f8fbfc;
  color: var(--ink);
  padding: 14px;
  text-decoration: none;
}
.command-card strong,
.command-card span {
  display: block;
}
.command-card strong {
  margin-bottom: 8px;
  font-size: 15px;
}
.command-card span {
  color: var(--muted);
  font-size: 13px;
  line-height: 1.35;
}
.terminal-panel {
  background: #0f1720;
  color: #e8fbfb;
  border: 1px solid #23323d;
  overflow: auto;
}
.trade-form-panel {
  border: 1px solid var(--line);
  margin-bottom: 14px;
}
.trade-form-panel form {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.trade-form-panel button {
  grid-column: 1 / -1;
}
.checkbox-row {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 600;
}
.data-panel {
  background: var(--panel);
  border: 1px solid var(--line);
  padding: 18px;
  margin-bottom: 14px;
}
.user-table {
  display: grid;
  gap: 0;
  border: 1px solid var(--line);
  overflow-x: auto;
}
.user-row {
  display: grid;
  grid-template-columns: 110px minmax(160px, 1fr) 160px 110px 150px;
  min-width: 690px;
  border-bottom: 1px solid var(--line);
}
.user-row:last-child {
  border-bottom: 0;
}
.user-row span {
  padding: 11px 10px;
  font-size: 13px;
}
.user-head {
  background: var(--field);
  font-weight: 700;
}
.ticket-table {
  display: grid;
  gap: 8px;
}
.ticket-row {
  display: grid;
  grid-template-columns: minmax(150px, 1.4fr) 80px 110px minmax(110px, 1fr) minmax(90px, 1fr) 90px;
  gap: 8px;
  border: 1px solid var(--line);
  padding: 10px;
  background: #fff;
}
.ticket-row span {
  font-size: 12px;
  font-weight: 700;
  overflow-wrap: anywhere;
}
.ticket-row.ok {
  border-left: 5px solid var(--success);
}
.ticket-row.blocked {
  border-left: 5px solid var(--danger);
}
.ops-table {
  display: grid;
  gap: 8px;
  overflow-x: auto;
}
.ops-row {
  display: grid;
  grid-template-columns: repeat(5, minmax(110px, 1fr));
  min-width: 620px;
  gap: 8px;
  border: 1px solid var(--line);
  background: #fff;
  padding: 10px;
}
.positions-table .ops-row {
  grid-template-columns: 130px 100px 90px 100px 110px 110px 120px;
  min-width: 780px;
}
.history-table .ops-row {
  grid-template-columns: minmax(180px, 1.4fr) 150px 90px 120px 120px 90px 100px;
  min-width: 850px;
}
.audit-filter-panel a.button-link {
  min-height: 48px;
}
.audit-table .ops-row {
  grid-template-columns: minmax(180px, 1.3fr) 130px minmax(180px, 1.2fr) 90px 120px minmax(180px, 1.2fr) 80px;
  min-width: 1020px;
}
.audit-table .ops-row.ok {
  border-left: 5px solid var(--success);
}
.audit-table .ops-row.blocked {
  border-left: 5px solid var(--danger);
}
.opportunity-table .ops-row {
  grid-template-columns: 130px 110px 100px minmax(140px, 1fr) minmax(170px, 1.3fr);
  min-width: 710px;
}
.ops-row span {
  font-size: 13px;
  font-weight: 650;
  overflow-wrap: anywhere;
}
.ops-head {
  background: var(--field);
}
.ops-head span {
  color: var(--muted);
  font-size: 12px;
  text-transform: uppercase;
}
.kv-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}
.kv-grid div {
  border: 1px solid var(--line);
  background: #f8fbfc;
  padding: 12px;
}
.kv-grid strong,
.kv-grid span {
  display: block;
}
.kv-grid strong {
  color: var(--muted);
  font-size: 12px;
  margin-bottom: 6px;
}
.kv-grid span {
  font-size: 15px;
  font-weight: 700;
}
.compact-list {
  margin: 0;
  padding-left: 18px;
}
.compact-list li {
  margin: 7px 0;
  font-weight: 700;
}
.status.success {
  color: var(--success);
  border-color: #a7dfbc;
  background: #edfdf3;
}
.status pre {
  color: inherit;
  background: transparent;
  border: 0;
  padding: 8px 0 0;
  font-size: 12px;
}
pre {
  margin: 0;
  padding: 16px;
  font-size: 13px;
  line-height: 1.42;
  white-space: pre-wrap;
  font-family: Consolas, "Courier New", monospace;
}
@media (max-width: 760px) {
  .auth-shell {
    grid-template-columns: 1fr;
  }
  .brand-panel {
    min-height: 34vh;
    padding: 30px 22px;
  }
  .form-panel {
    padding: 30px 22px;
  }
  h1 { font-size: 28px; }
  h2 { font-size: 25px; }
  .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .dashboard-shell {
    padding: 14px;
  }
  .mobile-topbar {
    align-items: flex-start;
  }
  .top-actions {
    flex-direction: column;
    align-items: stretch;
  }
  .command-grid,
  .kv-grid {
    grid-template-columns: 1fr;
  }
  .trade-form-panel form {
    grid-template-columns: 1fr;
  }
  .system-strip span {
    flex: 1 1 42%;
  }
  .ticket-row {
    grid-template-columns: 1fr 1fr;
  }
}
"""


def _trade_status_page(user_ctx: Dict[str, Any], session: Dict[str, Any]) -> str:
    load_local_env()
    
    active_sessions = SessionRuntimeService().get_active_sessions()
    
    if not active_sessions:
        return _page(
            "Trade Status",
            f'''
            <main class="dashboard-shell">
              {_header("Trade Status Summary", user_ctx, "trade-status")}
              {_identity_strip(user_ctx, "Status: Disconnected")}
              <section class="data-panel" aria-label="Disconnected Status">
                <h2>Ledger Data</h2>
                <div class="alert error">DATA UNAVAILABLE: No active CSS runtime session found. Cannot load canonical state.</div>
              </section>
            </main>
            '''
        )
        
    session_id = active_sessions[0]["session_id"]
    snapshot = PnlRuntimeService().get_latest_snapshot(session_id)
    trades = TradeRuntimeService().get_all_session_trades(session_id)
    
    if not snapshot:
        snapshot = {}
        
    trades_html = ""
    for t in trades:
        tid = html.escape(str(t.get("trade_id", "UNKNOWN")))
        sym = html.escape(str(t.get("symbol", "N/A")))
        side = html.escape(str(t.get("direction", "N/A")))
        asset_class = html.escape(str(t.get("asset_class", "N/A")))
        status = html.escape(str(t.get("status", "UNKNOWN")).upper())
        qty = html.escape(str(t.get("quantity", "0.0")))
        entry = html.escape(str(t.get("entry_price", "0.0")))
        current = html.escape(str(t.get("current_price", "0.0")))
        pnl = html.escape(str(t.get("realized_pnl", "0.0")))
        gate = html.escape(str(t.get("gate_decision", "N/A")))
        broker = html.escape(str(t.get("broker_name", "UNKNOWN")))
        tstamp = html.escape(str(t.get("opened_at", "")))
        
        trades_html += f'''
        <tr class="trade-row">
          <td><span class="muted">{tstamp[:19] if tstamp else ''}</span><br>{tid[:8]}</td>
          <td><strong>{sym}</strong><br>{side} {qty} {asset_class}</td>
          <td>{entry} / {current}<br><span class="muted">{broker}</span></td>
          <td>{status} / {gate}<br>{pnl}</td>
        </tr>
        '''
        
    if not trades_html:
        trades_html = '<tr><td colspan="4" class="muted center">No canonical trades recorded for this session.</td></tr>'

    return _page(
        "Trade Status",
        f'''
        <main class="dashboard-shell">
          {_header("Trade Status Summary", user_ctx, "trade-status")}
          {_identity_strip(user_ctx, "Status: Canonical")}
          <section class="metric-grid" aria-label="Account Balances">
            <article><strong>Account balance</strong><span>{snapshot.get("account_balance", "DATA UNAVAILABLE")}</span></article>
            <article><strong>Cash</strong><span>{snapshot.get("available_cash", "DATA UNAVAILABLE")}</span></article>
            <article><strong>Buying power</strong><span>{snapshot.get("buying_power", "DATA UNAVAILABLE")}</span></article>
            <article><strong>Equity</strong><span>{snapshot.get("equity", "DATA UNAVAILABLE")}</span></article>
            <article><strong>Open PnL</strong><span>{snapshot.get("unrealized_pnl", "DATA UNAVAILABLE")}</span></article>
            <article><strong>Realized PnL</strong><span>{snapshot.get("realized_pnl", "DATA UNAVAILABLE")}</span></article>
            <article><strong>Total PnL</strong><span>{snapshot.get("net_pnl", "DATA UNAVAILABLE")}</span></article>
            <article><strong>Open trades</strong><span>{snapshot.get("open_positions", "DATA UNAVAILABLE")}</span></article>
            <article><strong>Closed trades</strong><span>{snapshot.get("closed_positions", "DATA UNAVAILABLE")}</span></article>
            <article><strong>Pending/rejected orders</strong><span>{snapshot.get("pending_orders", "DATA UNAVAILABLE")} / {snapshot.get("rejected_orders", "DATA UNAVAILABLE")}</span></article>
          </section>
          
          <section class="data-panel" aria-label="Trade List">
            <h2>Canonical Trade Ledger</h2>
            <div class="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Time / ID</th>
                    <th>Asset / Side</th>
                    <th>Entry / Current / Broker</th>
                    <th>Status / Gate / PnL</th>
                  </tr>
                </thead>
                <tbody>
                  {trades_html}
                </tbody>
              </table>
            </div>
          </section>
        </main>
        ''',
    )
