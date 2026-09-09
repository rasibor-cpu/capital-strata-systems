# CSS Session 8 Certification Manifest

Status: read-only evidence captured during Session 8

## Repository

- Branch: `css-com002c-performance-accounting`
- Session 8 base HEAD: `2502e29d`
- Runtime state: `runtime_supervisor.json` is runtime-only and untracked
- Execution posture: advisory-only; execution remains blocked and unarmed

## Collection Evidence

- Full pytest collection: PASS (`COLLECTION_EXIT=0`)
- Tests collected: 1,768
- Full suite: 1,768 passed, 0 failed, 49 warnings
- Formerly blocked modules: 13 passed
- Dashboard suite: 114 passed, 2 pre-existing deprecation warnings
- Session 6/7 and client economics regressions: 37 passed
- Collection debt repaired: unused `bs4` import removed; historical read-only `backend.data.price_feed` contract restored
- Full-suite execution: PASS; the slippage-protection test completed during the full run

## Broker Decision

| Broker | Classification | Evidence and blockers |
| --- | --- | --- |
| OANDA | LAUNCH_SUPPORTED | Registered adapter, paper/live metadata, execution-gate coverage, credentials fail closed when absent |
| Coinbase | LAUNCH_SUPPORTED | Registered adapter, paper/live metadata, crypto adapter and margin/read-only coverage, credentials fail closed when absent |
| Questrade | READ_ONLY_SUPPORTED | Account-state parser and activity reconciliation only; no order adapter, no live execution authority, real-account validation pending |
| IBKR | PAPER_ONLY | Adapter/runtime manager expose connectivity and empty snapshots; no complete order path or live certification |
| Alpaca | UNSUPPORTED | Registry metadata exists, but no registered adapter path or certification evidence |

Launch-supported broker scope is OANDA and Coinbase. Questrade is available only for read-only evidence and account-state inspection. IBKR and Alpaca are not production launch brokers.

## Credential and Security Evidence

- Credentials are loaded from broker-specific files or environment variables.
- Missing or malformed credentials fail closed.
- Credential values are not emitted by the loader or certification payloads.
- No real credentials were added or rotated.
- Synthetic credentials remain limited to test fixtures.

## Outstanding Validation

- Questrade real-account read-only validation remains pending because credentials/provider access is unavailable.
- Full-suite execution result must be recorded after the final Session 8 regression run.
- No live-funded execution authority is certified by this artifact.