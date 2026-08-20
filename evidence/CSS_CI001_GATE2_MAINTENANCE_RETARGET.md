# CSS-CI-001 — Retarget Gate-2 CI to canonical maintenance

**Date (UTC):** 2026-08-20  
**Notepad:** not opened (cloud agent)  
**Implementation base:** `origin/css-v1.0.1-maintenance` @ `2b39141e18fcfa2f1ee2dfcf7806061ab42e79f5`  
**Not used as implementation base:** draft PR #64 (RSM-001 evidence only)

---

## Starting repository identity

```
PWD=/workspace
REMOTE=github.com/rasibor-cpu/capital-strata-systems
START_BRANCH=css-agent/css-rsm001-cloud-resume-af15
START_HEAD=ac7b036fc88aa6dbafd6b7080e5f71cbff761b59
CANONICAL_BASE=origin/css-v1.0.1-maintenance
CANONICAL_BASE_SHA=2b39141e18fcfa2f1ee2dfcf7806061ab42e79f5
WORK_BRANCH=css-agent/css-ci001-gate2-maintenance-target-af15
```

Exact SHA match to the authorized base was verified before edits. RSM-001 branch was left intact and was not merged.

---

## Phase 1 — workflows inspected

All files under `.github/workflows/`:

| File | Role | Old triggers | Gate-2? |
| --- | --- | --- | --- |
| `css_gate2_release_ci.yml` | **CSS Gate 2 Release CI**; job `gate2-ci` named `Compile + bounded Gate-2 regression` | push/PR: `main`, `css-unified-consolidation-2026-07-13`; `workflow_dispatch` | **YES** |
| `css_governance.yml` | **CSS Governance Validation** (AR-016 / RB-011); job `governance-ci`; same bounded pytest as Gate-2 | same as above | **YES** (same suite) |
| `ai-governance-sweep.yml` | Full `pytest` + `scripts/run_ai_governance_sweep.py` | `main`, consolidation, `css-evening-consolidation-2026-06-09` | **NO** — not modified |
| `build_css_audit_zip.yml` | Audit zip | `workflow_dispatch` + self-path push | **NO** — not modified |

No reusable workflow `uses: .github/workflows/...` dependencies.  
No CI helper Python with a hard-coded trigger branch that required a product-code change.  
`workflow_dispatch` was already present on both Gate-2 files (no `inputs`; any ref that contains the file can be dispatched).

**PRs targeting `css-v1.0.1-maintenance` did not receive Gate-2** because `on.pull_request.branches` omitted that name.  
**Pushes to maintenance** likewise did not run Gate-2.

Branch protection API returned **403** from this token. Workflow **names** and job names were preserved so existing required-check strings (if any) are not renamed:

- `CSS Gate 2 Release CI` / `Compile + bounded Gate-2 regression`
- `CSS Governance Validation` / `governance-ci`

---

## Phase 2 — trigger policy

| Rule | Decision |
| --- | --- |
| A. maintenance receives Gate-2 | **Add** `css-v1.0.1-maintenance` to push + pull_request |
| B. PRs targeting maintenance | Same `pull_request.branches` addition |
| C. workflow_dispatch | **Kept** |
| D. Do not make `main` authoritative | Comment in YAML; `main` is not listed first |
| E. Do not remove `main` | **Kept** (stale default still gets the same named checks) |
| F. Remove obsolete consolidation? | **No.** PKG-D classifies `css-unified-consolidation-2026-07-13` as preserve-for-reference; historical PRs still need the same check names |
| G. Preserve check names | Workflow `name:` and Gate-2 job `name:` unchanged; pytest list unchanged |

---

## Phase 3 — patch

Files changed (CI only):

- `.github/workflows/css_gate2_release_ci.yml`
- `.github/workflows/css_governance.yml`

Before:

```
push/PR branches: main, css-unified-consolidation-2026-07-13
```

After:

```
push/PR branches: css-v1.0.1-maintenance, main, css-unified-consolidation-2026-07-13
```

`git diff --stat`: 2 files, 12 insertions.  
`git diff --check`: clean.  
YAML: `yaml.safe_load` **OK** for both files. Job steps, permissions (`contents: read`), pytest paths, and `CSS_CERTIFICATION_PROFILE: fixture_lab` unchanged.

