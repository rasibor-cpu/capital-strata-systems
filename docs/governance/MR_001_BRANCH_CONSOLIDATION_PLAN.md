# MR-001 — Branch Consolidation and Merge Readiness Audit

**Programme:** CSS Merge Readiness Programme
**Phase:** MR-001 (offline audit only)
**Date:** 2026-07-31
**Active branch:** `css-unified-consolidation-2026-07-13`
**Active HEAD:** `66e11d4f83600a7765b4e55afa33d19e301dd70e`
**Maintenance tip:** `origin/css-v1.0.1-maintenance` @ `9a9263c185680353fac9319577b4a1f82d3311dd`
**Merge-base:** `b0703f36096bf183514293ef9b83b6e7849bd087` (Phase 183J)
**Status:** AUDIT COMPLETE — **NO MERGE PERFORMED**
**Runtime:** Not accessed, stopped, restarted, or modified

---

## 1. Executive summary

`css-unified-consolidation-2026-07-13` and `css-v1.0.1-maintenance` diverged after Phase 183J:

| Side | Unique commits | Theme |
| --- | --- | --- |
| Unified | **1** (`66e11d4f`) | RC-001 broker-reporting consistency |
| Maintenance | **9** (MW-001…004, DIP-002…006; DIP-001 docs in DIP-002) | Paper residuals + Decision Intelligence |

**Textual overlap:** **0 shared files** changed on both sides since the merge-base.
`git merge-tree --write-tree` produced a tree without conflict markers → **low textual merge risk**.

**Semantic overlap:** **YES** — especially Mission Control broker health (MW-002) vs RC-001 reporting semantics; ExecutionGate price plumbing (MW-003); TradeRuntimeService / mobile paper path (MW-001/004, DIP-003).

**Recommendation:** Proceed to a future, staged merge into a **new** RC-LIVE-001 candidate branch using the group order below. Do **not** merge onto the live endurance host without controlled shutdown.

---

## 2. Workspace verification (frozen)

| Field | Value |
| --- | --- |
| Repository | `C:\rasib\source\capital-strata-systems` |
| Remote | `https://github.com/rasibor-cpu/capital-strata-systems.git` |
| Branch | `css-unified-consolidation-2026-07-13` |
| HEAD | `66e11d4f83600a7765b4e55afa33d19e301dd70e` |
| Upstream | `origin/css-unified-consolidation-2026-07-13` |
| Parity | `0 0` |
| Tracked dirty | No (untracked LDT/MR local docs & evidence only) |

STOP condition: not triggered.

---

## 3. Branch difference inventory

### A. Commits only on unified (`maintenance..unified`)

| SHA | Subject |
| --- | --- |
| `66e11d4f83600a7765b4e55afa33d19e301dd70e` | RC-001: Normalize broker reporting semantics and canonical readiness parity |

**Files (7):**

- `backend/runtime/broker_readiness_framework.py`
- `backend/runtime/canonical_broker_state_adapter.py`
- `backend/runtime/canonical_broker_state_builder.py`
- `backend/runtime/live_readiness_state_machine.py`
- `backend/runtime/startup_summary.py`
- `dashboard/runtime/frontend_contract.py`
- `tests/test_reporting_consistency_remediation.py`

### B. Commits only on maintenance (`unified..maintenance`)

| SHA | Subject |
| --- | --- |
| `7253dbc1…` | MW-001: persist equity peak for deterministic risk gating |
| `3de93073…` | MW-002: align Mission Control with active broker profile |
| `5019a574…` | MW-003: enforce canonical price for volatility sizing |
| `c1b2f88b…` | MW-004: improve paper ledger execution fidelity |
| `99498bbc…` | DIP-002: establish canonical Trade DNA schema (+ DIP-001 architecture doc) |
| `6e408ca1…` | DIP-003: add deterministic Trade DNA capture and analytics |
| `85a5ba1f…` | DIP-004: add deterministic enterprise edge intelligence |
| `6cfa8862…` | DIP-005: add deterministic enterprise intelligence suite |
| `9a9263c1…` | DIP-006: certify enterprise readiness with limitations |

**Files:** 70 paths (+12208 / −209 vs merge-base).

### C. Files changed by both

**None** (0 path intersection since merge-base).

### D. Potential merge conflicts (textual)

| Finding | Detail |
| --- | --- |
| `git merge-tree --write-tree` | Succeeded → tree `2a6871c9…` (ephemeral merge result; **not** a branch) |
| Conflict markers | None observed |
| Residual risk | Future edits on either tip before merge could introduce conflicts; re-run merge-tree at execution time |

### E. Potential semantic conflicts

