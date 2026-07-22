# Wave 2 — Consolidated Root Cause Analysis

**Programme:** Release Gate 2  
**Batch:** Wave 2 — Security & Broker Integrity  
**Scope:** AR-023, AR-024, AR-025, AR-026, AR-028, AR-029, AR-030, AR-031, AR-032, AR-033  
**Date:** 2026-07-21  
**Checkpoint:** `RG2_CHECKPOINT_001`

## Shared theme

Development and local-operator conveniences (default passwords, open LAN mutations, writable broker adapters, unwired ops/metrics, dual install surfaces, legacy credential dictionaries) were left on paths that Gate 2 must treat as **production-boundary surfaces**. Shared corrective principle: **fail-closed honesty** — remove defaults, quarantine writes, require configuration, demote incomplete activation claims.

## Shared architectural causes

| Cluster | ARs | Cause |
| --- | --- | --- |
| Identity & API boundary | 023, 024, 025 | Auth defaults + multi-host mutations + HTTP PWA without secure-context honesty |
| Broker write surface | 026, 032, 033 | Legacy executable adapters + env aliases + plaintext credential loaders coexist with read-only/lease authorities |
| Ops telemetry activation | 028, 029, 030 | Frameworks exist in tests only; empty/local files mistaken for production monitoring |
| Advisory data honesty | 031 | Engine complete; providers empty — must not fabricate readiness |

## Common security weaknesses

1. Hardcoded bootstrap credentials (`00000` / `123456`).
2. Unauthenticated mutation routes on LAN-bound launcher / headless engine.
3. In-memory sessions and cookie auth without CSRF synchronizer on HTTP.
4. Secure cookie flags absent on non-HTTPS.
5. Automated auth bypass env usable outside test profile.

## Common broker integrity issues

1. `OandaAdapter` retains POST/PUT/close while read-only adapter exists.
2. Live-enable aliases / truthy flags can confuse profiles (bootstrap partially mitigates).
3. Legacy `load_credentials` plaintext still on active paths beside vault/handles.
4. Options income correctly blocked but activation incomplete — honesty must stay explicit.

## Smallest coherent remediation set

1. **AR-023:** Require bootstrap secret env; remove hardcoded password; strengthen min length; secure cookies when HTTPS/forced; gate automated bypass.
2. **AR-024:** Auth-gate launcher + headless mutations; durable mobile sessions; CSRF header check; localhost vs LAN profile honesty.
3. **AR-025:** Declare canonical PWA identity; document HTTPS/secure-context; label launcher manifest non-canonical (docs + manifest markers).
4. **AR-026:** Quarantine OANDA write methods fail-closed; tests prove denial.
5. **AR-032:** Ensure bootstrap live-flag force-false + remove/narrow dangerous aliases; tests green (commit readiness).
6. **AR-033:** Fail-closed demote live plaintext credential load for production/live-read profiles; certification stays NOT_CERTIFIED while legacy active.
7. **AR-028:** Required checkers; empty → CRITICAL; wire into one canonical host activation helper.
8. **AR-029:** Periodic/host `persist_snapshot` + redaction; restart-survivable history.
9. **AR-030:** Single alert query authority + wire retention purge; docs: local ≠ production pager.
10. **AR-031:** Enforce empty-registry → `DATA_DEPENDENCY_BLOCKED` + `execution_allowed=False`; no fake data.

## Expected closure posture

| AR | Expected recommendation |
| --- | --- |
| 023, 024, 026, 028 | CLOSE (or CLOSE with residual test-profile notes) |
| 025 | CLOSE (docs + canonical identity; physical Android checklist documented) |
| 029, 030 | CLOSE for persistence/retention honesty; external backends remain future |
| 031 | CLOSE for advisory honesty; provider activation remains AR-040/033 residual |
| 032 | CLOSE if bootstrap + alias tests land; else PARTIALLY CLOSE |
| 033 | PARTIALLY CLOSE if full vault migration incomplete — fail-closed demotion lands |

## Safety constraints

- No live trading enablement.
- No new broker write capability.
- No fabricated options market data.
- No Wave 3 evidence/OAT work in this batch.
