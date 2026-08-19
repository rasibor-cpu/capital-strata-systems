# CSS-CONSOL-CERT-001 — Post-Merge Certification and Backlog Consolidation

**Task ID:** `CSS-CONSOL-CERT-001`  
**Date (UTC):** 2026-08-19  
**Pass type:** Read-only certification + documentation backlog reconciliation  
**Canonical base:** `css-v1.0.1-maintenance`  
**Verified HEAD:** `fc7a6c99b4c547df653d5668458b7803f1789c34`  
**Evidence branch:** `css-consol-cert-001`  
**Live trading authority:** NONE  
**Runtime/code mutation:** NONE  

This record is the authoritative post-merge certification and backlog-reconciliation result after TAI-001, TAI-002, Autonomous Supervisor restoration, MI-EXT-001 R2, and RC-LIVE-CONSOL-001 (185A/186A/187A offline). It does **not** grant production certification, live trading, broker execution, or new live ingestion.

Where older STATUS notes, draft-PR language, or historical RC scorecards conflict with this page for *task lifecycle / merge state / remaining work*, **this page prevails**. Production-certification authority remains `docs/release/CSS_CANONICAL_RELEASE_STATUS.md` and Phase 181 `NOT_CERTIFIED`.

---

## A. Verified canonical HEAD

| Check | Result |
| --- | --- |
| `git fetch origin` | Performed |
| `origin/css-v1.0.1-maintenance` | `fc7a6c99b4c547df653d5668458b7803f1789c34` |
| Required HEAD | Match — **no stop** |
| Tip commit | `Merge PR #60: consolidated offline market readiness recovery` |
| Working tree at verification | Clean |
| GitHub default branch | `main` @ `faf1485dd88d7056bbd8f7f891cb47caf7685603` (Phase 113Y) — **stale vs maintenance** |

Landed merges on this HEAD:

| PR | Title | Merged into maintenance |
| --- | --- | --- |
| #53 | TAI-001 | yes |
| #55 | AOD-001 | yes |
| #57 | TAI-002 R2 | yes |
| #58 | RC-LIVE-W1-001 Autonomous Supervisor | yes |
| #59 | MI-EXT-001 R2 | yes |
| #60 | RC-LIVE-CONSOL-001 offline market readiness | yes |

`agent_tasks/STATUS.md` at this HEAD still described #58 / #60 as unmerged drafts. That description is **false as of `fc7a6c99`**. Lifecycle cleanup is Package D.

---

## B. Post-merge regression totals

Environment: Cloud Agent Python 3.12, **`python-dotenv` not installed**. Declared dependency `python-dotenv==1.2.2` in `requirements.txt` was **not** installed (governance: this pass does not install dependencies).

Broadest **safe** offline set practical here, **without** broker credentials, funded sessions, live network, or live orders.

### Executed totals (JUnit, one combined run)

| Metric | Count |
| --- | --- |
| Passed | **480** |
| Failed | **50** (none suppressed) |
| Skipped | **0** |
| Warnings | **1** (Starlette TestClient / httpx vs httpx2 deprecation) |
| Collection errors | **15 files** (~269 `def test_*` not executed) |
| Full-repo suite (~3700) | **not run** — not practical without dotenv + would pull live/launcher paths |

### Clean groups (all passed)

#### Intelligence — 104 passed / 0 failed

| Suite | Passed |
| --- | --- |
| TAI-001 `tests/test_tai001_technical_intelligence.py` | 11 |
| TAI-002 `tests/test_tai002_technical_intelligence_integration.py` | 14 |
| MI-EXT provenance | 14 |
| MI-EXT hardening | 11 |
| MI-EXT recovery R2 | 22 |
| Autonomous opportunity intelligence | 2 |
| Opportunity ranking | 10 |
| Market regime engine | 3 |
| Market regime intelligence | 4 |
| Intelligence orchestrator | 8 |
| Autonomous supervisor | 5 |