| Area | Why |
| --- | --- |
| MC health / broker projection (MW-002) vs RC-001 reporting | MW-002 maps `connection_status`/`readiness` into FAIL/DEGRADED buckets for MC AMBER; RC-001 changed PASS/PRESENT/NOT_TESTED/contamination semantics — risk of false AMBER or false green after combine |
| ExecutionGate (MW-003) | Large rewrite (+price / `price_instrument`); interacts with AntiBleed/margin tests; must not regress live authority fail-closed |
| Mobile paper path (MW-001/003/004) | Shared `dashboard/mobile/mobile_app.py` across MW commits; equity peak + vol price + ledger fidelity |
| TradeRuntimeService (MW-004 + DIP-003) | Persistence + DNA capture hooks — paper/runtime data path |
| DIP-006 limitations | Declares `live_trading_integration: NOT_READY` — merge must not be sold as live unlock |

---

## 4. Decision intelligence / maintenance inventory

| Item | Commit | Primary files | Dependencies | Execution impact | Runtime impact | Merge risk | Certification required |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **MW-001** | `7253dbc1` | SQL `005_pnl_snapshots_equity_peak.sql`; PnL repo/service; `mobile_app.py`; audit doc; tests | DB migration; mobile risk inputs | Paper risk sizing correctness | Mobile + PnL persistence | **Medium** (migration + mobile) | Focused PnL/mobile equity-peak tests; paper ticket smoke |
| **MW-002** | `3de93073` | `active_broker_projection.py` (new); `contracts.py`; `health.py`; audit; tests | MC contracts; broker state fields | None directly | MC health projection | **Medium–High semantic** with RC-001 | MW-002 tests + MC health + RC-001 reporting suite together |
| **MW-003** | `5019a574` | `execution_gate.py`; `canonical_volatility_price.py`; sizer; adapters; engine_loop; mobile; tests | ExecutionGate API | **Yes** — sizing/gate path | Engine + mobile paper | **High** | MW-003 + ExecutionGate/AntiBleed/margin/risk integration tests |
| **MW-004** | `c1b2f88b` | `trade_runtime_service.py`; `paper_execution_economics.py`; orchestrator; mobile; tests | Paper ledger | Paper execution economics | Mobile/orchestrator paper | **Medium** | MW-004 + paper fidelity tests |
| **DIP-001** | Docs in `99498bbc` | `DIP_001_…ARCHITECTURE.md` | None code | None | None | **Low** | Doc presence only |
| **DIP-002** | `99498bbc` | `backend/intelligence/trade_dna/*`; docs; tests | Pure library | None (advisory schema) | None unless wired | **Low** | `test_dip002_*` |
| **DIP-003** | `6e408ca1` | DNA capture/close/durable_store; decision_analytics; **hooks `trade_runtime_service.py`** | DIP-002 | Capture on close path | Persistence side effects | **Medium** | DIP-003 + trade runtime tests |
| **DIP-004** | `85a5ba1f` | `edge_intelligence/*`; docs; tests | DIP-002/003 data | Advisory | None default | **Low** | `test_dip004_*` |
| **DIP-005** | `6cfa8862` | `enterprise_intelligence/*`; docs; tests | DIP-004 | Advisory | None default | **Low** | `test_dip005_*` |
| **DIP-006** | `9a9263c1` | DIP-006 cert doc + manifest; certification test | DIP-002…005 | None | None | **Low** | Re-run DIP-006 cert on **post-merge** HEAD (manifest currently pins maintenance SHAs) |

---

## 5. Runtime conflict analysis

| Surface | Touched by maintenance? | Overlap detail |
| --- | --- | --- |
| **ExecutionGate** | **YES** | MW-003 substantial edit; requires `price` / `price_instrument` |
| **RiskGovernor** | Module **NO**; tests only (+price args) | No production `risk_governor.py` change |
| **TradeRuntimeService** | **YES** | MW-004 + DIP-003 |
| **Mission Control runtime** | **YES** | MW-002 projection/health/contracts |
| **Broker adapters** | **NO** direct adapter modules | Semantic coupling via MC projection + RC-001 reporting (unified) |
| **RBAC** | **NO** | — |
| **AntiBleed** | Module **NO**; integration tests updated | Still live-critical with CAD20 conflict (LDT-002) |
| **Margin Gate** | Module **NO**; tests updated | — |
| **Capital governor (152A)** | **NO** | — |
| **Startup pipeline** | Unified RC-001 touches `startup_summary` / readiness; maint **NO** on those files | Semantic combine with MW-002 |
| **Mobile launcher** | **NO** (`css_mobile_launcher.py` clean) | `mobile_app.py` **YES** (MW-001/003/004) |
| **Runtime supervisor** | **NO** | — |

---

## 6. Safe merge groups

