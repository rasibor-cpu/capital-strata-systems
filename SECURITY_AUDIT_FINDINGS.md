# Security Audit Findings

Date: 2026-05-06

Verdict: NOT SAFE TO DEPLOY

This program should not be deployed to production, exposed to the internet, or run with real broker credentials until the findings below are resolved and retested.

## Findings

### Finding 1: [P0] Hardcoded default superuser password

File: `backend/app/auth/auth_config.py:35-36`

The auth layer defaults the production superuser password to `123456` if no environment override is present. That is a deploy blocker, especially because this repo also contains several other auth paths using the same deterministic password pattern.

### Finding 2: [P0] OTP disclosed in response in dev mode

File: `backend/app/auth/auth_router.py:95-100`

When `HEADLESS_DEV_MODE` is enabled, login returns the OTP in the API response. If that environment flag leaks into deployment, second factor collapses into a single API call.

### Finding 3: [P0] No rate limiting on login or OTP verification

File: `backend/app/auth/auth_router.py:83-130`

The login and OTP verify endpoints have no throttling, account lockout, IP throttling, replay telemetry, or brute-force controls. A 6-digit OTP plus no rate limit is not production-safe.

### Finding 4: [P0] Live broker order adapter has no internal live gate

File: `backend/app/brokers/oanda_adapter.py:107-154`

`place_order` posts directly to OANDA when configured. It validates symbol/side/units, but it does not enforce an execution firewall, live kill switch, session authorization, max order size, SL/TP requirement, or idempotency. Any caller reaching this method can place an order.

### Finding 5: [P0] Coinbase private key material found in repo

File: `keys/cdp_api_key (2).json:2-3`

A Coinbase CDP private key is present under the repo's `keys` directory. Treat it as compromised. Rotate/revoke it before any deployment, and purge it from git history if it was committed.

### Finding 6: [P1] Headless API execution path is broken

File: `backend/app/headless_guarded_entry.py:230-231`

The API builds a `HeadlessConfig`, then `run_headless` calls `ExecutionGate(allow_live=cfg.allow_live)`, but the current `ExecutionGate.__init__` takes no arguments. A smoke check returned `TypeError: ExecutionGate.__init__() got an unexpected keyword argument 'allow_live'`.

### Finding 7: [P1] Orchestrator cannot instantiate allocator

File: `backend/intelligence/trade_decision_orchestrator.py:25-28`

`TradeDecisionOrchestrator` calls `CapitalAllocator()` with no arguments, but the current allocator requires `total_capital`. A smoke check fails at construction, so the main decision path is not currently reliable.

### Finding 8: [P1] Gate rejects dashboard asset-class casing

File: `backend/governance/css_unified_trade_gate.py:8-12`

The unified trade gate accepts lowercase asset classes (`crypto`, `fx`, etc.), while the dashboard bridge emits uppercase `CRYPTO`. This makes the gate ineffective operationally because integration code can either block everything or route around it to keep the dashboard working.

## Summary

The application has the shape of a governance-first trading system, but it is not yet deployable. The critical blockers are credential exposure, weak/default authentication, missing rate limits, inconsistent live execution boundaries, broken core execution paths, and integration drift across gate/orchestrator/dashboard layers.

Minimum deployment bar:

- Rotate all exposed broker/API credentials.
- Remove secrets and runtime state from the repository and git history.
- Replace default-password auth with production-grade password handling.
- Disable OTP disclosure outside isolated local development.
- Add rate limiting and lockout to auth endpoints.
- Put a final, non-bypassable live execution firewall inside every real broker order method.
- Fix and retest the headless execution path.
- Fix and retest the trade decision orchestrator.
- Normalize asset-class casing before gate evaluation.
- Add deployment tests that prove live orders cannot execute unless every required gate passes.

## Fix Plan

The work should be done in priority order. P0 and P1 are deploy blockers.

### P0: Stop Deployment Risk Immediately

1. Rotate and revoke exposed credentials.
   - Revoke the Coinbase CDP key found in `keys/cdp_api_key (2).json`.
   - Rotate OANDA live/practice tokens found in backup `.env` files.
   - Treat every credential that has touched this repo as compromised.

2. Purge secrets from git history.
   - Remove private keys, `.env` contents, API tokens, and runtime state from history.
   - Add strict ignore rules for `keys/`, `*.pem`, `*.key`, `.env`, `.env.*`, `artifacts/`, and broker state files.

3. Remove hardcoded production auth defaults.
   - Files: `backend/app/auth/auth_config.py`, `backend/app/security/auth_gate.py`, dashboard auth blocks.
   - Example fix:
     ```python
     password = os.getenv("REA_SUPERUSER_PASSWORD")
     if not password:
         raise RuntimeError("REA_SUPERUSER_PASSWORD must be set")
     ```

4. Disable OTP disclosure outside isolated local development.
   - File: `backend/app/auth/auth_router.py`.
   - Example fix:
     ```python
     if HEADLESS_DEV_MODE and os.getenv("APP_ENV") == "production":
         raise RuntimeError("HEADLESS_DEV_MODE forbidden in production")
     ```

5. Add auth rate limiting and lockout.
   - Protect `/auth/login` and `/auth/verify`.
   - Add per-username and per-IP throttling.
   - Burn OTPs after too many failed attempts.
   - Audit failed login and OTP attempts.

