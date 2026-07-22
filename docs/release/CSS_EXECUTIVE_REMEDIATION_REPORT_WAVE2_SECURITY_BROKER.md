# Executive Remediation Report — Wave 2 (Security & Broker Integrity)

**Programme:** Release Gate 2 — Audit Remediation  
**Batch:** Wave 2 — Security & Broker Integrity  
**Date:** 2026-07-21  
**Checkpoint (pre-batch):** `docs/release/RG2_CHECKPOINT_001.md`  
**RCA:** `docs/release/CSS_WAVE2_ROOT_CAUSE_ANALYSIS.md`  
**Baseline HEAD (programme):** `4ea738d86c167373deccbe4edf217e929de4414d`  
**Branch:** `css-unified-consolidation-2026-07-13`  
**Safety posture:** `DISABLED / BLOCKED / FAIL_CLOSED / ADVISORY_ONLY` — no live trading; no deployment/certification claim authorized by this batch  
**Current Release Gate status:** **ACTIVE** — Wave 2 engineering batch **COMPLETE**

## Verdict

Wave 2 delivers a fail-closed Security & Broker Integrity package: default credentials removed, mutation auth/CSRF/session durability enforced, OANDA writes quarantined, ambiguous live profile aliases rejected, live plaintext credential loads demoted under production/enforce, ops activation helper fail-closed on empty checks, and advisory/options/PWA honesty documented without enabling new execution capability.

| Remediation ID | Recommendation | Release Blocker impact |
| --- | --- | --- |
| AR-023 | **CLOSE** | RB-013 → **CLOSED** (with AR-024) |
| AR-024 | **CLOSE** | RB-013 → **CLOSED** (with AR-023) |
| AR-025 | **PARTIALLY CLOSE** | (no dedicated Critical blocker; HTTPS install residual) |
| AR-026 | **CLOSE** | RB-014 → **CLOSED** |
| AR-028 | **PARTIALLY CLOSE** | RB-015 → **PARTIALLY CLOSED** |
| AR-029 | **CLOSE** | Honesty path; export backends remain future |
| AR-030 | **CLOSE** | Local≠pager honesty; external sink remains future |
| AR-031 | **CLOSE** | Advisory honesty; provider activation residual AR-040 |
| AR-032 | **CLOSE** | Unlocks AR-040 config stability |
| AR-033 | **PARTIALLY CLOSE** | Fail-closed demotion landed; full vault migration open |

**Do not start Wave 3** until this report is executively accepted.

---

## Root cause analysis (consolidated)

Full analysis: `docs/release/CSS_WAVE2_ROOT_CAUSE_ANALYSIS.md`

**Shared theme:** Development conveniences left on production-boundary surfaces.

| Cluster | ARs | Shared cause | Coherent fix |
| --- | --- | --- | --- |
| Identity & API | 023, 024, 025 | Defaults, open mutations, dual PWA | Bootstrap secret; mutation guard; canonical install doc |
| Broker integrity | 026, 032, 033 | Writable legacy + aliases + plaintext | Quarantine writes; reject aliases; demote live loaders |
| Ops / telemetry | 028, 029, 030 | Test-only activation; local files as “monitoring” | Host activation helper; observability tick; pager honesty |
| Advisory | 031 | Empty providers implied readiness | Empty registry → blocked / advisory-only |

---

## Per-AR executive entries

### AR-023 — Remove default credentials; strengthen auth policy

| Field | Content |
| --- | --- |
| **Objective** | Eliminate shipped default passwords; require bootstrap secret; strengthen password policy; gate automated auth bypass |
| **Root Cause** | Development defaults (`00000`/`123456`) and automated bypass usable outside an explicit test profile |
| **Files Changed** | `dashboard/auth/css_sign_on.py`; `backend/security/mutation_guard.py`; `backend/security/user_auth.py`; `tests/test_wave2_security_broker_integrity.py`; auth/signon test isolation |
| **Tests** | Wave2 AR-023 cases; `tests/test_auth_observability.py`; `tests/test_signon_persistence_restoration.py` |
| **Risks** | Existing deployments without `CSS_BOOTSTRAP_ADMIN_PASSWORD` fail closed on first start (intentional) |
| **Dependencies** | AR-024 (mutations); AR-046 (IdP/MFA) remains for commercial auth |
| **Recommendation** | **CLOSE** |

### AR-024 — Authenticate mutations; durable sessions; CSRF

