# CSS v1.0.1 — Maintenance Workstream 002
## RR-002 Mission Control `broker_state_not_green` / Active Broker Projection

**Programme:** CSS v1.0.1 Maintenance
**Workstream:** MW-002 / RR-002
**Status:** IMPLEMENTED — VALIDATED — AWAITING COMMIT APPROVAL
**Workspace:** Laptop (`C:\rasib\source\capital-strata-systems`)
**Branch:** `css-v1.0.1-maintenance`
**HEAD (base, verified pre-implementation):** `7253dbc194809dcf3a09081e1b7a3fd3e57c1b86`
**Date:** 2026-07-29 / 2026-07-30
**Does not authorize:** live trading, OV-002, production deployment, desktop interference

---

## 1. Executive summary

RC-003R FINAL reported Mission Control health **AMBER** with reason `broker_state_not_green` while runtime mode was **PAPER**, live authority **BLOCKED**, and paper orders succeeded via CSS_PAPER / OANDA Practice market data.

Audit confirmed: `build_health_summary` correctly AMBER’d when **projected** `active_broker.connection_status` was FAIL, but the projected active broker was stale **COINBASE / live / FAIL**, not the campaign paper/practice broker.

**Root cause (confirmed):** Mission Control active-broker projection followed runtime/startup `selected_broker` without aligning to the current runtime profile (PAPER). Inactive / disabled live brokers could drive overall readiness colour.

**Implementation:** Profile-aligned active-broker projection in Mission Control. Inactive broker FAIL remains advisory in `broker_list`. True active FAIL still AMBER. Safety / live-authority flags unchanged (fail-closed).

**Recommendation:** **READY_TO_COMMIT**

---

## 2. Confirmed root cause

| Finding | Detail |
| --- | --- |
| Classification | **H. Mixed** — health rule correct for projected input; **projection misaligned** with PAPER campaign |
| Path | runtime snapshot / broker section → `contracts._brokers` → `health.build_health_summary` → `/mission-control/api/health` |
| RC-003R projection | `active_broker=COINBASE`, `broker_mode=live`, `connection_status=FAIL` while `runtime_mode=PAPER` |
| Not the bug | Forcing GREEN; weakening authority; adapter failure of a truly active broker |

Confirmed by audit evidence + deterministic remapping matrix in this workstream.

---

## 3. Implementation

### Behaviour

1. When `runtime_mode` is PAPER (practice/demo equivalents) and projected selection is a **stale live Tier-1** broker (e.g. COINBASE live FAIL), remapping sets `active_broker` to the campaign paper/practice broker (`campaign_broker` / OANDA practice / default **CSS_PAPER**).
2. Superseded selection retained as `inactive_projected_broker` and annotated on `broker_list` (selected=false, advisory FAIL visible).
3. Compatible selections (CSS_PAPER, PAPER/NONE/DEMO, OANDA/Coinbase in paper/practice mode) are unchanged — true active FAIL still yields AMBER.
4. Health reasons: keep `broker_state_not_green`; add `active_broker_fail:<NAME>`, `active_broker_degraded:<NAME>`, `active_broker_missing`. DEGRADED maps to AMBER.
5. Platform `selected_broker` uses the same projection helper for consistency.
6. Health payload still forces: `execution_allowed=false`, `live_trading_blocked=true`, `broker_execution_armed=false`, `advisory_only=true`.

### Out of scope (preserved)

- Broker adapters, credentials, runtime startup, orchestrator, thresholds, Anti-BleedGuard, execution authority, desktop CSS runtime.

---

## 4. Files changed

| File | Change |
| --- | --- |
| `dashboard/mission_control/active_broker_projection.py` | **New** — profile alignment, inactive annotation, canonical status mapping |
| `dashboard/mission_control/contracts.py` | `_brokers` / `_platform` use projection + annotated registry |
| `dashboard/mission_control/health.py` | Broker-qualified reasons; DEGRADED→AMBER; missing active broker |
| `tests/test_mw002_active_broker_projection.py` | **New** — MW-002 deterministic matrix |
| `docs/governance/CSS_V1_0_1_MAINTENANCE_002_BROKER_STATE_AUDIT.md` | This record |

---

## 5. Tests added

`tests/test_mw002_active_broker_projection.py`:

1. Active OANDA Practice READY + inactive Coinbase FAIL → GREEN overall
2. Active OANDA FAIL → AMBER + `active_broker_fail:OANDA`
3. No active broker → AMBER + `active_broker_missing`
4. Multiple brokers / one active drives health
5. Mission Control reason-code projection
6. Canonical broker-state mapping (PASS/FAIL/DEGRADED)
7. Live-authority flags remain fail-closed on GREEN health
8. Full MC state: PAPER + stale COINBASE live FAIL remaps to OANDA practice READY; Coinbase remains unselected advisory

---

## 6. Validation results

| Suite | Result |
| --- | --- |
| `git diff --check` | PASS |
| `tests/test_mw002_active_broker_projection.py` | **12 passed** |
| MC foundation / live / runtime snapshot / mc007b | **PASS** |
| `tests/test_phase153i_live_execution_authority.py` | **PASS** |
| `tests/test_phase153c_broker_regression_startup_flow.py` | **PASS** |
| `tests/test_broker_registry.py` + kill-switch paper path | **PASS** |
| phase177c / phase178b excluding env-sensitive `resolve_runtime_mode()==DISABLED` | **PASS** (see limitations) |

Desktop CSS: **not accessed / not started / not stopped**.

---

## 7. Safety verification

- Health and broker safety blocks remain fail-closed.
- No execution arming, no live authority grant, no credential/adapter/startup changes.
- Inactive Coinbase FAIL does not suppress a true active-broker FAIL.

---

## 8. Live-authority verification

- `test_phase153i_live_execution_authority.py` passed.
- MW-002 GREEN cases assert `execution_allowed=false`, `live_trading_blocked=true`, `broker_execution_armed=false`.
- **LIVE_TRADING_NOT_AUTHORIZED** unchanged.

---

## 9. Remaining limitations

1. Remapping is Mission Control projection-layer only; startup diagnostics / launcher artifacts may still list a stale `selected_broker` until a separate upstream cleanup (out of MW-002 bound).
2. Default remapping target is **CSS_PAPER** when no `campaign_broker` / practice evidence is present.
3. Local env may set runtime mode to PAPER, causing pre-existing tests that assert `resolve_runtime_mode() == DISABLED` to fail outside clean CI — **not caused by MW-002**.
4. Upstream artifact selection alignment remains optional follow-on.

---

## 10. Rollback

Revert MW-002 commit(s) on `css-v1.0.1-maintenance`. No schema migration.

---

## 11. Final recommendation

**READY_TO_COMMIT**

Do not push until explicit approval. Do not start CSS. Do not touch desktop.

---

*End of CSS_V1_0_1_MAINTENANCE_002_BROKER_STATE_AUDIT.md*
