# CSS Deployment Approval Framework

## Approval Authorities
* **Lead Engineer:** Responsible for technical soundness, test coverage, and code review.
* **Operations Manager:** Responsible for operational readiness, risk governance, and timing of deployment.
* **Security Officer:** Responsible for validating credential separation and auditing requirements (required for major updates).

## Approval Workflow
1. **Proposal:** Engineer creates a release candidate branch and opens a Pull Request.
2. **Automated Checks:** CI pipeline enforces 100% test pass rate and linting constraints.
3. **Review:** Peer engineers review the code for logic and architecture.
4. **Sign-off:** Lead Engineer and Operations Manager explicitly approve the release ticket.
5. **Execution:** Automated pipeline deploys to production following approval.

## Required Evidence
* Link to passing test pipeline run.
* Link to completed Production Release Checklist.
* Hash chain of the release artifact.

## Deployment Authorization Rules
* Deployments strictly prohibited during active market hours unless mitigating a SEV1 incident.
* "No Friday Deployments" rule enforced strictly.
* Unilateral deployments bypasses are forbidden; dual-authorization is mandatory via GitHub protection rules.
