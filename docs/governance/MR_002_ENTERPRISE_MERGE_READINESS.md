# MR-002 — Enterprise Merge Readiness

**Programme:** CSS Enterprise Merge Readiness
**Workstream:** MR-002
**Title:** Enterprise Merge Readiness Package (Documentation Only)
**Status:** `MR_002_READY_FOR_REVIEW`
**Package date:** 2026-08-01

**Documentation worktree (this package):**
- Path (operator reference): `C:\rasib\source\capital-strata-systems-mi`
- Remote repository: `https://github.com/rasibor-cpu/capital-strata-systems`
- Required branch: `css-market-intelligence-external-sources-001`
- Expected HEAD: `3c7a6b61de2f7784e794b9f186a440d0f50392b2`
- Verified HEAD: `3c7a6b61de2f7784e794b9f186a440d0f50392b2`
- Tip subject: `MI-EXT-001: add governed external events and source provenance`

**Active runtime (DO NOT TOUCH):**
- Path (operator reference): `C:\rasib\source\capital-strata-systems`
- Branch: `css-unified-consolidation-2026-07-13`
- HEAD: `66e11d4f83600a7765b4e55afa33d19e301dd70e`
- Tip subject: `RC-001: Normalize broker reporting semantics and canonical readiness parity`

**This package does not authorize:** merge, cherry-pick, implementation, runtime access, broker access, live trading, controlled-online MI validation, commit, or push.

**Companion artifacts:**
1. `docs/governance/MR_002_RC_LIVE_FREEZE_CHECKLIST.md`
2. `docs/governance/MR_002_MERGE_MATRIX.json`

---

## 1. Executive verdict

| Item | Verdict |
| --- | --- |
| Workspace / branch / HEAD | **VERIFIED** — MI documentation branch matches expected SHA |
| Active runtime isolation | **RESPECTED** — no runtime interaction performed |
| MI-EXT-001 additive surface | **MERGE-READY (textually)** onto current RC tip (`66e11d4f…`) as a fast-forward of one commit |
| Decision Intelligence (DIP / Trade DNA) | **DEPENDENT ON MR-001** — present on `css-v1.0.1-maintenance`, absent on MI/RC tip for DIP suite |
| Mission Control activation of MI-EXT panels | **NOT READY / NOT AUTHORIZED** — design-only; no MC panel activation against endurance runtime |
| Live / broker / execution | **FORBIDDEN** for this workstream |
| Package status | **`MR_002_READY_FOR_REVIEW`** |

**Recommendation:** Accept this documentation package for enterprise review. Do **not** merge MI-EXT into the active endurance runtime. Sequence merges per §4 (MR-001 Decision Intelligence first when full advisory learning is required; MI-EXT may land on RC tip as an additive advisory library after freeze criteria in the RC-LIVE checklist).

---

## 2. Workspace verification

| Check | Expected | Observed | Result |
| --- | --- | --- | --- |
| Documentation branch | `css-market-intelligence-external-sources-001` | `css-market-intelligence-external-sources-001` | PASS |
| Documentation HEAD | `3c7a6b61de2f7784e794b9f186a440d0f50392b2` | `3c7a6b61de2f7784e794b9f186a440d0f50392b2` | PASS |
| MI base commit (charter) | `66e11d4f83600a7765b4e55afa33d19e301dd70e` | merge-base(MI, unified) = `66e11d4f…` | PASS |
| MI ahead of unified | 1 commit | `0 1` (left-right unified…MI) | PASS |
| Active runtime branch (reference only) | `css-unified-consolidation-2026-07-13` | tip `66e11d4f…` on origin | PASS (not modified) |
| Runtime access | Forbidden | Not performed | PASS |
| Broker access | Forbidden | Not performed | PASS |
| Merge / cherry-pick | Forbidden | Not performed | PASS |
| Commit / push | Forbidden | Not performed | PASS |

**Repository naming note:** Operator MI worktree path is `capital-strata-systems-mi`; remote origin is `capital-strata-systems`. Branch/SHA identity is authoritative.

---

## 3. Complete branch inventory

Remote refs observed on origin at package time (46 remote branches). Roles below are merge-governance classifications for MR-002.

### 3.1 Primary merge actors

