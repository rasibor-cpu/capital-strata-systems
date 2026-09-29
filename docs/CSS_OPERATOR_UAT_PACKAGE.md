# CSS Operator UAT Package — Engineering Release Candidate

_For human operator acceptance of the operator web dashboard and commercial governance on the engineering release candidate. DEVELOPMENT/UAT only: nothing here authorizes production, live trading, broker execution, customer charging or money movement. No credential appears in this document or anywhere in the repository._

## 1. What is under test

| Item | Value |
|---|---|
| Repository | `rasibor-cpu/capital-strata-systems` |
| Branch / PR | `css-operator-auth-2026-09-28` / PR #101 (→ `css-commercial-collections-2026-09-19`) |
| Source | The release-candidate commit recorded as `SOURCE_HEAD` in the "Release evidence" block of `docs/CSS_COMMERCIAL_CLOSURE_EVIDENCE.md`. Check out exactly that commit; `git rev-parse HEAD` must match. |
| Application | Operator web dashboard `dashboard.web.web_app:app` (uvicorn) |
| Safety posture (must hold throughout) | `execution_allowed=false` · `live_trading_blocked=true` · `broker_execution_armed=false` · `advisory_only=true` |

## 2. Configuration

Set by `launchers/CSS Web UAT Server.cmd` (override any of them by setting the variable before launching):

| Variable | UAT value | Purpose |
|---|---|---|
| `CSS_ENV` | `development` | Allows the session cookie over plain HTTP on `127.0.0.1` only. Never set in a real deployment. |
| `CSS_COMMERCIAL_DB` | `data\css_commercial_uat.sqlite3` | Maker-checker actions + commercial audit log (enables the commercial governance API). |
| `CSS_AUTH_AUDIT_DB` | `data\css_auth_audit.sqlite3` | Authentication/account audit trail. |
| Runtime DB | `data\css_runtime.db` (fixed) | Agreements, trial enrollments, commercial records. |
| User store | `data\users.json` (fixed) | Operator identities (`css_sign_on`). |

All of `data\` and `artifacts\` are gitignored; nothing produced by UAT can be committed by accident.

## 3. One-time setup (engineering, before operators arrive)

Run from the repository root in a terminal on the UAT machine.

1. **Back up** any existing `data\users.json`, `data\css_runtime.db*`, `data\css_commercial_uat.sqlite3`, `data\css_auth_audit.sqlite3` (copy them somewhere outside the repo). These are the rollback point.
2. **Initialize the administrator (one time, local only).** A fresh or never-claimed user store holds administrator `00000` with no usable password; the old published default no longer works anywhere.
   ```
   python -m scripts.bootstrap_css_admin
   ```
   Type the new administrator password twice (not echoed). The command refuses to run a second time. Record the password in the owner's password manager — never in a file in the repo, a ticket or chat.
3. **Provision the DEV/UAT operator identities.**
   ```
   python scripts\provision_dev_uat_operators.py
   ```
   Creates FINCON `10001`, HEAD_FINCON `10002`, AUDIT `10003`, HEAD_COMPLIANCE `10004` with random one-time passwords written only to the gitignored `artifacts\dev_uat_operator_credentials.json`. Hand each operator their own one-time password out of band (in person or via the password manager); each must change it at first sign-in. Delete the file once handed over.
4. **Seed the UAT governing agreement.**
   ```
   set CSS_ENV=development
   python -m scripts.seed_uat_trial_agreement
   ```
   Inserts exactly one agreement, `UAT-AGR-001` / `v1` ("UAT ONLY" terms). Idempotent; refuses outside `CSS_ENV=development|dev|local|uat`; refuses to rewrite a different agreement with the same id.

## 4. Start / stop

- **Start:** double-click `launchers\CSS Web UAT Server.cmd` (or run it from a terminal). Open `http://127.0.0.1:8000/login`.
- **Stop:** press `Ctrl+C` in the server window, then close it.
- **Restart** (used by checklist item 16): stop, then start again. Operator sessions are held in memory and end on restart by design (see known limitations); pending maker-checker actions, enrollments and audit logs persist.

## 5. First sign-in (forced password change)

The web sign-in page asks operators with a one-time password to change it first. Use the operator API once per operator (engineering can run this with the operator at the keyboard):

```
curl -s -X POST http://127.0.0.1:8000/auth/operator/change-password -H "Content-Type: application/json" -d "{\"user_id\":\"10001\",\"current_password\":\"<one-time>\",\"new_password\":\"<new>\",\"confirm_password\":\"<new>\"}"
```

Passwords: at least the policy minimum, not previously used, not the old published default. Do not paste real passwords into shared terminals or logs; clear shell history afterwards.

## 6. UAT checklist and expected results

Record each result (Pass / Fail + note) in the evidence sheet (section 8). "Role" is who performs the step.

