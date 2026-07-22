# Batch 1 — Consolidated Root Cause Analysis

**Programme:** Release Gate 2 — Final Close-Out  
**Batch:** 1 — Deployment readiness  
**Scope:** AR-016 / RB-011  
**Date:** 2026-07-22  
**Plan:** `docs/release/CSS_RG2_FINAL_CLOSEOUT_PLAN.md`

## Shared theme

Deployment authority documents claimed **automated CI/CD** while repository evidence shows only partial/weak CI and **no deploy automation**. Shared corrective principle: **fail-closed honesty + real CI gates + documented manual-with-approvals CD** — without inventing a Kubernetes platform.

## Root causes

1. `css_governance.yml` is structurally invalid / weak (broken `on:` indentation); banner implies pass without pytest gates.
2. `CSS_DEPLOYMENT_APPROVAL_FRAMEWORK.md` asserts “100% tests + linting” and “Automated pipeline deploys to production.”
3. Production playbook covers local pilot startup, not staged promotion / dual-auth promote / post-deploy verify / rollback targets.
4. Master Audit correctly flagged absent CD; remediation was deferred until Final Close-Out.

## Smallest coherent remediation

1. Replace Gate-2 CI workflow with valid YAML: checkout, Python, compileall (scoped), bounded Gate-2 pytest suite, fail-closed.
2. Rewrite approval framework: CI gates + dual-auth **manual** promote; no automated deploy claim.
3. Extend production deployment playbook with controlled CD steps (manual-with-approvals).
4. Expose `deployment_honesty_status()` contract (`ci_cd_automation_present=False`, `cd_mode=manual_with_approvals`).

## Non-goals (Batch 1)

- Full lint/type/security platform (AR-043)
- Dockerfile/K8s
- Automated production deploy jobs
- AR-034 risk lean path

## Expected closure

| Item | Recommendation |
| --- | --- |
| AR-016 | CLOSE if exit criteria met |
| RB-011 | CLOSED |
