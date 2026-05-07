from __future__ import annotations

import html
import os
import secrets
import time
import urllib.parse
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse

from dashboard.auth.css_sign_on import (
    AuthFailure,
    PasswordChangeRequired,
    PasswordValidationError,
    authenticate_credentials,
    change_password,
    load_users,
    save_users,
)
from dashboard.runtime.runtime_bootstrap import DashboardRuntimeBootstrap


SESSION_COOKIE = "css_mobile_session"
PASSWORD_CHANGE_COOKIE = "css_mobile_pw_change"
SESSION_MAX_SECONDS = int(os.getenv("CSS_MOBILE_SESSION_SECONDS", "28800") or 28800)
PASSWORD_CHANGE_SECONDS = int(os.getenv("CSS_MOBILE_PASSWORD_CHANGE_SECONDS", "600") or 600)

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


@app.post("/logout")
async def logout(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        _SESSIONS.pop(token, None)
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/api/status")
async def status(request: Request):
    session = _get_session(request)
    return JSONResponse(
        {
            "ok": True,
            "authenticated": bool(session),
            "mode": "mobile-read-only",
            "live_orders_enabled": False,
        }
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
              <span>Read Only</span>
            </div>
          </section>

          <section class="form-panel" aria-label="Sign on form">
            <h2>Sign On</h2>
            <p class="muted">Use your CSS user ID and password.</p>
            {_status_markup(message, status)}
            <form method="post" action="/login" autocomplete="on">
              <label for="user_id">User ID</label>
              <input id="user_id" name="user_id" inputmode="numeric" pattern="[0-9]*" value="00000" required>

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
    safe_name = html.escape(str(user_ctx.get("display_name", "CSS User")))
    safe_role = html.escape(str(user_ctx.get("role", "VIEWER")))
    safe_user_id = html.escape(str(user_ctx.get("user_id", "")))

    return _page(
        "Dashboard",
        f"""
        <main class="dashboard-shell">
          <header class="mobile-topbar">
            <div>
              <p class="eyebrow">Capital Strata Systems</p>
              <h1>Dashboard</h1>
            </div>
            <form method="post" action="/logout">
              <button class="ghost" type="submit">Logout</button>
            </form>
          </header>

          <section class="identity-strip">
            <span>{safe_name}</span>
            <span>{safe_role}</span>
            <span>ID {safe_user_id}</span>
            <span>Mobile Read Only</span>
          </section>

          <section class="metric-grid" aria-label="Dashboard summary">
            <article><strong>Mode</strong><span>Paper</span></article>
            <article><strong>Orders</strong><span>Disabled</span></article>
            <article><strong>Gate</strong><span>Read Only</span></article>
            <article><strong>Runtime</strong><span>Mobile</span></article>
          </section>

          <section class="terminal-panel" aria-label="Dashboard output">
            <pre>{html.escape(dashboard_text)}</pre>
          </section>
        </main>
        """,
    )


def _mobile_dashboard_text(user_ctx: Dict[str, Any], session: Dict[str, Any]) -> str:
    return DashboardRuntimeBootstrap().run(
        account_payload={
            "cash_balance": 10000.00,
            "total_equity": 10250.00,
            "buying_power": 5000.00,
            "margin_used": 0.00,
            "available_margin": 5000.00,
            "currency": "USD",
            "broker": "MOBILE",
            "account_mode": "paper",
        },
        positions_payload={
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
        market_payload={
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
            "regime_state": "MOBILE_READ_ONLY",
            "spread_state": "TIGHT",
            "execution_cost_state": "NO_PHONE_EXECUTION",
            "signal_confluence_state": "CONFIRMED",
        },
        governance_payload={
            "governance_enabled": True,
            "session_locked": False,
            "defensive_mode_active": False,
            "unified_trade_gate_active": True,
            "audit_enabled": True,
            "last_governance_event": "Mobile read-only dashboard session authenticated",
        },
        risk_payload={
            "risk_state": "READ_ONLY",
            "gate_status": "PHONE_EXECUTION_DISABLED",
            "current_drawdown_pct": 0.35,
            "max_drawdown_pct": 2.00,
            "daily_loss_limit": 500.00,
            "position_limit": 0,
            "exposure_limit": 0.00,
            "risk_limits_breached": [],
        },
        execution_payload={
            "execution_state": "VIEW_ONLY",
            "accepted_trade_count": 0,
            "rejected_trade_count": 0,
            "pending_trade_count": 0,
            "total_execution_cost": 0.00,
            "slippage_cost": 0.00,
            "spread_cost": 0.00,
            "fee_cost": 0.00,
            "avg_slippage_bps": 0.00,
            "avg_spread_bps": 0.00,
            "execution_cost_state": "NO_PHONE_ORDERS",
            "last_execution_event": "Phone dashboard is read-only",
        },
        session_payload={
            "session_id": "MOBILE-SESSION",
            "user_id": str(user_ctx.get("user_id", "mobile_user")),
            "role": str(user_ctx.get("role", "VIEWER")),
            "cycle_number": 1,
            "engine_mode": "SAFE",
            "live_or_paper": "paper",
        },
        diagnostics_payload={
            "message": f"Mobile session created={int(float(session.get('created', 0)))}"
        },
    )


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
input:focus {
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
.terminal-panel {
  background: #0f1720;
  color: #e8fbfb;
  border: 1px solid #23323d;
  overflow: auto;
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
}
"""
