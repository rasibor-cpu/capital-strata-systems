# Phase 196-R2 — Live-Authority TTL

## Status

Implementation under review.

This phase adds a dedicated finite live-execution authority lease to the
canonical `backend/runtime/live_execution_authority.py` AND-gate.

It does not authorize live trading.

`LIVE_TRADING_NOT_AUTHORIZED` remains active.

## Contract

The lease is:

- finite;
- maximum 300 seconds;
- broker-bound;
- environment-bound;
- action-bound to `LIVE_EXECUTE`;
- single-use through the registry;
- revocable;
- persisted without extending original expiry;
- fail-closed when durable state is ambiguous.

Phase 189 `READ_ONLY_OPERATIONAL` TTL remains separate and cannot satisfy this
live-execution lease.

Credentials, authentication, connectivity, market data, runtime startup, and
operator intent do not themselves create execution authority.

All pre-existing live-authority conditions remain mandatory, including
AntiBleedGuard, Margin Gate, Unified Trade Gate, capital governor, RBAC,
kill-switch clearance, pilot arming, and GO/NO-GO.

## Safety posture

- No broker authentication.
- No broker contact.
- No secret access.
- No order submission.
- No CSS restart.
- No freeze SHA.
- No founder GO.
- No live trading authorization.

Remaining Phase 196 blockers include controlled online FX certification,
controlled online microstructure certification, DIP live readiness resolution,
fresh controlled OANDA/Coinbase read-only revalidation, final pre-freeze
validation, freeze designation, and founder GO/NO-GO.