6. Put final live execution gates inside broker adapters.
   - File: `backend/app/brokers/oanda_adapter.py`.
   - Required checks: global kill switch, authenticated session, role permission, broker mode, max order size, instrument whitelist, idempotency key, SL/TP policy, and audit logging.
   - Example fix:
     ```python
     if not live_execution_allowed():
         return {"ok": False, "error": "LIVE_EXECUTION_BLOCKED"}

     if units_i > MAX_OANDA_UNITS:
         return {"ok": False, "error": "ORDER_SIZE_LIMIT_EXCEEDED"}

     if not idempotency_key:
         return {"ok": False, "error": "MISSING_IDEMPOTENCY_KEY"}
     ```

### P1: Restore Broken Core Execution Paths

1. Fix the headless execution path.
   - File: `backend/app/headless_guarded_entry.py`.
   - Current issue: `ExecutionGate(allow_live=cfg.allow_live)` does not match the current `ExecutionGate.__init__`.
   - Fix by either removing the constructor argument and using a separate firewall, or updating `ExecutionGate` to accept the intended parameter.

2. Fix orchestrator allocator construction.
   - File: `backend/intelligence/trade_decision_orchestrator.py`.
   - Current issue: `CapitalAllocator()` requires `total_capital`.
   - Example fix:
     ```python
     self.capital_allocator = CapitalAllocator(total_capital=100000.0)
     ```
   - Better fix: inject capital from account/portfolio state and fail closed if live capital cannot be resolved.

3. Normalize asset-class casing.
   - File: `backend/governance/css_unified_trade_gate.py`.
   - Example fix:
     ```python
     asset_class = str(candidate.get("asset_class", "")).lower()
     ```
   - Also normalize source data in `backend/intelligence/dashboard_orchestrator_bridge.py`.

4. Make gate API usage consistent.
   - Standardize on one canonical method, such as `approve_trade(...)`.
   - Ensure orchestrator, dashboard, and execution paths all call the same gate contract.

5. Add smoke tests for deploy-critical paths.
   - Headless API does not crash.
   - Orchestrator can instantiate.
   - Gate handles normalized asset classes.
   - Broker adapter blocks live orders without explicit authorization.
   - Auth rejects missing production password config.

### P2: Consolidate Architecture and Remove Bypass Paths

1. Define one authoritative app entrypoint.
   - Current overlap includes root `main.py`, `backend/app/main.py`, `backend/app/api.py`, and dashboard runner scripts.
   - Pick one production API path and exclude everything else from deploy packaging.

2. Define one authoritative execution boundary.
   - All execution should flow through auth/session validation, decision envelope, risk gate, live firewall, and broker adapter final gate.
   - No direct dashboard or script calls should reach live broker methods.

3. Separate runtime state from source.
   - Move `artifacts/`, `audit_logs/`, session recovery files, account state files, and broker state JSON outside the repo.

4. Replace plain JSON state with durable storage.
   - Use SQLite or Postgres for sessions, orders, audit logs, idempotency records, positions, and risk state.

5. Add idempotency and replay protection.
   - Every order attempt should carry an idempotency key.
   - Duplicate keys must not place duplicate orders.
   - Store request hash, user, timestamp, decision ID, and broker response.

6. Harden password storage.
   - Replace SHA-256 password hashes with Argon2id or bcrypt.
   - Add per-user salts.
   - Remove unsafe max-6 password policy.

### P3: Operational Hardening and Scalability

1. Pin dependencies.
   - Replace broad `requirements.txt` entries with exact versions.
   - Add dependency vulnerability scanning.

2. Add structured audit logging.
   - Log user ID, session ID, request ID, decision ID, gate result, broker mode, and reason.
   - Never log secrets, OTPs, tokens, private-key paths, or full sensitive payloads.

3. Add production configuration validation.
   - Fail startup if default credentials are active, dev mode is enabled, live mode lacks broker gates, secrets are loaded from repo files, or kill switch config is missing.

4. Add deployment test suite.
   - Prove `LIVE_EXECUTION_ENABLED=false` blocks all real orders.
   - Prove missing auth blocks all non-health API calls.
   - Prove bad OTP attempts throttle or lock out.
   - Prove duplicate order requests do not double-execute.
   - Prove broker adapter refuses oversized orders.

5. Add monitoring and alerting.
   - Alert on failed login bursts, OTP brute-force attempts, live-mode arming, order rejection spikes, missing heartbeat, broker credential loads, and kill-switch changes.

6. Clean repo hygiene.
   - Remove backup scripts from production packaging.
   - Move old dashboard snapshots outside deploy scope.
   - Fix `.gitignore` contradictions.
   - Add CI checks for secret scanning, linting, tests, dependency audit, and runtime artifact detection.

### Recommended Fix Order

1. Rotate/revoke secrets.
2. Purge secrets from git history.
3. Disable default credentials and OTP disclosure.
4. Add auth rate limiting.
5. Gate broker adapters directly.
6. Fix headless execution crash.
7. Fix orchestrator crash.
8. Normalize gate inputs.
9. Add deploy-blocking tests.
10. Consolidate execution paths.
11. Move runtime state out of the repo.
12. Harden dependencies, monitoring, and CI.
