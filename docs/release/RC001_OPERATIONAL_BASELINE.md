# RC-001 Operational Baseline

**Programme:** CSS Version 1 — Release Candidate RC-001  
**Captured:** 2026-07-22T03:46:53Z (post-start health stamp)  
**Authority:** Repository + live Desktop runtime observations only  
**Constraints observed:** No OAT · No 72h endurance · No broker operational validation · No live trading enablement

---

## Repository

| Field | Value |
| --- | --- |
| **Commit SHA** | `6513e6a1e45ffc42aff192e1c784171ad6fc182b` |
| **Branch** | `css-unified-consolidation-2026-07-13` |
| **Remote** | `origin/css-unified-consolidation-2026-07-13` (pushed) |
| **Commit timestamp** | `2026-07-21 23:39:09 -0400` |
| **Sync timestamp (UTC)** | `2026-07-22T03:42:18Z` |
| **Dependencies** | `pip install -r backend/requirements.txt` exit **0** |
| **Worktree (committed)** | Clean for RC-001 SHA; untracked local noise only (`pytest_*.txt`, diagnostics dumps) |

---

## Startup

| Field | Value |
| --- | --- |
| **Startup procedure** | `launch_css.bat` (standard; no `CSS_AUTOMATED_INPUT`; no live-trading env flags) |
| **Primary surface after start** | `launcher.css_mobile_launcher` on port **8765** |
| **Startup time (health stamp)** | `2026-07-22T03:46:53Z` |
| **Evidence** | `artifacts/_rc001_sync.txt`, `artifacts/_rc001_post_start_health.json`, `artifacts/_rc001_surface_probes.txt` |

---

## Runtime

| Field | Observed |
| --- | --- |
| **Runtime mode** | `DISABLED` |
| **Readiness / fail-closed** | `fail_closed=true` (`incomplete_startup_information` / empty context) |
| **Backend status** | **ONLINE** — `GET /health` → `healthy` (`css_mobile_launcher`) |
| **Supervisor status** | Launcher-managed restart path used; service healthy on 8765 (dedicated `/ops/health` **404** on this surface — not claimed as ops-host ACTIVE) |
| **Heartbeat / telemetry** | `GET /api/runtime-telemetry` → **200** (schema present) |
| **Broker status** | Live execution **BLOCKED**; credentials not present / not authenticated; Options Income `ADVISORY_ONLY` / `DATA_DEPENDENCY_BLOCKED` |
| **Health status** | **healthy** |

---

## Surfaces

| Surface | Result |
| --- | --- |
| Mobile Dashboard | **Reachable** — `GET /` 200 (CSS Mobile Launcher); `manifest.json` 200 |
| Mission Control | **Reachable** — `GET /mission-control` **303** (redirect) |
| Executive / OI APIs | **Operational (advisory)** — `/api/options-income/status` 200; `/api/runtime-mode` 200; `/api/v1/live-execution-authority` 200 |
| Ports 8090 / 8000 | Not listening (not required for this RC-001 surface) |

---

## Operational safety

| Control | Confirmation |
| --- | --- |
| **Advisory-only** | **Confirmed** — `advisory_only=true` on runtime-mode and live-authority payloads |
| **Live trading blocked** | **Confirmed** — `live_trading_enabled=false`; `can_live_execute=false`; `execution_allowed=false`; `live_authority_state=BLOCKED` |
| **Fail-closed preserved** | **Confirmed** — `fail_closed=true`; resolution `fail_closed:empty_context` |
| **Broker safety** | **Confirmed** — execution authority false; failed conditions include credentials/auth/connected/broker_execution_enabled |
| **Production certification** | Phase 181 **`NOT_CERTIFIED`** · Batch 2 decision **CERTIFIABLE AFTER OPERATIONAL VALIDATION** |
| **Commercial readiness** | **NO-GO** |

### Honesty note (non-blocking)

`operator_requested_live=true` appears in the live-execution-authority payload while all execution gates remain false and authority remains **BLOCKED**. RC-001 does not treat this as live enablement. Operators should clear any stale live-request intent before Operational Validation scenarios that inspect authority JSON.

---

## Certification / readiness snapshot

| Metric | Value |
| --- | --- |
| Phase 181 | `NOT_CERTIFIED` |
| Gate 2 engineering | Substantially complete (RC-001) |
| Production readiness | **NO-GO** (pending Operational Validation) |
| Commercial readiness | **NO-GO** |

---

*End of RC001_OPERATIONAL_BASELINE.md*