| # | Area | Role | Steps | Expected result |
|---|---|---|---|---|
| 1 | Sign in | each | Sign in at `/login` with the changed password | Lands on `/dashboard`; header shows the navigation bar with a **Logout** button |
| 2 | Wrong password / lockout | any | Enter a wrong password 3 times for one identity | 3rd attempt reports a timed pause; correct password is refused until it expires |
| 3 | Admin bootstrap closed | engineering | Try signing in as `00000` with the old default `123456` | Refused |
| 4 | Mission Control | each | Open Dashboard; check status panels | Data or "unavailable" states load; nothing indicates execution allowed or armed |
| 5 | Role restriction — commercial | AUDIT | On Trial & Contract, attempt **Enroll** | Blocked (not permitted); nothing created |
| 6 | Billing | FINCON / AUDIT | Open Billing; enter a policy id and period | Page loads while signed in (no sign-in error). On a fresh UAT DB an unknown policy shows a not-found message — fail-closed, expected |
| 7 | Advice attribution / profitability / loss recovery | FINCON / AUDIT | On Billing, open advice-profitability history for a terms id | Same as 6: presentation loads; with no seeded history, a not-found message. See section 9 for the data caveat |
| 8 | Trial contract — load terms | FINCON | Trial & Contract → Agreement ID `UAT-AGR-001`, Version `v1` → Load Agreement | Shows the "UAT ONLY" pricing and conversion disclosure, 30-day trial, jurisdiction CA-ON |
| 9 | Trial enrollment — maker | FINCON | Enter a new Customer ID + Account Reference, tick both confirmations, **Enroll** | Message: enrollment request `<id>` is **PENDING** and takes effect only after a second approver; no payment executed |
| 10 | Maker cannot approve own request | FINCON | Try to approve the action from step 9 via the governance API with FINCON's session | Refused |
| 11 | Checker approval | HEAD_FINCON (or HEAD_COMPLIANCE) | Approve the action from step 9 (governance API: `POST /api/v1/commercial/controlled-actions/<id>/approve` with its `expected_payload_hash`) | Status **EXECUTED**; Trial & Contract → Check Status for that customer shows **TRIAL_ACTIVE** |
| 12 | Replay / tamper | HEAD_FINCON | Approve the same action again; approve another with a wrong payload hash | Replay refused (already decided); wrong hash refused |
| 13 | Cancellation | FINCON → HEAD_FINCON | **Cancel** for the enrolled customer, then approve | PENDING, then EXECUTED after approval; Check Status shows **CANCELED** and automatic conversion not allowed |
| 14 | Commercialization operations | FINCON / AUDIT | Open Launch Ops; enter identifiers | Page loads and its status call is accepted while signed in (no sign-in error). Whatever status is shown for UAT identifiers, nothing indicates payment or charging is enabled |
| 15 | Audit visibility | AUDIT / HEAD_COMPLIANCE | Governance API `GET /api/v1/commercial/audit` | REQUEST / APPROVE / EXECUTE events for steps 9–13 with maker and checker ids; no passwords or tokens |
| 16 | Restart / recovery | engineering | Leave one request PENDING, restart the server (section 4), sign in again as HEAD_FINCON | Previous browser session is signed out; the PENDING request is still listed and can be approved |
| 17 | Logout / session revocation | each | Click **Logout**; press Back and reload | Returns to sign-in; the old session cannot load any page |
| 18 | Disable (session revocation) | SUPER_USER `00000` | Disable one UAT identity via `POST /auth/operator/admin/users/<id>/disable`; that operator reloads | Operator is signed out and cannot sign in; re-enable restores sign-in with a fresh session |

Governance-API steps (10–12, 15, 18) need a bearer token: `POST /auth/operator/login` returns `token`; send it as `Authorization: Bearer <token>`. Never share or record tokens.

## 7. Rollback / recovery

- **Application:** stop the server; check out the previous known-good commit (`55865222` for COM-014, `d5129cf6` for COM-015) and restart. No schema migration in this release candidate needs reversing: the user-store change adds one field (`bootstrap_state`) to administrator `00000` only; the runtime and commercial databases gain only UAT rows.
- **Data:** stop the server and restore the files backed up in section 3 step 1.
- **Lost administrator password (UAT only):** restore the backed-up `data\users.json`, or remove the `00000` record from a copy of the store and rerun `python -m scripts.bootstrap_css_admin` (the store re-creates `00000` uninitialized).
- Broader commercial rollback: `docs/CSS_COMMERCIAL_ROLLBACK_PLAN.md`.

## 8. Evidence capture

For each checklist row record: date/time, operator id (never the password), result, screenshot (browser window only — no terminals showing secrets), and any on-screen message. At the end of the session, engineering collects:

- `git rev-parse HEAD` output;
- `data\css_auth_audit.sqlite3` and `data\css_commercial_uat.sqlite3` (copies), plus the result of verifying both chains:
  ```
  python -c "from engine.commercial.commercial_audit import CommercialAuditLog as L; [print(p, L(p).verify()) for p in (r'data\css_auth_audit.sqlite3', r'data\css_commercial_uat.sqlite3')]"
  ```
- the completed checklist, signed off by the owner.

Evidence files contain operator ids and business test data; store them with the UAT record, not in the repository.

## 9. Known limitations and caveats for operators

- **Sessions do not survive a server restart** — sign in again (item 16).
- **CSRF rejections are refused but not written to the audit trail.**
- **No seeded advice-profitability / client-earnings history.** Items 6, 7 and 14 verify that the screens load and fail closed; the commercial economics (commission only on profitable, accepted-CSS-advice trades; earning stops in loss and resumes only after full recovery to net positive; independent/modified/external trades attributed separately) are verified by 189 automated tests, not by populated screens. Presenting populated history in UAT needs an owner-approved paper/sandbox dataset.
- **Open product/governance decisions** (not defects, visible by design): no per-operator book-of-business scoping; Mission Control open to any signed-in operator; no maker-checker on identity administration.
