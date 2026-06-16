# AI Governance Phase 2: Governance Auditor Agent

## Purpose
The Governance Auditor Agent is the first implementation of the CSS AI Governance Layer. Its sole responsibility is to ingest repository metadata, analyze governance declarations, and output deterministic findings regarding authority-drift or canonical violations.

## Authority Boundaries
The Governance Auditor Agent is strictly **read-only**:
- It cannot execute trades.
- It cannot interact with broker adapters.
- It cannot alter live execution configurations.
- It cannot write to the file system.
- It cannot modify risk parameters.

## Inputs
The agent accepts structured `metadata` dictionaries containing representations of:
- Authority Register compliance status.
- Current authority declarations.
- Certification reference records.

## Outputs
The agent outputs an `AuditResult` containing:
- `status`: Either `PASS`, `FAIL_CLOSED`, or `FINDINGS`.
- `findings`: A list of `AuditFinding` objects detailing the severity, issue, and affected component.

## Fail-Closed Behavior
If the agent is invoked without governance metadata, or if the metadata is missing the required `authority_register` key, the agent immediately defaults to a `FAIL_CLOSED` status, preventing downstream processes from proceeding under the false assumption of governance compliance.

## Test Evidence
The agent is backed by an explicit test suite (`tests/test_governance_auditor_agent.py`) proving:
- Valid governance metadata returns PASS.
- Missing authority register returns FAIL_CLOSED.
- Duplicate authority declarations are correctly flagged.
- Incomplete certification references are correctly flagged.
- The agent has zero execution or broker side-effects (validated by structural inspection).

## Future Integration Path
In Phase 109B, this agent logic will be mapped to a CI/CD pre-commit or pre-merge hook to autonomously block Pull Requests that introduce authority drift or bypass canonical gates.
