# Phase 165 - Coinbase Authentication Completion and Read-Only Connectivity Certification

## Purpose

Phase 165 completes Coinbase read-only broker integration by replacing generic authentication failures with structured diagnostic evidence and producing a canonical read-only connectivity certificate.

This phase does not add trading functionality. It never submits orders, cancels orders, arms execution, enables live trading, or bypasses RC1 safety controls.

## Authentication Trace

`backend.runtime.coinbase_authentication_trace` captures:

- credential validation status
- API key format status
- EC private key PEM parsing
- JWT/signature generation status
- timestamp and clock-skew status
- declared read permission status
- endpoint alignment and sandbox/live mismatch evidence
- TLS/host resolution state
- authentication latency
- HTTP status
- Coinbase error code
- Coinbase error message
- precise failure stage

When credential material is required and invalid, endpoint reads are not attempted.

## Read-Only Certification

`backend.runtime.coinbase_connectivity_certificate` summarizes:

- credential validation
- authentication
- account access
- balances
- portfolio information
- products
- market data
- latency
- safety gates
- execution authority

Read-only certification passes only when all required read-only evidence passes and safety remains blocked.

## Runtime Integration

Phase 156B embeds the Coinbase authentication trace in the authentication stage details. Existing Phase 156B payload fields remain backward compatible.

## Safety Guarantees

All Phase 165 outputs force:

- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`
- `advisory_only=true`

Execution authority remains `BLOCKED`.