#### Mission Control (non-launcher) + offline market — 114 passed / 0 failed / 1 warning

| Suite | Passed |
| --- | --- |
| mc001 foundation | 12 |
| mc005 operations command center | 12 |
| mc006 decision intelligence | 8 |
| mc007a institutional intelligence | 8 |
| mc007b secure operations | 8 |
| mc007c production hardening | 5 |
| Phase 185A market/FX contracts | 13 |
| Phase 186A offline providers | 15 |
| Phase 187A OANDA read-only cert framework (offline) | 22 |
| RC-LIVE-CONSOL-001 isolation | 11 |

mc002 / mc003 / mc004 **did not collect** (dotenv / launcher import boundary). Required intelligence observability for this pass is covered by mc001 / mc006 / mc007a.

#### Safety / execution isolation — 146 passed in the core safety batch; plus 28 dashboard/margin controls in the combined JUnit

| Suite | Passed |
| --- | --- |
| Unified Trade Gate asset-class normalization | 5 |
| Dashboard trade-gate migration | 17 |
| Dashboard trade-gate freeze | 5 |
| AntiBleed guard integration | 7 |
| Capital allocation engine | 8 |
| Margin trade gate | 9 |
| Margin trade gate enforcement | 6 |
| Margin snapshot | 1 |
| Margin dashboard integration | 7 |
| Live authorization TTL (60s consume-once) | 33 |
| Regime-aware weighting | 7 |
| Phase 154A broker-readiness framework | 3 |
| Engine live-order kill switch | 3 |
| Web kill-switch governance | 34 |
| Risk governor | 8 |
| CSS mobile controls (no launcher dotenv path) | 21 |

#### Other executed production-readiness that passed

| Suite | Passed |
| --- | --- |
| LDT-001 charter | 13 |
| LDT-002 (except stale ancestor test) | 7 |
| Canonical execution integration | 12 |
| RC1 readiness | 5 |
| DIP-004 / DIP-005 / DIP-006 | 17 / 10 / 6 |
| Trade-decision orchestrator gate | 1 |
| Security phase alpha (non-OANDA-constructor tests) | 6 |
| OV-002 endurance (subset that did not hit identity probe) | 3 |
| OV-002 R1 continuity (subset) | 7 |
| MR-001 (one remaining historical check) | 1 |

---

## C. Failing / blocked suites

Failures are recorded, not suppressed. None are treated as TAI / MI-EXT / CONSOL product regressions.

### C1. STALE TEST (canonical HEAD is now maintenance)

| Test | Why it fails on `fc7a6c99` | Classification |
| --- | --- | --- |
| `test_ldt002_non_ancestor_certification_cannot_be_silently_credited` | Asserts `9a9263c1` is **not** an ancestor of HEAD. On current maintenance it **is**. Test was written for `css-unified-consolidation-2026-07-13` @ `66e11d4f`. | STALE TEST |
| `tests/test_mr001_branch_consolidation_plan.py` (5 failed) | Frozen SHAs (`66e11d4f`, local branch name without `origin/`, “maintenance artifacts absent”). HEAD is maintenance; plan is historical. | STALE TEST |

### C2. TEST ENVIRONMENT GAP — OV-002 identity probe (12 failed)

`ContinuityError: identity_probe_incomplete:creation_time,executable_path,executable_sha256`

| Suite | Failed | Passed |
| --- | --- | --- |
| `tests/test_ov002_endurance_monitor.py` | 7 | 3 |
| `tests/test_ov002_r1_continuity_remediation.py` | 5 | 7 |

This cloud/restricted process view cannot fill live identity fields. **Not** a merge breakage of intelligence or offline market packages. Historical OV-002 72h run remains `ENDURANCE INVALIDATED` (`docs/release/CSS_OV002_72H_ENDURANCE_REPORT.md`).

### C3. TEST ENVIRONMENT GAP + import boundary — dotenv at runtime (32 failed)