| Branch | Tip SHA (short) | Role | Merge posture |
| --- | --- | --- | --- |
| `css-unified-consolidation-2026-07-13` | `66e11d4f` | **RC / active runtime lineage** | Protected; freeze target; DO NOT TOUCH for ops |
| `css-market-intelligence-external-sources-001` | `3c7a6b61` | **MR-002 subject (MI-EXT-001)** | Additive advisory library; 1 commit atop RC tip |
| `css-v1.0.1-maintenance` | `9a9263c1` | **MR-001 / DIP Decision Intelligence carrier** | Diverged from RC tip; DIP-001…006 suite |
| `main` | `faf1485d` | Historical public mainline | Behind RC programme; not RC-LIVE target |
| `master` | `eaa8d538` | Legacy | Archive / ignore for RC-LIVE |

### 3.2 Programme / consolidation lineage

| Branch | Tip | Classification |
| --- | --- | --- |
| `css-evening-consolidation-2026-06-09` | `c2c4d588` | Historical consolidation audit |
| `consolidation/pcnrass-mainline` | `540a21e0` | Canonicalization governance foundation |
| `phase1-lock-candidate-manual` | `31634eaf` | Historical lock candidate |
| `post-claude-audit-remediation-phase-a-clean` | `8f0f33fc` | Audit remediation baseline |
| `css-v1.0.1-maintenance` | `9a9263c1` | Maintenance + DIP certification tip |

### 3.3 Intelligence-adjacent historical branches

| Branch | Tip | Classification |
| --- | --- | --- |
| `feature/css-world-event-intelligence` | `f5c8ecf1` | Early events module scaffolding — superseded by GIE + MI-EXT |
| `wip/intel-adapter-edits` | `778bc2fa` | WIP intel adapters — do not merge as parallel spine |
| `phase-155-caie-capital-allocation-intelligence` | `a81ce8a1` | CAIE / broker readiness lineage — already absorbed into RC programme historically |
| `phase57-regime-governance-foundation` | `ee5043d5` | Regime governance foundation |
| `phase90a-institutional-instrument-framework` | `2f66bd66` | Institutional instruments |
| `phase90b-institutional-registry-engine` | `7136df7a` | Institutional registry |

### 3.4 Options / futures specification branches (docs/spec only or sandbox)

| Branch | Tip | Classification |
| --- | --- | --- |
| `feature/options-sandbox-phase1` | `f374539b` | Sandbox |
| `feature/options-*-spec` (multiple) | various | Spec-only; not RC-LIVE merge blockers |
| `feature/futures-orchestrator-integration-spec` | `0f028308` | Spec-only |

### 3.5 Broker / PnL / ops historical

| Branch | Tip | Classification |
| --- | --- | --- |
| `feature/broker-bootstrap` | `407d8bc8` | Historical bootstrap |
| `live-adapters` | `cb97af44` | Historical adapters |
| `pnl-engine-safe-integration` | `53753f42` | Historical PnL integration |
| `css-pnl-recovery-clean-2026-04-25` | `16efbb77` | Historical recovery |
| `css-profit-baseline-reference` | `d2f0129f` | Reference baseline |
| `css-phone-ops-2026-06-17` | `467ecf22` | Phone ops / capital governance |
| `css-phase2-coinbase-init-fix` | `ee5f0606` | Coinbase init fix |
| `phase71-phone-recovery` | `a59a0dc7` | Phone recovery artifacts |
| `phase71-church-governance-pack` | `a7586432` | Governance pack |
| `recover-full-dashboard-2056` | `2bdbfd3b` | Dashboard recovery |
| `phone-offline-merge` | `b7b01a0a` | Offline merge artifacts |

### 3.6 Codex / agent / posting / ledger historical

| Branch | Tip | Classification |
| --- | --- | --- |
| `codex/build-css-profitability-analytics-foundation` | `ea229cd0` | Codex analytics |
| `codex/implement-opportunity-normalization-foundation` | `51dc02ea` | Opportunity normalization |
| `codex/fix-phase-54-*` (2) | various | Pilot safety test fixes |
| `css-agent/dev-environment-setup-ef97` | `1fcabe2c` | Agent environment docs |
| `css-agent/healthchecker-plus-cursor-setup-a78b` | `e0dea39c` | Agent setup package |
| `feature/backend-core-wiring` | `c5f62333` | Historical backend wiring |
| `feature/posting-screens` / `phase-10-posting-screens` | various | Posting screens |
| `phase1c-ledger-printing` | `dfc657c5` | Ledger / sizing |
| `governance_phase_lock` | `e61060d1` | Gate lock |

Full machine-readable inventory: `MR_002_MERGE_MATRIX.json` → `branch_inventory`.

---

## 4. Merge dependency graph

