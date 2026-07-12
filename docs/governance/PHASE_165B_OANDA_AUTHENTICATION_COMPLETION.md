# Phase 165B - OANDA Authentication Completion

## Purpose

Phase 165B adds OANDA-specific authentication tracing and read-only connectivity certification to the Phase 165 broker diagnostics workstream.

The implementation replaces generic OANDA availability failures with structured evidence for credential material, endpoint selection, HTTP status, transport reachability, account access, market-data access, open trades, and positions.

This phase certifies read-only operational connectivity only. It never authorizes live execution.

## Validation Sequence

1. Validate credential material through the canonical broker credential loader or an explicitly supplied environment mapping.
2. Confirm token presence, account ID presence, structural format, selected environment, selected base URL, and practice/live endpoint alignment.
3. Capture DNS/TLS reachability state for the configured OANDA host.
4. Probe read-only endpoints:
   - account summary
   - account details
   - instruments
   - EUR_USD pricing
   - open trades
   - open positions
5. Record HTTP status, endpoint stage, response type, sanitized OANDA error code/message, exception class, and latency.
6. Produce a canonical read-only certificate with credential, authentication, account, balance, NAV, margin, instruments, pricing, trades, positions, latency, and safety-gate status.

## Safety Guarantees

Phase 165B is advisory only.

It always reports:

- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`
- `advisory_only=true`
- `execution_authority=BLOCKED`

The module never submits orders, previews orders, cancels orders, closes trades, closes positions, modifies broker state, arms execution, or enables live trading.

## Runtime Integration

The OANDA authentication trace is embedded into Phase 156B authentication evidence. Phase 156B continues to own operational connectivity certification and continues to fail closed when Phase 156A is not GREEN.

The Phase 165B certificate is a canonical read-only connectivity report. It is parallel to the Coinbase Phase 165 certificate and does not replace R7, RBAC, broker startup gates, NO-GO logic, live execution firewall, or execution boundary validation.

## Consistency Rules

The certificate must not report:

- GREEN health when authentication fails
- account metrics when account access fails
- live execution capability while advisory-only mode is active
- any execution authority while `broker_execution_armed=false`

If any required read-only evidence is missing, the canonical broker state is `READ_ONLY_BLOCKED`.

When all required read-only evidence passes and latency is not RED, the canonical broker state is `READ_ONLY_CERTIFIED`.

## Governance Relationship

Phase 165B depends on the existing broker credential loader, broker bootstrap behavior, broker readiness framework, Phase 156B connectivity certifier, and live execution firewall.

It does not weaken any of them. R7 governance, RBAC, NO-GO protections, and firewall controls remain authoritative for any live execution decision.