| Suite | Failed | Notes |
| --- | --- | --- |
| `tests/test_oanda_live_firewall.py` | 30 | Collects; `OandaAdapter()` imports `credential_loader` → `dotenv` |
| `tests/test_security_phase_alpha.py` (OANDA firewall cases) | 2 | Same constructor path |

**LIVE-ONLY / broker-adjacent.** Firewall logic is **unproven in this environment**, not demonstrated broken.

### C4. Collection ERROR — dotenv at import (15 files, ~269 tests not run)

| File | Approx. `def test_*` | First dotenv import style | Classification |
| --- | --- | --- | --- |
| `tests/test_phase166a_canonical_broker_readiness.py` | 16 | `dotenv_values` | TEST ENV GAP + ARCHITECTURAL BOUNDARY |
| `tests/test_phase152a_live_micro_pilot_capital_governor.py` | 15 | `dotenv_values` | TEST ENV GAP + LIVE-ONLY |
| `tests/test_phase152b_live_readiness_certification.py` | 10 | `load_dotenv` | TEST ENV GAP + LIVE-ONLY |
| `tests/test_canonical_order_limit_config.py` | 6 | `dotenv_values` | TEST ENV GAP + ARCHITECTURAL BOUNDARY |
| `tests/test_trade_tab_opportunity_ranking.py` | 7 | `dotenv_values` | TEST ENV GAP + ARCHITECTURAL BOUNDARY |
| `tests/test_phase155ab_opportunity_intelligence.py` | 8 | `load_dotenv` | TEST ENV GAP; TAI/AOI covered elsewhere |
| `tests/test_mc002_mission_control_live_integration.py` | 11 | `load_dotenv` | TEST ENV GAP; mc001/mc007a passed |
| `tests/test_mc003_mission_control_runtime_snapshot_integration.py` | 8 | `dotenv_values` | TEST ENV GAP |
| `tests/test_mc004_active_runtime_publisher_binding.py` | 11 | `dotenv_values` | TEST ENV GAP |
| `tests/test_css_mobile_launcher.py` | 64 | `dotenv_values` | TEST ENV GAP + launcher coupling |
| `tests/test_ov002_r1_r1_blocker_repairs.py` | 88 | `dotenv_values` | TEST ENV GAP |
| `tests/test_phase153i_live_execution_authority.py` | 6 | `dotenv_values` | TEST ENV GAP + LIVE-ONLY |
| `tests/test_phase154b_broker_parity_validator.py` | 7 | `load_dotenv` | TEST ENV GAP + LIVE-ADJACENT |
| `tests/test_phase153b_broker_selection_startup_gate.py` | 9 | `dotenv_values` | TEST ENV GAP + launcher |
| `tests/dashboard/test_mobile_live_order_kill_switch.py` | 3 | `dotenv_values` | TEST ENV GAP; other kill-switch suites passed |

**TRUE PRODUCT FAILURE of landed TAI / MI-EXT / CONSOL packages:** none identified in executed clean suites.

---

## D. dotenv / environment diagnosis

### What requires `dotenv`

Tests generally **do not** import `dotenv`. Collection fails because **production modules import it at module import time**:

| Module | Import | Role |
| --- | --- | --- |
| `backend/runtime/environment_bootstrap.py` | `from dotenv import dotenv_values` | Canonical `.env` bootstrap |
| `backend/runtime/broker_environment_profiles.py` | `from dotenv import dotenv_values` | Broker env profiles |
| `backend/app/brokers/credential_loader.py` | `from dotenv import load_dotenv` | Credential load |
| `dashboard/runtime/broker_credential_check.py` | `from dotenv import load_dotenv` | Broker credential check |
| `dashboard/mobile/mobile_app.py` | imports `environment_bootstrap` | Mobile app |
| `launcher/css_mobile_launcher.py` | `live_environment_loader` → bootstrap | Launcher |
| `OandaAdapter.__init__` | `load_credentials("oanda", ...)` | Live/practice adapter |