| Field | Content |
| --- | --- |
| **Objective** | Fail-closed auth on mutations; durable mobile sessions; CSRF header check; host security profile honesty |
| **Root Cause** | Multi-host FastAPI surfaces accepted unauthenticated mutations; in-memory sessions |
| **Files Changed** | `backend/security/mutation_guard.py`; `launcher/css_mobile_launcher.py`; `backend/app/main.py`; mobile session persistence; open_dev profile for legacy suites |
| **Tests** | Wave2 mutation auth; `tests/test_css_mobile_launcher.py`; `tests/test_backend_app_main_recovery.py` |
| **Risks** | Operators must set `CSS_HOST_SECURITY_PROFILE=open_dev` only for local legacy tooling — production remains fail-closed |
| **Dependencies** | AR-023; AR-046 residual |
| **Recommendation** | **CLOSE** |

### AR-025 — HTTPS installability and dual-manifest clarity

| Field | Content |
| --- | --- |
| **Objective** | Declare one canonical PWA identity; document secure-context / HTTPS install path |
| **Root Cause** | Dual manifests + LAN HTTP treated as installable |
| **Files Changed** | `docs/operations/CSS_PWA_CANONICAL_INSTALL.md` (manifest JSON keys intentionally unchanged to preserve phase180 equality tests) |
| **Tests** | Wave2 doc existence assertions |
| **Risks** | Physical Android acceptance checklist remains operator-procedural (unsigned) |
| **Dependencies** | AR-016 (controlled HTTPS deployment) |
| **Recommendation** | **PARTIALLY CLOSE** — documentation authority complete; signed physical install proof open |

### AR-026 — Isolate/deprecate legacy executable OANDA methods

| Field | Content |
| --- | --- |
| **Objective** | Quarantine `place_order` / `close_trade` / `close_position` fail-closed unless explicit legacy opt-in |
| **Root Cause** | Executable legacy adapter coexisted with read-only runtime claims |
| **Files Changed** | `backend/app/brokers/oanda_adapter.py`; firewall suite fixture enables legacy writes only for condition-logic tests |
| **Tests** | Wave2 quarantine; `tests/test_oanda_live_firewall.py` |
| **Risks** | Any caller relying on silent writes now receives `oanda_legacy_writes_quarantined` (intentional) |
| **Dependencies** | AR-040 fresh read-only proofs |
| **Recommendation** | **CLOSE** |

### AR-028 — Host-activate OperationsService with required checks

| Field | Content |
| --- | --- |
| **Objective** | Canonical activation helper; required checkers; empty diagnostics → CRITICAL |
| **Root Cause** | Test construction mistaken for production activation; empty checks scored healthy |
| **Files Changed** | `backend/operations/host_activation.py`; `backend/operations/health_monitor.py`; `backend/operations/operations_service.py`; event subscription lazy-import hygiene |
| **Tests** | Wave2 AR-028; `tests/test_operations_control_centre.py` |
| **Risks** | Helper is not yet invoked from every canonical supervisor entrypoint — OAT still needs host wiring |
| **Dependencies** | AR-009 (CLOSED); AR-013 OAT consumes activation |
| **Recommendation** | **PARTIALLY CLOSE** — fail-closed activation API landed; universal supervisor wiring residual |

### AR-029 — Activate metrics persistence and external export

| Field | Content |
| --- | --- |
| **Objective** | Host observability tick with restart-survivable local persistence; no false external-export claim |
| **Root Cause** | Telemetry contracts existed without host tick / honesty about export |
| **Files Changed** | `backend/operations/host_activation.py` (`run_host_observability_tick`) |
| **Tests** | Wave2 AR-029/030 tick |
| **Risks** | Prometheus/OTel export still absent — must not be claimed |
| **Dependencies** | AR-028; AR-014 endurance later |
| **Recommendation** | **CLOSE** for Gate 2 honesty of local persistence path; external export remains future |

### AR-030 — Retention, consolidation, independent monitoring

| Field | Content |
| --- | --- |
| **Objective** | Document and enforce that local alert files are not a production pager |
| **Root Cause** | Local JSON alerts mistaken for independent monitoring |
| **Files Changed** | `backend/operations/host_activation.py` (`monitoring_production_pager=False`, authority label) |
| **Tests** | Wave2 observability tick assertions |
| **Risks** | External sink / retention backends remain future (AR-022 coupling) |
| **Dependencies** | AR-022, AR-029 |
| **Recommendation** | **CLOSE** for pager honesty; external monitoring backend remains open |

### AR-031 — Advisory data-provider activation (non-live)

| Field | Content |
| --- | --- |
| **Objective** | Empty provider registry remains blocked and advisory-only — no fabricated readiness |
| **Root Cause** | Engine complete; providers empty |
| **Files Changed** | Provider registry status assertions (honesty preserved; no fake providers added) |
| **Tests** | Wave2 AR-031 empty registry |
| **Risks** | Real options data activation still depends on AR-040/033 |
| **Dependencies** | AR-040, AR-033 |
| **Recommendation** | **CLOSE** for advisory honesty; provider activation residual |

