# CSS Evidence Custody Standard

**Document type:** Release Gate 2 evidence chain-of-custody  
**Remediation:** AR-002  
**Effective date:** 2026-07-21  
**Baseline source SHA:** `4ea738d86c167373deccbe4edf217e929de4414d`  
**Canonical release status:** `docs/release/CSS_CANONICAL_RELEASE_STATUS.md`

This standard defines how production-certification evidence must be captured, stored, referenced, and accepted. It does **not** modify application runtime behaviour.

---

## 1. Purpose

Prevent untracked worktree artefacts, fixture URIs, or undated reports from being treated as Production Certification proof.

Every accepted certification artefact must be traceable to:

1. Repository source evidence (paths / symbols)
2. Tests executed (commands + exit codes)
3. Documentation / Gate reference
4. Audit finding or Remediation ID
5. Immutable Git SHA (and preferably branch)

---

## 2. Evidence classes

| Class | Examples | Allowed as Production Certification proof? |
| --- | --- | --- |
| A — Source-bound | Tracked code, tracked tests, tracked governance docs at a SHA | Yes, as supporting evidence |
| B — SHA-bound run artefact | Compile/pytest/OAT/endurance/DR outputs with SHA + command + exit code | Yes, when stored under custody rules |
| C — Worktree / untracked local | `runtime_reports/` without custody header; local `.venv`; scratch logs | **No**, until promoted under §4 |
| D — Synthetic fixture | `evidence://phase181/...`, clock-injected endurance | **No** for production profile (see AR-045) |
| E — Historical certificate | Superseded RC1 GO docs | **No** for current production claims (see AR-001) |

---

## 3. Mandatory custody header

Every Class B artefact MUST begin with (or be accompanied by) a custody manifest containing:

```text
evidence_id:           CSS-EVD-YYYYMMDD-NNN
remediation_ids:       AR-XXX[, AR-YYY]
audit_refs:            Master Audit §... / RB-XXX
gate:                  Release Gate 2
git_branch:            <branch>
git_sha:               <full sha>
worktree_state:        CLEAN | INVENTORIED
worktree_inventory:    <path to inventory file if INVENTORIED>
command:               <exact command>
exit_code:             <integer>
started_at_utc:        <ISO-8601>
finished_at_utc:       <ISO-8601>
operator:              <role or name>
approver:              <role or name, if required>
artifact_sha256:       <hash of primary output>
related_paths:         <repo paths exercised>
```

Template: `docs/release/CSS_EVIDENCE_CUSTODY_MANIFEST_TEMPLATE.md`

---

## 4. Storage and promotion rules

1. **Do not commit** generated caches, `.venv`, or credential-bearing files.
2. Generated certification packages under `runtime_reports/` are **Class C** until a custody manifest is attached and the package is either:
   - stored in an approved external evidence archive bound to `git_sha`, or
   - committed only when a Gate 2 owner explicitly accepts them as Class B and the files contain the custody header.
3. Uncommitted Phase 181A / 182A source remains **non-released**; it must not appear in production claims (AR-001).
4. Before recording Gate 2 certification evidence, the operator must run:

```powershell
git status --short
git rev-parse HEAD
git branch --show-current
```

5. If the worktree is not clean, either:
   - clean/stash unrelated changes, **or**
   - produce a dated **worktree inventory** listing every modified/untracked path and mark `worktree_state: INVENTORIED`.

Release evidence captured against an undocumented dirty worktree is **invalid**.

---

## 5. Release checklist — evidence gate

Before any Production Certification claim:

- [ ] Canonical status reviewed: `docs/release/CSS_CANONICAL_RELEASE_STATUS.md`
- [ ] `git_sha` recorded and matches the candidate under test
- [ ] Worktree is `CLEAN` or `INVENTORIED` with attached inventory
- [ ] Each Critical evidence file has a custody manifest (§3)
- [ ] Commands and exit codes recorded (no missing exit status)
- [ ] Artefacts mapped to AR / RB IDs
- [ ] No Class D fixtures used as production proof
- [ ] No superseded Class E GO scorecard used as current authority
- [ ] Owners acknowledged per `docs/governance/CSS_REPOSITORY_OWNERSHIP_REGISTER.md`

---

## 6. Traceability matrix (minimum)

| Certification dimension | Required evidence class | Typical commands / paths | Linked ARs / RBs |
| --- | --- | --- | --- |
| Compile | B | `python -m compileall ...` | AR-012 / RB-001 |
| Bounded regression | B | `pytest ...` with exit code | AR-012, AR-005 / RB-001, RB-004 |
| OAT | B | Authorized OAT runbook outputs | AR-013 / RB-001 |
| Endurance | B | Wall-clock samples (not clock injection) | AR-014 / RB-012 |
| Disaster recovery | B | Backup/restore drill log + timings | AR-015 / RB-012 |
| Health fail-closed | A+B | Source + tests for empty-check behaviour | AR-009, AR-010 / RB-008 |
| Execution honesty | A+B | Unified pipeline / paper journal proof | AR-006, AR-007 / RB-005, RB-006 |
| Release authority | A | Canonical status + supersession table | AR-001 / RB-002 |
| Evidence integrity | A | This standard + inventories | AR-002 / RB-003 |

---

## 7. Invalidation conditions

Evidence is automatically invalid if any of the following is true:

- Missing or mismatched `git_sha`
- Missing exit code / command
- Worktree dirty without inventory
- Fixture URI presented as observed production evidence
- Artefact predates a material source change on the claimed SHA
- Claim conflicts with `CSS_CANONICAL_RELEASE_STATUS.md`

---

## 8. Related documents

- `docs/release/CSS_CANONICAL_RELEASE_STATUS.md`
- `docs/release/CSS_EVIDENCE_CUSTODY_MANIFEST_TEMPLATE.md`
- `docs/release/CSS_AUDIT_REMEDIATION_REGISTER.md`
- `docs/release/CSS_RELEASE_BLOCKER_MATRIX.md`
- `docs/release/CSS_RELEASE_GATE_2_PLAN.md`
- `CSS_V1_MASTER_COMPLETION_AUDIT.md`

---

*AR-002 remediation artifact. Does not authorize deployment, restart, broker authentication, or live trading.*