| Group | Contents | Independently mergeable? | Notes |
| --- | --- | --- | --- |
| **A — Pure governance docs** | DIP-001/002/003/004/005/006 docs + MW audit docs (if split) | Yes (docs-only cherry-picks) | Lowest risk; optional first |
| **B — Offline analytics libraries** | DIP-002 trade_dna core (without capture hooks); DIP-004; DIP-005 | Yes if DIP-003 deferred | No ExecutionGate |
| **C — Trade DNA capture** | DIP-003 (+ TradeRuntimeService hooks) | After B | Persistence side effects |
| **D — Decision Intelligence certification** | DIP-006 docs/tests/manifest refresh | After B+C | Must rewrite manifest SHAs post-merge |
| **E — Paper residual MW-001** | Equity peak migration + mobile resolution | Yes | Requires DB migration discipline |
| **F — Mission Control MW-002** | Active broker projection + health | After or with RC-001 retained | **Semantic gate with RC-001** |
| **G — ExecutionGate MW-003** | Canonical vol price + gate | Separate high-scrutiny PR | Restart + heavy regression |
| **H — Paper ledger MW-004** | Economics + orchestrator + mobile | After E (shared mobile) | Prefer after MW-001 to reduce mobile thrash |
| **I — Unified baseline preserve** | Keep `66e11d4f` RC-001 as first parent / merge base side | N/A | Do not drop reporting remediation |

**Do not** lump G with F in one unreviewed mega-merge.

---

## 7. Recommended merge order

Assume future worktree/branch (not the endurance host). **No merge in MR-001.**

| Step | Group | Est. textual conflicts | Required regression | Runtime impact | Restart required? | Certification |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | Verify tips + re-run merge-tree | — | — | None | No | — |
| 1 | **A** docs | Very low | Doc link check | None | No | None |
| 2 | **B** DIP-002/004/005 libs | Low | dip002/004/005 tests | None | No | Offline DIP unit |
| 3 | **E** MW-001 | Low–Med | equity peak + pnl tests | Persistence | **Yes** if migration applied on a runtime host | Paper risk path |
| 4 | **I** ensure RC-001 present | — | reporting consistency tests | Reporting only | Prefer restart after later runtime groups | RC-001 suite |
| 5 | **F** MW-002 | Low textual / **High semantic** | MW-002 + MC health + **RC-001 reporting** | MC | Restart MC/mobile surfaces | Combined broker reporting/MC cert |
| 6 | **H** MW-004 | Med (mobile/orchestrator) | MW-004 | Paper ledger | Restart | Paper fidelity |
| 7 | **C** DIP-003 | Med | DIP-003 + trade runtime | Capture hooks | Restart | DIP-003 |
| 8 | **G** MW-003 | Med–High | MW-003 + ExecutionGate + AntiBleed + margin + risk tests | **Engine gate** | **Yes** | ExecutionGate cert |
| 9 | **D** DIP-006 | Low | Refresh manifest to new HEAD; dip006 test | None | No | DIP-006 re-issue |
| 10 | Full focused bundle | — | LDT offline + DIP + MW + RC-001 + gate suites | — | Clean runtime for paper | Pre-RC-LIVE-001 |

If any step fails: stop; do not proceed to live-read-only or live.

---

## 8. RC-LIVE-001 preparation plan (design only — do not create)

### Goal

Create a **future** release-candidate branch that consolidates unified RC-001 with approved maintenance groups, then freeze for LDT preflight (still **NO live** until LDT gates pass).

### Proposed process

1. **Branch name (future):** `css-rc-live-001-candidate` (from `css-unified-consolidation-2026-07-13` @ freeze parent).
2. **Merge sequence:** follow §7 steps 1–9 on a **clean** machine/worktree — **not** the endurance runtime host.
3. **Freeze SHA:** tip after step 9 + green regressions; record in LDT freeze record; remote parity `0 0`.
4. **Required regression:**
   - RC-001 reporting tests
   - MW-001…004 focused tests
   - DIP-002…006 tests (manifest updated)
   - ExecutionGate / AntiBleed / margin / risk integration
   - MC health + active broker projection
5. **Required runtime test (post controlled endurance shutdown):** single-tree startup; supervisor healthy; heartbeat fresh; kill switch engaged; live authority BLOCKED.
6. **Required paper test:** RC-003R-style paper acceptance re-run on freeze SHA.
7. **Required live-read-only test:** OANDA LIVE-read-only preflight (no orders) per LDT-002 gap list.
8. **Founder approval:** written GO for **candidate freeze only** — not live arming. Live remains LDT-blocked (AntiBleed/CAD20, FX contract, TTL, OANDA LIVE, etc.).

**Explicit:** MR-001 does **not** create `css-rc-live-001-candidate` and does **not** authorize live trading.

---

## 9. Relationship to LDT-001 / LDT-002

- Non-ancestor MW/DIP evidence still **cannot be silently credited** on active HEAD until merged and re-certified (LDT-002).
- AntiBleed vs CAD 20 remains **BLOCKED** independent of this merge.
- Merge readiness ≠ live readiness.

---

## 10. Explicit non-actions

MR-001 did not: merge, cherry-pick, rebase, commit, push, contact brokers, modify runtime-loaded code, or touch the running CSS instance.