Typical chain: test → Mission Control / launcher / `api_bridge` / `frontend_contract` → broker diagnostics / health / OANDA auth trace → `credential_loader` / `environment_bootstrap` → `dotenv`.

### Is `python-dotenv` declared?

| Location | Pin | Role |
| --- | --- | --- |
| `requirements.txt` | `python-dotenv==1.2.2` | **Declared runtime dependency** |
| `backend/requirements.txt` | `python-dotenv` (unpinned) | Declared backend runtime dependency |
| `pyproject.toml` | not present | N/A |
| This Cloud Agent venv | **not installed** | Missing environment package |

It is **not** a stale accidental import, **not** test-only extra, and **not** something this pass may install (no dependency-install authority).

### Classification of the failure mode

1. **TEST ENVIRONMENT GAP** — declared dependency missing from the agent venv.  
2. **ARCHITECTURAL IMPORT-BOUNDARY PROBLEM** — offline unit collection should not require live `.env` parsers.  
3. Affected suites are often also **LIVE-ONLY** or launcher-bound.  
4. **Not** a true product failure of TAI-001 / TAI-002 / MI-EXT / CONSOL / UTG / TTL / AntiBleed integration as exercised by isolated suites.

### Remediation recommendation (do **not** implement in this task)

**Preferred (test-environment-only, separately authorized):**

1. Install `python-dotenv==1.2.2` from existing `requirements.txt` in CI / Cloud Agent images so declared deps match the lockfile. Installing dotenv **does not** constitute live-broker evidence and **must not** be used to claim AR-040.

**Preferred (architecture, later governed task):**

2. Lazy-import `dotenv` inside bootstrap/credential **functions**, not at module top level, so advisory/offline collection does not require the package.  
3. Keep `OandaAdapter` constructor from importing credentials until credentials are actually needed (optional empty-credentials path already exists if callers pass `credentials={}`).

**Do not:**

- Treat dotenv collection errors as TAI/MI-EXT/CONSOL merge breakage.  
- Add live `.env` secrets to CI.  
- Broaden `OandaAdapter` live defaults.

---

## E. Current truthful release posture

Canonical production-certification page `docs/release/CSS_CANONICAL_RELEASE_STATUS.md` is still dated **2026-07-21** and bound to SHA `4ea738d8` / branch `css-unified-consolidation-2026-07-13`. That SHA binding is **stale vs `fc7a6c99`**. The **posture labels** remain the truthful ones; only the SHA/date need Package D reconciliation. This cert pass does **not** rewrite that page’s GO/NO-GO claims.

| Surface | Truthful status |
| --- | --- |
| Development / maintenance line | **Active** on `css-v1.0.1-maintenance` @ `fc7a6c99` |
| Controlled paper / advisory / read-only | **GO** historically under OP-003 `CERTIFIED_CONTROLLED_PAPER_OPERATION` — not re-proven on this SHA |
| Production certification | **NO-GO** — Phase 181 `NOT_CERTIFIED` |
| Commercial readiness | **NO-GO** |
| Live trading / live micro-pilot execution | **NO-GO** |
| Broker execution armed | **false** |
| Advisory-only | **true** |
| `execution_allowed` | **false** |
| `live_trading_blocked` | **true** |
| MI-EXT live ingestion | **Unauthorized** |
| RC-LIVE candidate wholesale merge | **Not authorized** |

Safety label: `DISABLED / BLOCKED / FAIL_CLOSED / ADVISORY_ONLY`

Owner-approved live-pilot **policy** currently on maintenance (not live enablement):

- LDT-002 R2A: **CAD-only** fail-closed capital (no FX conversion for live-pilot gating).  
- LDT-002 R3A: **60-second consume-once** live authorization TTL.

### Major remaining blockers

