# CSS Full-System Security Audit Closure — Cycle 1

Status: TECHNICAL CLOSURE VALIDATION PENDING CI

This report rechecks the historical deployment blockers recorded in
SECURITY_AUDIT_FINDINGS.md against the current full-test release candidate.

## Historical findings

1. Hardcoded/default superuser password
   - CLOSED in current code.
   - Superuser password is required from REA_SUPERUSER_PASSWORD.
   - Missing configuration fails authentication closed.

2. OTP disclosure in headless mode
   - CLOSED in current regression suite.
   - Generated OTP is not returned in the login response.

3. Missing authentication rate limiting
   - CLOSED in current regression suite.
   - Repeated failed login attempts are rate-limited.

4. OANDA order firewall bypass risk
   - CLOSED by this cycle.
   - OANDA_ENABLE_LIVE_TRADING alone is insufficient.
   - Every broker mutation now requires canonical live-toggle RBAC authorization
     plus live-arm authorization.
   - Private mutation calls through _request_json fail closed unless the public
     mutation boundary has explicitly authorized them.
   - Order placement requires an idempotency key.
   - Order size is capped by OANDA_MAX_ORDER_UNITS with a fail-closed ceiling.

5. Headless ExecutionGate constructor mismatch
   - CLOSED in current code/regression coverage.

6. TradeDecisionOrchestrator capital allocator construction
   - CLOSED in current code/regression coverage.

7. CSS unified trade gate asset-class normalization
   - CLOSED in current code/regression coverage.

8. Active live-dashboard broker caller bypass
   - CLOSED by this cycle.
   - The active dashboard supplies authenticated SESSION_USER_CTX to the OANDA
     adapter and derives a deterministic per-session/symbol/cycle idempotency
     key before broker order placement.

## Broker mutation rule after closure

Broker mutation requires all applicable controls to agree:

- OANDA broker mutation firewall enabled;
- engine in LIVE mode;
- authenticated/auditable user context;
- role or explicit permission authorizes live execution;
- REA live-arm controls authorize execution;
- order idempotency key present for new order creation;
- units within configured ceiling; and
- adapter private mutation wall cannot be bypassed.

No single environment variable is sufficient to authorize an OANDA mutation.

## Remaining production distinction

This technical closure does not enable production live execution. Production
still requires the separately governed execution certification, broker
credentials/environment approval, operational evidence, and release-owner
authorization. Current test and commercialization controls remain fail-closed.