```text
origin/main (faf1485d)
  historical — not RC-LIVE target
        |
        | (diverged programme)
        v
css-unified-consolidation-2026-07-13
66e11d4f — RC-001 tip / ACTIVE RUNTIME LINEAGE (DO NOT TOUCH)
        |                               \
        | fast-forward +1                \ divergent (MR-001 carrier)
        v                                 v
css-market-intelligence-          css-v1.0.1-maintenance
external-sources-001              9a9263c1 — DIP-001..006 / Trade DNA
3c7a6b61 — MI-EXT-001 (MR-002)    Edge / Enterprise Intelligence
        |                                 |
        |                                 | MR-001 (Decision Intelligence)
        |                                 v
        |                     RC tip + DIP (post-MR-001)
        +--------------------> then integrate MI advisory context /
          MR-002 (Market Intel)  profit-attribution learning contract
                                          |
                                          v
                              RC-LIVE freeze SHA candidate
                              (see freeze checklist)
```

### 4.1 Ordered dependencies

| Order | Dependency | Why |
| --- | --- | --- |
| 0 | Protect `66e11d4f…` runtime | Endurance / RC ops continuity |
| 1 | **MR-001** — Decision Intelligence (DIP/Trade DNA/Edge/Enterprise Intel) from `css-v1.0.1-maintenance` | Required before MI-EXT profit-attribution learning targets are real modules |
| 2 | **MR-002** — Market Intelligence external events (`3c7a6b61…`) | Additive catalogue/provenance/advisory library; textual FF onto current RC tip; rebase if MR-001 lands first |
| 3 | Mission Control projection workstream (future) | Read-only MI-EXT panels; not part of this package |
| 4 | Controlled-online validation (future, separate authorization) | Live network adapters remain fail-closed |
| 5 | RC-LIVE freeze | Only after certification checkpoints green |

### 4.2 Non-dependencies (explicit)

- MI-EXT does **not** depend on options/futures spec branches.
- MI-EXT does **not** depend on WIP intel-adapter or world-event feature branches (those are superseded / non-spine).
- MI-EXT does **not** require broker, ExecutionGate, RiskGovernor, or AntiBleed changes.

---

## 5. Semantic conflict matrix

| Domain | RC tip (`66e11d4f`) | MI-EXT (`3c7a6b61`) | Maintenance / DIP (`9a9263c1`) | Conflict class | Resolution rule |
| --- | --- | --- | --- | --- | --- |
| External event provenance | Gap / partial GIE source strings | Canonical MI-EXT catalogue + schema | N/A | **Additive** | MI-EXT owns provenance spine |
| GIE `IntelligenceEvent` | Existing consumer model | Optional fail-safe `gie_bridge` | May consume events later | **Compatible** | Bridge never becomes second scheduler/store |
| Overnight MI / Phase 138 | Active multi-factor / overnight | Extends via advisory context; no fork | Advisory learning later | **Compatible** | No second MI engine |
| Trade DNA / Edge / Enterprise Intel | Absent as DIP suite | Design contract only (`ABSENT_UNTIL_MR_001`) | Authoritative DIP modules | **Sequencing** | Merge MR-001 before enabling learning wiring |
| Execution / risk gates | Active authority | Static boundary: no imports/mutation | Advisory-only DIP | **None** | Hard fail-closed flags |
| Source tiers / contradiction | Weak / ad-hoc | Tier 1–4 + Tier-1 dominance | N/A | **Additive** | Lower tier cannot override Tier 1 |
| Live network fetch | Broker MD separate | Fixture-only; live unauthorized | Offline DIP | **None** | Keep fail-closed |
| Mission Control MI page | Read-only regime/signals | No panel activation this phase | MC decision panels exist | **Deferred** | Future additive projection only |

---

## 6. Runtime conflict matrix

| Runtime surface | Active endurance (`capital-strata-systems` @ `66e11d4f`) | MI worktree / branch | Conflict risk | MR-002 rule |
| --- | --- | --- | --- | --- |
| Process / ports / endurance | Running / operator-owned | Documentation / offline tests only | **HIGH if touched** | **DO NOT TOUCH** |
| Broker sessions | Possibly armed/read-only per RC ops | No broker access | **CRITICAL if touched** | Forbidden |
| ExecutionGate / RiskGovernor / AntiBleed | Live authority path | Not imported by MI-EXT | None if isolated | Keep isolated |
| Mission Control UI | Active projections | No MI-EXT panel deploy | Medium if hot-patched | No hot-patch |
| Python package `external_events` | Absent on RC tip | Present on MI tip | Low (additive) | Merge only via governed RC-LIVE |
| Persistence | Runtime DBs | In-pipeline only | None | No production store activation |
| Network egress for news | Ops-controlled | Fixture-only | None while unauthorized | Keep unauthorized |

