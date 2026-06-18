# AI Governance Phase 3: Certification Agent

## Purpose
The Certification Agent is the second implementation of the CSS AI Governance Layer. Its responsibility is to monitor, ingest, and validate certification metadata, ensuring that the repository's governance artifacts (Phases 107 and 108) remain compliant, unbroken, and unexpired.

## Authority Boundaries
The Certification Agent is strictly **read-only**:
- It cannot execute trades.
- It cannot interact with broker adapters.
- It cannot alter live execution configurations.
- It cannot write to the file system.
- It cannot modify risk parameters.

## Inputs
The agent accepts a structured `metadata` dictionary containing:
- An array of `certifications`, where each item has a `reference_id`, `status` (e.g., `APPROVED`, `EXPIRED`, `DEPRECATED`), and optional `depends_on` chains.

## Outputs
The agent outputs a `ReadinessSummary` containing:
- `status`: Either `READY`, `FAIL_CLOSED`, or `NOT_READY`.
- `findings`: A list of `CertificationFinding` objects detailing the severity, issue, and affected reference ID.

## Fail-Closed Behavior
If the agent is invoked without metadata, or if the metadata payload is malformed (e.g., missing the `certifications` key or providing a non-list type), the agent immediately defaults to `FAIL_CLOSED`. This ensures that a missing payload cannot be misinterpreted as a "clean" validation pass.

## Test Evidence
The agent is backed by an explicit test suite (`tests/test_certification_agent.py`) proving:
- Valid certification inventory passes and returns `READY`.
- Missing certifications (e.g., missing Phase 107 or 108 documents) are flagged as `HIGH` severity.
- Incomplete certification chains (dependencies that are not `APPROVED`) are flagged.
- Expired or deprecated certifications are flagged.
- Malformed inputs securely trigger `FAIL_CLOSED`.
- The agent has zero execution or broker side-effects (validated by structural inspection).

## Future Integration Roadmap
In Phase 109C, this agent logic will be mapped to automated artifact generators in the CI/CD pipeline, parsing the actual `.md` files and repository state to dynamically build the JSON metadata payload that this agent evaluates.
