# Phase 109C: GitHub Actions AI Governance Workflow Integration

## A. Workflow Objective
The objective of this phase is to construct the first actionable GitHub Actions workflow (`ai-governance-sweep.yml`) that actively enforces the AI Governance Layer on pull requests. This integrates the executable framework built in Phase 109B directly into the CI/CD pipeline as a deterministically gated pre-merge check.

## B. Trigger Conditions
The workflow is configured to execute automatically under the following conditions:
- **`pull_request`**: Any PR targeting the `css-evening-consolidation-2026-06-09` or `main` branches.
- **`workflow_dispatch`**: Manual triggering via the GitHub Actions UI for diagnostic and ad-hoc validation.

## C. Read-Only Permissions
To adhere to the fail-closed and strictly read-only execution constraints defined in the AI Governance Architecture:
- The GitHub Actions token is deliberately restricted using `permissions: contents: read`.
- This ensures that if any part of the execution framework is compromised, the pipeline cannot write back to the repository, push code, or mutate artifacts.

## D. Checks Executed
The job provisions an Ubuntu runner with Python 3.11, installs necessary dependencies (e.g., `pytest`), and then sequentially performs:
1. **AI Governance Sweep**: `python scripts/run_ai_governance_sweep.py` - Runs the full aggregation of the Auditor, Certification, Repository, and Operations Commander agents.
2. **Test Suite Execution**: `python -m pytest` - Ensures no regressions have broken the underlying architectural logic.

## E. Fail-Closed Behavior
Because the workflow uses standard bash script behavior implicitly, any non-zero exit code immediately aborts the run and flags the check as failed on the PR.
- If the governance sweep detects missing metadata, malformed schemas, or an `AUTHORITY_DRIFT`, the script returns exit code `1`.
- The GitHub PR status will immediately mirror this `FAIL_CLOSED` or `NOT_READY` state, blocking the merge.

## F. Secret Handling
This workflow utilizes absolutely zero execution secrets.
- There are no Alpaca tokens mapped.
- There are no database credentials exposed.
- All structural validation runs statelessly against the file system provided by the `actions/checkout` step.

## G. Future CI/CD Enhancements
While this implements the fundamental pre-merge check, subsequent pipeline phases will expand to:
- Nightly Scheduled sweeps testing expiration bounds on canonical certifications.
- Abstract Syntax Tree (AST) scanning within the `RepositoryIntelligenceAgent` to dynamically parse Python files rather than depending purely on static metadata.

## H. Validation Evidence
This integration was verified locally using the same command sequence present in the runner:
- `python scripts/run_ai_governance_sweep.py` returns `exit 0` under nominal structural conditions.
- `python -m pytest` executes seamlessly with no execution side-effects.