---

## 7. Decision Intelligence dependencies

| Dependency | Location today | Required for | Status |
| --- | --- | --- | --- |
| DIP-001 Architecture | `css-v1.0.1-maintenance` | Platform spine | Architecture complete (maintenance) |
| DIP-002 Trade DNA schema | maintenance | Immutable trade SoT | Present on maintenance |
| DIP-003 Capture & analytics | maintenance | Attribution inputs | Present on maintenance |
| DIP-004 Edge Intelligence | maintenance | Edge metrics | Present on maintenance |
| DIP-005 Enterprise Intelligence Suite | maintenance | Executive suite | Present on maintenance |
| DIP-006 Certification | maintenance tip `9a9263c1` | Readiness with limitations | `READY_TO_COMMIT_WITH_LIMITATIONS` (DIP doc) |
| MC-006 Decision Intelligence | RC tip | Read-only decision projections | Certified read-only on RC lineage |
| Executive Decision Intelligence (Phase 179) | RC tip | Executive scorecards | Present on RC lineage |
| MI → DIP learning contract | `decision_integration.profit_attribution_learning_contract()` | Event→Trade DNA learning | **`ABSENT_UNTIL_MR_001`** |
| Auto-allocation | — | — | **Always false** |

**Rule:** MR-002 may merge MI-EXT as an advisory library without DIP present, but must not claim Trade DNA / Edge learning integration until MR-001 lands.

---

## 8. Market Intelligence dependencies

| Component | Path / artifact | Role | Merge note |
| --- | --- | --- | --- |
| MI-EXT package | `backend/intelligence/external_events/*` | Catalogue, provenance, dedup, freshness, impact, safety | Subject of MR-002 |
| Charter / schema / catalogue | `docs/governance/MI_EXT_001_*` | Governance authority | Must travel with code |
| Fixtures | `tests/fixtures/mi_ext_001/*` | Offline wave-1 sources | Required for certification |
| Tests | `tests/test_mi_ext_001_*.py` | Offline + hardening | Required green before RC-LIVE |
| GIE bridge | `gie_bridge.py` | Optional projection | Fail-safe |
| Decision integration | `decision_integration.py` | AdvisoryContextPatch | Hard execution flags false |
| Overnight MI | `backend/executive_intelligence/overnight_market.py` | Existing consumer (future) | Do not fork |
| Phase 138 engines | `backend/market_intelligence/*` | Multi-factor advisory | Do not fork |
| Legacy `intel/` adapters | `intel/` | Partial / legacy | Catalogue supersedes trust policy |
| World-event / WIP branches | historical | Non-spine | Do not merge as parallel engines |

---

## 9. Mission Control dependencies

| Surface | Status on RC tip | MI-EXT impact | Gate |
| --- | --- | --- | --- |
| MC foundation / live snapshot / runtime binding (MC-001…004) | Present | None this package | Keep read-only |
| Operations command center (MC-005) | Present | None | Keep read-only |
| Decision Intelligence (MC-006) | Certified read-only | Future consumer of advisory context | No execution language |
| Institutional / secure ops (MC-007A/B) | Present | None | Keep metadata-only where certified |
| Market Intelligence page | Regime/signals display | **No MI-EXT panel activation** | Future workstream |
| Source registry / freshness | Section provenance | Distinct from news provenance | Do not conflate |
| Cryptography / ReportLab env gaps | Known blockers for some launcher tests | Documented in MI charter | Do not treat as MI code failure |

**Rule:** Mission Control remains read-only. MI-EXT must not introduce POST mutation routes, broker arms, or live toggles.

---

## 10. Certification checkpoints

| ID | Checkpoint | Evidence | Required before |
| --- | --- | --- | --- |
| CP-MR002-01 | Branch/HEAD verification | This document §2 | Review acceptance |
| CP-MR002-02 | MI governance docs present | Charter, schema, catalogue + this package | Review acceptance |
| CP-MR002-03 | Offline MI-EXT provenance tests | `tests/test_mi_ext_001_external_events_provenance.py` | Code merge authorization |
| CP-MR002-04 | Hardening / boundary / catalogue integrity | `tests/test_mi_ext_001_hardening_review.py` | Code merge authorization |
| CP-MR002-05 | Advisory-only / execution_allowed=false invariants | Schema consts + static AST tests | Code merge authorization |
| CP-MR002-06 | No runtime/broker interaction in merge prep | Operator attestation | RC-LIVE freeze |
| CP-MR002-07 | MR-001 decision (land / defer / waive learning) | Explicit governance decision record | Claiming DIP integration |
| CP-MR002-08 | Mission Control non-activation attestation | Checklist | RC-LIVE freeze |
| CP-MR002-09 | `git diff --check` clean on package | Validation log | Package acceptance |
| CP-MR002-10 | Freeze SHA criteria satisfied | `MR_002_RC_LIVE_FREEZE_CHECKLIST.md` | RC-LIVE candidate |