1. OV-002 72h endurance **invalidated**; no current-SHA endurance credit (AR-014).  
2. OAT production-profile residuals (AR-013; SHUTDOWN / host ops observations).  
3. Authorized Coinbase/OANDA **live read-only** PASS/FAIL not captured (AR-040).  
4. Notification transports remain non-operational / honesty-labelled (AR-022).  
5. Phase 181 cannot become CERTIFIED until evidence packages exist on a freeze SHA.  
6. GitHub `main` is years/phases behind maintenance — default-branch confusion.  
7. dotenv/CI environment does not install declared runtime deps.  
8. Live-readiness architecture forks (184A / 196 / 197 / 188+) remain **unmerged by design**.

---

## F. Complete authoritative backlog

Items are reassessed against `fc7a6c99`, not copied from stale STATUS.

| ID / theme | Classification | Notes |
| --- | --- | --- |
| TAI-001 | COMPLETE / LANDED | PR #53; 11/11 this pass |
| TAI-002 R2 | COMPLETE / LANDED | PR #57; 14/14 this pass; #54 must not merge |
| RC-LIVE-W1-001 Autonomous Supervisor | COMPLETE / LANDED | PR #58; 5/5 this pass |
| MI-EXT-001 R2 | COMPLETE / LANDED | PR #59; 47/47 this pass; **live ingestion remains unauthorized** |
| RC-LIVE-CONSOL-001 (185A/186A/187A offline) | COMPLETE / LANDED | PR #60; 61/61 this pass; no ExecutionGate / live network |
| AOD-001 | COMPLETE / LANDED | PR #55 |
| OV002-R1-R9 sign-on lifecycle (code) | COMPLETE / LANDED (engineering) | Endurance **evidence** still open |
| DIP-004/005/006 on maintenance | COMPLETE / LANDED | 33/33 this pass |
| OV-002 72h endurance / restart | EVIDENCE / CERTIFICATION ONLY | Invalidated historically; identity probe blocked here |
| OAT SHUTDOWN / production-profile OAT | EVIDENCE / CERTIFICATION ONLY | AR-013 residual |
| Broker live read-only probes | EVIDENCE / CERTIFICATION ONLY | AR-040; credentials + network; laptop/runtime |
| Notification transport evidence | EVIDENCE / CERTIFICATION ONLY | AR-022; honesty default non-operational |
| Phase 181 recert on current SHA | EVIDENCE / CERTIFICATION ONLY | Summary still NOT_CERTIFIED |
| Canonical release-status SHA bind | DOCUMENTATION / GOVERNANCE | Page still cites `4ea738d8` |
| STATUS / REVIEW→COMPLETE file moves | DOCUMENTATION / GOVERNANCE | #58/#60 still labelled draft in STATUS at cert start |
| Stale PRs #52, #54, #56 (+ #50/#51) | DOCUMENTATION / GOVERNANCE | Close without merge (Package D) |
| Default `main` vs maintenance | DOCUMENTATION / GOVERNANCE | Decision required; do not move `main` in this pass |
| Stale historical branches | DOCUMENTATION / GOVERNANCE | Preserve `css-rc-live-001-candidate` as reference |
| dotenv / CI declared-deps | ENVIRONMENT / TOOLING | See §D |
| OV-002 identity probe in cloud | ENVIRONMENT / TOOLING | Laptop/runtime |
| LDT-002 ancestor test / MR-001 SHA pins | ENVIRONMENT / TOOLING or STALE TEST | Rewrite only in a hygiene/test task |
| Advisory / watchlist productization | PRODUCT UX GAP | No live authority |
| Manual confirmation (“CSS finds, user taps”) | PRODUCT UX GAP | No live authority |
| Auto mode **state model** (display only) | PRODUCT UX GAP | Must not grant live authority |
| Mission Control execution-mode UX | PRODUCT UX GAP | mc002–004 blocked here by dotenv |
| Futures/options dashboard completeness | LOW-RISK FEATURE GAP | `.codex-instructions.md` priorities; not this cert |
| Multi-asset dashboard polish | LOW-RISK FEATURE GAP | Same |
| MI-EXT **live** ingestion | LIVE-READINESS / SAFETY-SENSITIVE | Remain unauthorized |
| Phase 184A AntiBleed policy / ExecutionGate wiring | LIVE-READINESS / SAFETY-SENSITIVE | Design/review only |
| Phase 188+ controlled broker connectivity | LIVE-READINESS / SAFETY-SENSITIVE | Credentials + network |
| Phases 189–194 qualification framework | LIVE-READINESS / SAFETY-SENSITIVE | Design/review only |
| Phase 196 300s live-authority lease | LIVE-READINESS / SAFETY-SENSITIVE | Incompatible with R3A 60s |
| Phase 197 FX-normalized LiveMicroPilotGovernor | LIVE-READINESS / SAFETY-SENSITIVE | Incompatible with R2A CAD-only |
| Phase 198 FX blocker governance | LIVE-READINESS / SAFETY-SENSITIVE | Follows 197; not recovered |
| RC-LIVE wholesale merge | OBSOLETE / SUPERSEDED as a landing plan | Candidate is historical reference |
| Historical “100% certified” RC1 scorecards | OBSOLETE / SUPERSEDED | Canonical NO-GO prevails |
| Draft PR #54 TAI-002 original | OBSOLETE / SUPERSEDED | Replaced by #57 |

