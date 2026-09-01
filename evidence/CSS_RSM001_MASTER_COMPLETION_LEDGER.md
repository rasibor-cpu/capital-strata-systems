# CSS-RSM-001 — Master Completion Ledger

**Authority for this recon:** GitHub-visible `css-v1.0.1-maintenance` @ `2b39141e` plus open PR #63.  
**Not authority:** FINANCE worktree, live processes, gitignored `runtime_reports/`.  
**Date (UTC):** 2026-08-20

This is the single prioritized backlog for moving CSS forward from the phone/cloud **without** bolting features onto an un-operated SHA. Duplicate recovery branches are consolidated. Phase 184+/MI-EXT live/ISO commercial tracks are deferred.

Categories: **P0** blocks safe operation/certification · **P1** required for CSS v1 completion · **P2** important enhancement · **P3** post-v1.

---

## P0 — blocks safe operation / certification

### RSM-P0-01 — COW-001 controlled operating window

| Field | Value |
| --- | --- |
| ID | RSM-P0-01 |
| Description | Start current canonical CSS as-is for ≥24h controlled/paper with current/live market data inside existing fail-closed gates. Do not stop healthy runs at 24h. |
| Current state | Charter present on maintenance. Window **not started in this cloud**. FINANCE state unknown. |
| Repository evidence | `docs/release/CSS_COW_001_CONTROLLED_OPERATING_WINDOW.md`; `agent_tasks/QUEUE/CSS-COW-001_CONTROLLED_OPERATING_WINDOW.md`; canonical status page |
| Dependency | Package D **merged** (PR #62). Optional visibility: PR #63. |
| can_do_from_cloud | **NO** |
| requires_FINANCE | **YES** |
| Scope | LARGE (operational, not a code sprint) |
| Acceptance | ≥24h continuous controlled run; safety posture preserved; SEV log; no live-funded submits unless separately authorized |
| Sequence | **1 — next real milestone** |

### RSM-P0-02 — Phase 181 remains NOT CERTIFIED

| Field | Value |
| --- | --- |
| ID | RSM-P0-02 |
| Description | Production certification cannot be claimed. Fixture Phase 181 tests are not a freeze-SHA recert. OV-002 endurance evidence is invalidated/not credited. |
| Current state | EVIDENCE_ONLY / NOT_CERTIFIED |
| Repository evidence | `docs/release/CSS_CANONICAL_RELEASE_STATUS.md`; OV-002 invalidation reports; `tests/test_phase181_*.py` uses `evidence://phase181/...` fixtures |
| Dependency | RSM-P0-01 observations; Gate 2 AR-011 recert rules |
| can_do_from_cloud | **NO** (cannot mint production cert from fixtures) |
| requires_FINANCE | **YES** |
| Scope | LARGE |
| Acceptance | New freeze SHA + verified OAT/endurance/DR/broker-read package; summary CERTIFIED or explicit remaining NO-GO |
| Sequence | After COW-001 evidence exists |

### RSM-P0-03 — GitHub default `main` is stale Phase 113Y

| Field | Value |
| --- | --- |
| ID | RSM-P0-03 |
| Description | Default branch `main` @ `faf1485d` is not canonical. Agents/PRs keep targeting the wrong line (#50–#52, #56). |
| Current state | Documented; **not executed** (admin setting) |
| Repository evidence | `docs/governance/CSS_BRANCH_DISPOSITION_REGISTER.md` Option A |
| Dependency | None |
| can_do_from_cloud | **NO** (GitHub admin) |
| requires_FINANCE | **YES** (owner/admin) |
| Scope | SMALL |
| Acceptance | Default branch = `css-v1.0.1-maintenance`; `main` retained historical; no merge of maintenance into `main` |
| Sequence | Parallel with COW-001 (owner action) |

---

## P1 — required for CSS v1 completion (non-feature-recovery)

### RSM-P1-01 — Retarget Gate-2 CI onto canonical maintenance

| Field | Value |
| --- | --- |
| ID | RSM-P1-01 |
| Description | `css_governance.yml` and `css_gate2_release_ci.yml` still fire on `main` and `css-unified-consolidation-2026-07-13` only. Canonical PRs to maintenance get no Gate-2 job. |
| Current state | PARTIAL / wrong trigger |
| Repository evidence | `.github/workflows/css_governance.yml`; `.github/workflows/css_gate2_release_ci.yml` |
| Dependency | None |
| can_do_from_cloud | **YES** |
| requires_FINANCE | **NO** |
| Scope | SMALL |
| Acceptance | PR/push to `css-v1.0.1-maintenance` runs bounded Gate-2 pytest; still no automated production deploy |
| Sequence | **Best immediate cloud task after RSM-001** |

### RSM-P1-02 — Independent review of draft PR #63 (COW dashboard visibility)

| Field | Value |
| --- | --- |
| ID | RSM-P1-02 |
| Description | Compact command dashboard / authoritative wiring. Useful for COW observability. Not COW itself. Do not merge solely to simplify recon. |
| Current state | OPEN draft; 3 files +739 vs `2b39141e` |
| Repository evidence | PR #63; `css-cow001-dashboard-visibility-r1` |
| Dependency | Reviewer; FINANCE may already have a different dashboard |
| can_do_from_cloud | **PARTIAL** (review comments/tests); merge is human |
| requires_FINANCE | **YES** if validating against the live host |
| Scope | SMALL |
| Acceptance | Reviewer confirms no gate weakening; hashes/wiring match operator need; then merge or FINANCE-only apply |
| Sequence | Before or during COW-001 if the operator cannot see the command surface |

### RSM-P1-03 — Reconcile Package D metadata drift

| Field | Value |
| --- | --- |
| ID | RSM-P1-03 |
| Description | PR #62 is merged (`2b39141e`) but `agent_tasks/STATUS.md` still lists Package D as REVIEW; canonical status still says Package D is proposed vs `d53e665`. |
| Current state | PARTIAL honesty |
| Repository evidence | `agent_tasks/STATUS.md`; `docs/release/CSS_CANONICAL_RELEASE_STATUS.md` vs `git log` |
| Dependency | None |
| can_do_from_cloud | **YES** |
| requires_FINANCE | **NO** |
| Scope | SMALL |
| Acceptance | STATUS COMPLETE for PKG-D; canonical page lists maintenance HEAD `2b39141e` / PR #62 merged; COW-001 still not started |
| Sequence | Same PR as RSM-P1-01 or immediately after |

### RSM-P1-04 — Execution authorization modes (AUTO / MANUAL_CONFIRM / ADVISORY)

| Field | Value |
| --- | --- |
| ID | RSM-P1-04 |
| Description | Product requirement: Mode 1 auto (still fully gated), Mode 2 user-taps staged orders (gates re-run on approve), Mode 3 advisory never submits. **Do not implement before COW-001** unless the window proves a staging surface is required. |
| Current state | NOT_FOUND as product policy; RuntimeMode + fail-closed flags only |
| Repository evidence | `backend/runtime/runtime_mode.py`; `scripts/css_live_dashboard.py` submit path; recon design in `evidence/CSS_RSM001_CLOUD_RESUME_RECONCILIATION.md` §3 |
| Dependency | RSM-P0-01 preferred first so policy matches operated CSS |
| can_do_from_cloud | **YES** (code+tests), but **should wait** |
| requires_FINANCE | **YES** for UX/runtime acceptance |
| Scope | MEDIUM |
| Acceptance | Default ADVISORY; manual cannot bypass R7/R14F/AntiBleed/caps/ExecutionGate; auto still blocked when `execution_allowed=false`; audit events for stage/approve/block |
| Sequence | After COW-001 unless a SEV-2 “cannot confirm trades” defect appears |

### RSM-P1-05 — Extract R14F into a shared backend policy

| Field | Value |
| --- | --- |
| ID | RSM-P1-05 |
| Description | Profitability gate lives in `scripts/css_live_dashboard.py` (`_legacy_*`). Ranking/API paths may not share the same numbers. |
| Current state | PARTIAL |
| Repository evidence | `scripts/css_live_dashboard.py` lines 44–88; duplicate builders under `scripts/build_r14*.py` |
| Dependency | Must not change thresholds without recording them |
| can_do_from_cloud | **YES** |
| requires_FINANCE | **NO** for extract+tests; **YES** to confirm live dashboard uses the module |
| Scope | SMALL |
| Acceptance | Single module imported by dashboard + tests for SAFE/FX/CRYPTO offsets; no silent threshold change |
| Sequence | After RSM-P1-01; can pair with RSM-P1-04 later |

---

## P2 — important product enhancement (defer if it competes with COW)

### RSM-P2-01 — Cloud/CI process-identity for OV-002 continuity tests

| Field | Value |
| --- | --- |
| ID | RSM-P2-01 |
| Description | Five `test_ov002_r1_continuity_remediation.py` cases fail in this cloud agent (`identity_probe_incomplete`). Classify and either skip-on-cloud or provide a documented probe fixture. Do not weaken production identity checks. |
| Current state | FAIL in cloud; likely PASS on Windows/FINANCE |
| Repository evidence | This recon pytest log |
| Dependency | None |
| can_do_from_cloud | **YES** (test harness only) |
| requires_FINANCE | **NO** to fix tests; **YES** to credit endurance |
| Scope | SMALL |
| Acceptance | Cloud-safe tests green without skipping production identity requirements on FINANCE |
| Sequence | Optional with RSM-P1-01 |

### RSM-P2-02 — Bounded compile/regression on maintenance HEAD

| Field | Value |
| --- | --- |
| ID | RSM-P2-02 |
| Description | Full `pytest --collect-only` = 2740 tests + 107 collection errors (missing `reportlab`/launcher extras). Honest inventory of extra deps vs `requirements.txt`. |
| Current state | PARTIAL quality bar |
| Repository evidence | `requirements.txt` vs collection errors |
| can_do_from_cloud | **YES** |
| requires_FINANCE | **NO** |
| Scope | MEDIUM |
| Acceptance | Documented extra extras or added optional extra; collection errors explained, not silently ignored |
| Sequence | After CI retarget |

### RSM-P2-03 — Mission Control / mobile staged-order UX

| Field | Value |
| --- | --- |
| ID | RSM-P2-03 |
| Description | “CSS finds the trades, user taps” needs a staged ticket, not only `pending_orders` counters. |
| Current state | NOT_FOUND |
| Dependency | RSM-P1-04 |
| can_do_from_cloud | **YES** for UI skeleton |
| requires_FINANCE | **YES** for operator flow |
| Scope | MEDIUM |
| Sequence | After RSM-P1-04 |

---

## P3 — post-v1 / do not start now

| ID | Description | Why deferred |
| --- | --- | --- |
| RSM-P3-01 | Wholesale merge of `css-rc-live-001-candidate` (Phase 184A/188+/196/197/198) | Live-architecture fork; PKG-D: preserve for reference only |
| RSM-P3-02 | MI-EXT **live** network ingestion | Advisory-only recovery already merged; live ingestion unauthorized |
| RSM-P3-03 | IBKR live / funded micro-pilot | Intentionally blocked; AntiBleed vs CAD20 honesty still open |
| RSM-P3-04 | ISO 27001/9001 evidence programmes | Gate 2 AR-020/021 after governance intake |
| RSM-P3-05 | Reopen closed wrong-base PRs #50–#52/#54/#56 | Superseded |

---

## Consolidated “do not do”

- Do not merge GitHub `main` with maintenance.
- Do not merge stale `css-tai-002-runtime-validation` (use landed R2).
- Do not re-merge AOD-001 branch (already in maintenance @ `ec857f62`).
- Do not implement execution modes in the next cloud slice.
- Do not start COW-001 from a cloud agent.
- Do not weaken R7 / R14F / AntiBleed / caps.

---

## Recommended sequence

1. **FINANCE:** start COW-001 (RSM-P0-01). Optionally apply/review PR #63 if the command dashboard is invisible (RSM-P1-02).  
2. **CLOUD (now):** RSM-P1-01 CI retarget + RSM-P1-03 metadata drift.  
3. **Owner:** RSM-P0-03 default-branch retarget.  
4. **After COW evidence:** RSM-P0-02 Phase 181 recert path; only then RSM-P1-04/05 execution-mode + R14F extract.  
5. **Never as next:** RSM-P3-*.

---

## Counts

```
P0_COUNT=3
P1_COUNT=5
P2_COUNT=3
P3_COUNT=5
CSS_V1_ESTIMATED_COMPLETION_PERCENT=65
PRIMARY_CRITICAL_PATH=RUNTIME_VALIDATION
```
