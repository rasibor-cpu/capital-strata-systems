# CSS Deployment Approval Framework

**Programme:** Release Gate 2 — Final Close-Out (AR-016 / RB-011)  
**Effective:** 2026-07-22  
**CD mode:** `manual_with_approvals`  
**Automated production deploy:** **NOT PRESENT**

## Approval Authorities

* **Lead Engineer:** Technical soundness, test coverage, and code review.
* **Operations Manager:** Operational readiness, risk governance, and timing of deployment.
* **Security Officer:** Credential separation and auditing requirements (required for major updates).

## Approval Workflow (honest)

1. **Proposal:** Engineer creates a release candidate branch and opens a Pull Request.
2. **Automated Checks (CI only):** GitHub Actions Gate-2 CI enforces scoped `compileall` + bounded pytest on the release/PR paths (see `.github/workflows/css_gate2_release_ci.yml` and `css_governance.yml`).  
   - CI does **not** perform lint/type/security platform gates (those remain AR-043 residual).  
   - CI does **not** deploy to any environment.
3. **Review:** Peer engineers review the code for logic and architecture.
4. **Sign-off:** Lead Engineer and Operations Manager explicitly approve the release ticket (dual authorization). Security Officer for major updates.
5. **Execution (manual):** An authorized operator executes the controlled deployment steps in `docs/operations/CSS_PRODUCTION_DEPLOYMENT_PLAYBOOK.md` after dual sign-off. There is **no** automated production deploy pipeline in this repository.

## Required Evidence

* Link to passing Gate-2 CI workflow run for the release SHA.
* Completed Production Release Checklist / playbook pre-deployment section.
* Recorded `git_sha` and worktree custody state (see Evidence Custody Standard).
* Dual-authorization sign-off record.

## Deployment Authorization Rules

* Live trading remains **BLOCKED** / advisory-only unless a separate programme authorizes otherwise.
* Deployments during active market hours prohibited unless mitigating a SEV1 incident (and still dual-authorized).
* "No Friday Deployments" rule enforced for controlled production promotes.
* Unilateral deployment bypasses are forbidden.

## Explicit non-claims

* No Kubernetes / container orchestration CD in Gate 2.
* No automated promote-to-production job.
* Passing CI is necessary but **not** sufficient for production authorization.