---

## G. Items marked COMPLETE / LANDED

- TAI-001  
- TAI-002 R2  
- RC-LIVE-W1-001 Autonomous Supervisor  
- MI-EXT-001 R2 (advisory/fixture catalogue only)  
- RC-LIVE-CONSOL-001 offline 185A/186A/187A  
- AOD-001  
- DIP-004 / DIP-005 / DIP-006 on this maintenance line  
- Isolated UTG / AntiBleed integration / Margin Gate / 60s TTL / kill-switch (non-dotenv paths) **tests** on this SHA  

COMPLETE does **not** mean production-certified or live-ready.

---

## H. Items obsolete / superseded

- Wholesale merge of `css-rc-live-001-candidate`  
- Draft PR #54 (`css-tai-002-runtime-validation`) — superseded by #57  
- Draft PR #52 vs `main` (historical MI-EXT / RC freeze onto stale `main`)  
- Using RC1 “GO / 100% Certified Ready” as current production authority  
- Crediting OV-002 Attempt 1 (~25h, `ENDURANCE INVALIDATED`) toward AR-014  
- Treating 185A FX **contracts** as live FX capital conversion (197)  
- Treating 187A offline OANDA cert framework as Phase 188 network connectivity  
- `agent_tasks/STATUS.md` language that #58 / #60 remain unmerged  

---

## I. Remaining low-risk gaps

- Futures/options module and dashboard completeness (Codex priorities).  
- Multi-asset dashboard presentation.  
- Mission Control launcher-bound observability (mc002–004) once dotenv/CI is honest.  
- Advisory/watchlist **product** surfaces without live ingestion.  
- Test hygiene for stale LDT-002 ancestor / MR-001 SHA pins.  
- Release-doc SHA footnotes.

---

## J. Remaining safety-sensitive gaps

- Any live ingestion for MI-EXT.  
- Phase 184A AntiBleed policy profiles + ExecutionGate wiring.  
- Phase 188+ real broker read-only connectivity.  
- Phases 189–194 multi-broker qualification.  
- Phase 196 300s lease vs current 60s consume-once TTL.  
- Phase 197/198 FX-normalized live capital vs CAD-only fail-closed.  
- Arming broker execution, live orders, funded sessions.  
- Changing UTG / AntiBleed / Capital Governor / Margin Gate / kill-switch defaults.  

**Do not implement these until a dedicated, owner-authorized live-readiness architecture review (Package C) completes, and not on this cert branch.**

---

## K. Consolidated future work packages (maximum 4)

### Package A — CERTIFICATION / EVIDENCE CLOSEOUT