---

## 11. Rollback points

| Point | SHA / ref | When to use |
| --- | --- | --- |
| **RP-0 Active runtime** | `66e11d4f83600a7765b4e55afa33d19e301dd70e` | Immediate restore of pre-MI RC tip / endurance baseline |
| **RP-1 Pre-MI documentation branch parent** | same as RP-0 (MI parent) | Undo MI-EXT commit before any integration |
| **RP-2 MI-EXT tip** | `3c7a6b61de2f7784e794b9f186a440d0f50392b2` | Known-good MI-EXT package tip (offline) |
| **RP-3 Post-MR-001 (future)** | *TBD at MR-001 freeze* | Rollback target after DIP lands |
| **RP-4 RC-LIVE freeze (future)** | *TBD at freeze* | Production-candidate rollback label |

Rollback standard reference: `docs/governance/CSS_ROLLBACK_AND_RECOVERY_STANDARD.md` (kill-switch → revert → verify → reconcile). MI-EXT rollback is library/docs removal or revert of the single additive commit if merged; it must not require broker recovery if advisory-only invariants held.

---

## 12. Freeze SHA criteria

A freeze SHA for RC-LIVE candidacy that includes MI-EXT MUST satisfy all of:

1. **Immutable identity:** full 40-char SHA recorded; branch tip == freeze SHA; clean committed tree for freeze scope.
2. **Ancestry:** freeze SHA is descendant of RC tip `66e11d4f…` OR explicitly re-parented post-MR-001 with recorded merge parents.
3. **MI content:** contains MI-EXT package + `MI_EXT_001_*` governance artifacts + offline tests/fixtures.
4. **Safety constants:** `advisory_only=true`, `execution_allowed=false` enforced in schema and code paths.
5. **No live adapters enabled:** `LiveNetworkFetchAdapter` / online validation remain unauthorized/fail-closed.
6. **No endurance mutation:** freeze process did not alter the running `capital-strata-systems` worktree/process.
7. **Certification evidence:** CP-MR002-03…05 green on freeze SHA.
8. **Drift protection:** post-freeze commits invalidate RC-LIVE continuous certification (same discipline as OV-002 freeze).
9. **DIP claim honesty:** if DIP modules absent, freeze notes MUST say learning integration deferred.
10. **MC honesty:** freeze notes MUST say MI-EXT Mission Control panels not activated unless a later certified workstream says otherwise.

Detailed operator checklist: `MR_002_RC_LIVE_FREEZE_CHECKLIST.md`.

---

## 13. RC-LIVE candidate workflow

1. **Isolate** — Keep active runtime worktree untouched. Perform merge prep only in a governed integration worktree.
2. **Decide MR-001** — Land, schedule, or explicitly defer DIP; record decision.
3. **Integrate MI-EXT** — Fast-forward onto `66e11d4f…` if still parent; otherwise merge/rebase onto post-MR-001 tip without activating live fetch.
4. **Validate offline** — MI-EXT provenance + hardening tests; documentation package intact; `git diff --check`.
5. **Attest non-activation** — No MC panel deploy, no broker, no endurance restart for MI.
6. **Freeze** — Tag/record freeze SHA per §12; start RC-LIVE candidate clock only after checklist sign-off.
7. **Operate under freeze** — No mid-run commits on freeze SHA; drift = invalidation.
8. **Rollback ready** — RP-0 / freeze parent recoverable within standard rollback procedure.

---

## 14. Explicit non-goals (this package)

- No merge execution
- No cherry-pick
- No implementation beyond documentation artifacts listed
- No runtime or broker access
- No commit / push from this documentation-only instruction set
- No live trading authorization
- No claim of Production Certification

---

## 15. Package contents checklist

- [x] `docs/governance/MR_002_ENTERPRISE_MERGE_READINESS.md`
- [x] `docs/governance/MR_002_RC_LIVE_FREEZE_CHECKLIST.md`
- [x] `docs/governance/MR_002_MERGE_MATRIX.json`

**Signal:** `MR_002_READY_FOR_REVIEW`