---

## Phase 4 — cloud-safe tests

### Exact Gate-2 pytest list (what GitHub will run)

```
tests/test_wave4_product_honesty.py
tests/test_wave3_evidence_machine.py
tests/test_wave2_security_broker_integrity.py
tests/test_batch1_deployment_honesty.py
tests/test_batch2_certification_evidence.py
tests/test_phase181_production_readiness_certification.py
tests/test_certification_engine.py
```

Also ran `python3 -m compileall -q backend dashboard launcher scripts` (COMPILE_OK).

```
GATE2_COLLECTED=51
GATE2_PASSED=49
GATE2_FAILED=2
```

Pre-existing on maintenance HEAD (this YAML patch does not touch Python):

1. `test_ar023_no_hardcoded_bootstrap_password` — `MIN_PASSWORD_LENGTH` is 8, test asserts `>= 12`
2. `test_ar023_bootstrap_seeds_with_strong_secret` — `CSS_BOOTSTRAP_REQUIRED: set CSS_BOOTSTRAP_ADMIN_PASSWORD (exactly 8 chars)`

**Not repaired in CI-001.** Not OV-002. Classification: `PREEXISTING_AR023_PASSWORD_POLICY_MISMATCH_ON_MAINTENANCE`. These will likely fail GitHub Gate-2 until a later honesty/auth task.

### OV-002 identity (not in Gate-2 list; not repaired)

Five tests still fail with `identity_probe_incomplete:creation_time,executable_path,executable_sha256`.

```
OV002_IDENTITY_FAILURE_COUNT=5
OV002_FAILURE_CLASSIFICATION=EXPECTED_CLOUD_ENV_IDENTITY_PROBE_INCOMPLETE
```

They are **not** Gate-2 blockers (Gate-2 does not invoke them). They are environment-dependent process-identity probes in this cloud container, same as RSM-001. Not a regression from this patch.

---

## Phase 5 — GitHub

Draft PR targeting **`css-v1.0.1-maintenance`**, not `main`. Not merged.

GitHub `pull_request` workflows are taken from the PR head; adding maintenance to `pull_request.branches` in this PR is what allows Gate-2 to run **before** merge. Push to the feature branch itself is **not** in `push.branches`, so only the PR event (and optional `workflow_dispatch`) is expected until merge.

```
YAML_VALIDATION=OK (PyYAML safe_load; GitHub `on:` key parses as True in YAML 1.1, accepted by Actions)
PR_CREATED=YES (filled after open)
PR_NUMBER=
PR_URL=
PR_BASE=css-v1.0.1-maintenance
PR_MERGED=NO
GITHUB_ACTIONS_TRIGGERED=PENDING_OBSERVATION
GITHUB_ACTIONS_RESULT=PENDING_OBSERVATION
```

---

## Phase 6 — next cloud task (not started)

From RSM-001 ledger, highest remaining with `can_do_from_cloud=YES` and `requires_FINANCE=NO` after this CI-001 (RSM-P1-01):

| Field | Value |
| --- | --- |
| ID | **RSM-P1-03** |
| Description | Reconcile Package D metadata drift: PR #62 is merged (`2b39141e`) but `agent_tasks/STATUS.md` still lists PKG-D as REVIEW; canonical status still says Package D is proposed vs `d53e665`. |
| Reason | Honesty of the canonical line; small; no runtime; unblocks operators/agents from treating Package D as still open. |
| Dependencies | None (PR #62 already merged) |
| Scope | SMALL |
| requires_FINANCE | NO |

RSM-P1-02 (PR #63 review) is not both-conditions (needs FINANCE for live dashboard proof). RSM-P1-04 execution modes is deferred until after COW-001.

---

## Safety

```
TRADING_LOGIC_CHANGED=NO
R7_CHANGED=NO
R14F_CHANGED=NO
ANTIBLEED_CHANGED=NO
POSITION_CAPS_CHANGED=NO
EXECUTION_MODES_CHANGED=NO
COW001_TOUCHED=NO
FINANCE_TOUCHED=NO
BROKER_CONTACTED=NO
LIVE_ORDER_SUBMITTED=NO
PR_MERGED=NO
```