Combine: OV-002 endurance/restart on a freeze SHA; OAT SHUTDOWN residual; notification evidence (or continued non-operational labelling); authorized broker **read-only** probes (AR-040); Phase 181 recert; bind canonical release docs to the freeze SHA.

**Needs laptop/runtime and operator authorization. Do not start in Cloud Agent without that access.**

### Package B — USER EXECUTION MODES (no new live authority)

Combine: Advisory/watchlist; Manual Confirmation (“CSS finds the trades, user taps”); Auto mode **state model**; Mission Control UX/state display.

May **define and productize modes**. **Must not** grant live authority, arm brokers, or change TTL/gates.

### Package C — LIVE-READINESS ARCHITECTURE REVIEW (design/review only first)

Combine analysis of: 184A AntiBleed/ExecutionGate policy; 196 TTL architecture vs R3A 60s; 197 FX capital normalization vs R2A CAD-only; 188+ controlled broker connectivity; 189–194 qualification framework; Phase 198 FX governance.

**Initially DESIGN/REVIEW ONLY. No implementation of competing live designs in the same PR as maintenance policy.**

### Package D — REPOSITORY / GOVERNANCE HYGIENE

Combine: close stale PRs without merge; branch disposition; default-branch (`main` vs maintenance) decision; STATUS/task file COMPLETE moves; release-document SHA reconciliation; optional stale-test rewrite (LDT-002 ancestor / MR-001).

**No live authority. Can start without broker credentials.**

Fewer than four is not justified: evidence, product UX, live architecture, and hygiene are distinct risk classes.

---

## L. Live-architecture conflict matrix

**Do not implement any of these in CSS-CONSOL-CERT-001.**

| Design | Benefit | Risk | Incompatibility | Superseded? | Preserve? | Future implementation justified? |
| --- | --- | --- | --- | --- | --- | --- |
| **Current maintenance: CAD-only fail-closed (R2A)** | No silent FX; explicit CAD identity only | Blocks non-CAD / OANDA unit live-pilot | Conflicts with 197 FX-normalized governor | **Canonical now** | **Yes — current owner policy** | Changes require new owner FX authority |
| **Current maintenance: 60s consume-once TTL (R3A)** | Tight freshness; single-use; kill-switch precedence | Short operator window | Conflicts with 196 max **300s** lease | **Canonical now** | **Yes** | Longer TTL only via new approved policy |
| **RC-LIVE Phase 196: 300s live-authority lease** | Longer operator/session window; lease/revoke model | Weaker freshness vs R3A; easy to land both and get the weaker one | Direct TTL conflict with 60s consume-once | **Not landed; not canonical** | **Preserve as candidate design notes only** | Justified **only** after owner chooses lease vs consume-once — not both |
| **RC-LIVE Phase 197: FX-normalized LiveMicroPilotGovernor** | Multi-asset live capital in one limit currency | Overrides CAD-only; FX rate authority; conversion bugs become live risk | Direct conflict with R2A | **Not landed** | **Preserve analysis; do not cherry-pick onto maintenance** | Justified only with approved FX authority + independent review |
| **RC-LIVE Phase 184A: AntiBleed policy profiles + ExecutionGate wiring** | Versioned STANDARD/MICRO_PILOT/PAPER/BACKTEST policies; first-gate preservation | Execution-path change; CONSOL explicitly excluded this bridge | Not compatible with “contracts-only” CONSOL isolation | **Not landed** | **Preserve as design** | Design/review yes; implementation only in a dedicated safety PR |
| **RC-LIVE Phase 188+: network OANDA read-only** | Real connectivity evidence vs 187A fixtures | Credentials, network, adapter surface | Complements 187A; does not replace CAD/TTL policy | **Not landed** | **Preserve** | After Package A/C; still not live **execution** |
| **Phases 189–194 / 198** | Qualification / FX blocker governance on candidate | Scope explosion; false “RC-LIVE certified” claims | Built on 196/197/188 stack | **Not landed** | Historical candidate | After C review; not a next implementation |