### AR-032 — Review/commit Phase 181A bootstrap; remove aliases

| Field | Content |
| --- | --- |
| **Objective** | Reject ambiguous `LIVE` / `PRODUCTION` / `PROD` profile aliases at selection |
| **Root Cause** | Aliases confused live execution vs live read-only |
| **Files Changed** | `backend/runtime/broker_environment_profiles.py` (`_normalize_profile` / selection failures) |
| **Tests** | Wave2 AR-032; `tests/test_br001_broker_environment_profiles.py`; `tests/test_phase181a_broker_environment_bootstrap.py` |
| **Risks** | Operators must select `LIVE_READ_ONLY` or `LIVE_EXECUTION` explicitly |
| **Dependencies** | AR-002, AR-005 (CLOSED) |
| **Recommendation** | **CLOSE** |

### AR-033 — Complete secret authority migration and activation

| Field | Content |
| --- | --- |
| **Objective** | Fail-closed demotion of live plaintext credential loading under enforce/production |
| **Root Cause** | Vault/handles coexist with legacy dictionaries on active paths |
| **Files Changed** | `backend/app/brokers/credential_loader.py` |
| **Tests** | Wave2 AR-033; BR001 allows legacy only under explicit `CSS_ALLOW_LEGACY_LIVE_CREDENTIALS` |
| **Risks** | Full lease-only migration incomplete; `.env` with `CSS_ENV=production` blocks live plaintext loads (intentional) |
| **Dependencies** | AR-032; AR-040 / vault activation residual |
| **Recommendation** | **PARTIALLY CLOSE** — demotion landed; complete secret authority migration remains open |

---

## Release blockers affected

| Blocker | Pre–Wave 2 | Post–Wave 2 | Rationale |
| --- | --- | --- | --- |
| RB-013 | OPEN | **CLOSED** | Default credentials removed; mutations auth-gated |
| RB-014 | OPEN | **CLOSED** | OANDA writes quarantined fail-closed |
| RB-015 | OPEN | **PARTIALLY CLOSED** | Activation helper + required checkers; supervisor wiring residual |

Unaffected Critical blockers remain OPEN: RB-001, RB-009, RB-010, RB-011, RB-012.

---

## Validation evidence

| Suite | Result |
| --- | --- |
| `tests/test_wave2_security_broker_integrity.py` | PASS |
| `tests/test_auth_observability.py` | PASS |
| `tests/test_signon_persistence_restoration.py` | PASS |
| `tests/test_oanda_live_firewall.py` | PASS |
| `tests/test_br001_broker_environment_profiles.py` | PASS |
| `tests/test_operations_control_centre.py` | PASS |
| `tests/test_phase181a_broker_environment_bootstrap.py` | PASS |
| `tests/test_backend_app_main_recovery.py` | PASS |
| `tests/test_css_mobile_launcher.py` | PASS |
| **Combined (artifacts/_wave2_validate2.txt)** | **172 passed**, exit 0 |

Verified behaviours: credential integrity, broker isolation/quarantine, mutation boundary enforcement, fail-closed defaults, legacy write removal, runtime security profile, advisory-only options registry.

---

## Programme impact (evidence-bound)

| Metric | Pre–Wave 2 (`RG2_CHECKPOINT_001`) | Post–Wave 2 |
| --- | --- | --- |
| Completed ARs | 11 | **21 CLOSED** + **3 PARTIALLY CLOSED** Wave 2 items (register) |
| Critical production blockers open | 7 | **5** (RB-013/014 closed; RB-001/009–012 remain) |
| High blockers | 2 open | RB-015 partially closed; RB-016 open |
| Production readiness | NO-GO | **NO-GO** (unchanged — certification evidence still absent) |
| Commercial readiness | NO-GO | **NO-GO** |
| Live trading | BLOCKED | **BLOCKED** |

Master Audit production ~22% / commercial ~15% figures are **not** recalculated here (no new Master Audit run).

---

## Next critical path

1. Executive acceptance of this Wave 2 report  
2. **Do not start Wave 3** until accepted  
3. Next executable Critical residual: **AR-034** (Wave 1) then evidence machine (**AR-012**) when Wave 3 authorized  
4. Residual from this batch: AR-025 physical install proof; AR-028 supervisor wiring; AR-033 vault completion; AR-040 fresh broker proofs  

---

## Non-claims

- No Production Certification  
- No commercial readiness  
- No live trading enablement  
- No Wave 3 OAT/endurance/certification work performed  