Offline 185A/186A/187A on maintenance are **contracts, fixtures, and cert framework only**. They do **not** implement 197 live FX capital conversion or 188 live network.

---

## M. PR / branch cleanup recommendations

**Do not close, merge, or delete in this task.** Recommendations only:

### Close without merge (stale / wrong base / superseded)

| PR | Why |
| --- | --- |
| **#54** | Superseded by merged #57; conflicting TAI-002 original |
| **#52** | Targets stale `main`; historical MI-EXT/RC freeze |
| **#56** | Access-check vs `main` |
| **#51**, **#50** | Cloud setup vs `main`; evaluate then close or retarget — do not merge onto `main` as if it were canonical |

### Already merged — do not reopen as work

#53, #55, #57, #58, #59, #60

### Branches

| Branch | Disposition |
| --- | --- |
| `css-v1.0.1-maintenance` | **Canonical development line** |
| `css-rc-live-001-candidate` | **Preserve** as historical reference; never wholesale merge |
| `css-tai-002-runtime-validation` | Delete after #54 closed |
| `css-tai-002-runtime-validation-r2` | Merged; optional delete after retention policy |
| `css-rclive-w1-autonomous-supervisor` | Merged; optional delete |
| `css-mi-ext-001-recovery-r2` | Merged; optional delete |
| `css-rclive-offline-market-readiness-consolidated` | Merged; optional delete |
| `main` @ `faf1485d` | **Do not fast-forward in this task.** Owner must decide default-branch policy |
| `css-unified-consolidation-2026-07-13` | Historical RC-001 line; keep as archive |

---

## N. Exact recommended NEXT package

**Package D — REPOSITORY / GOVERNANCE HYGIENE**

Rationale: the cert pass found no missing intelligence/offline-market *implementation* that should start now. The highest-value, lowest-safety-risk next work is making GitHub/STATUS/release docs match `fc7a6c99`, and removing merge hazards (#54 especially). That unblocks honest follow-on work without touching gates.

Package A is the next *certification* package but **waits for laptop/runtime**.  
Package B is the next *product* package after D if the owner wants UX — still no live authority.  
Package C stays design-only until D (and owner policy on TTL/FX) is explicit.

---

## O. Recommended branch / base

| Next package | Branch | Base |
| --- | --- | --- |
| D (hygiene) | new `css-agent/governance-hygiene-…` or owner-named hygiene branch | `css-v1.0.1-maintenance` @ then-current SHA (today `fc7a6c99` plus this cert commit if landed) |
| This cert record | `css-consol-cert-001` | `css-v1.0.1-maintenance` |
| A / B / C | **Do not** start on this cert branch | `css-v1.0.1-maintenance` after D (and A needs freeze SHA) |

---

## P. Whether implementation should begin immediately

| Work | Start now? |
| --- | --- |
| Package D hygiene (docs/PRs/branches/STATUS) | **Yes — after this cert PR is reviewed**; no laptop required |
| Package A evidence (endurance, OAT, broker RO, notifications) | **Wait for laptop/runtime + operator authorization** |
| Package B execution-mode UX | After D; **no live authority** |
| Package C live architecture | Design notes only until owner resolves TTL/FX conflicts |
| 184A / 188 / 196 / 197 / 198 / MI-EXT live | **Do not begin** |
| Installing dotenv in this cert task | **No** (not authorized here); separately as test-env correction |

---

## Governance of this pass

- No runtime, broker, execution, AntiBleed, Capital Governor, UTG, or TTL code changes.  
- No PR merges/closes, no branch deletes, no `main` modification.  
- No orders, credentials, or funded sessions.  
- Documentation-only record on `css-consol-cert-001`.

---

## Disposition

CSS CONSOLIDATED CERTIFICATION COMPLETE — NEXT PACKAGE IDENTIFIED
