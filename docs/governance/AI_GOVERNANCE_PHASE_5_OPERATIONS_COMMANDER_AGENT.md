# AI Governance Phase 5: Operations Commander Agent

## Purpose
The Operations Commander Agent is the fourth implementation of the CSS AI Governance Layer. Its primary function is to serve as an intelligent, read-only operational oversight plane. It ingests runtime telemetry, alert streams, and incident payloads, classifies their severity, and maps them directly to canonical escalation paths and runbook references.

## Authority Boundaries
The Operations Commander Agent is strictly **read-only**:
- It cannot execute trades.
- It cannot interact with broker adapters.
- It cannot alter live execution configurations.
- It cannot write to the file system.
- It cannot modify risk parameters or clear alerts automatically.

## Inputs
The agent accepts a structured `metadata` dictionary containing:
- A list of `telemetry` events, each containing properties such as `type`, `level` (e.g., INFO, WARNING, ERROR, P0), `description`, and optional `runbook_mappings`.

## Outputs
The agent outputs an `OperationsResult` containing:
- `status`: Either `OK`, `FAIL_CLOSED`, or `INCIDENT`.
- `incidents`: A list of `IncidentSummary` objects detailing the severity, description, designated escalation level (L1/L2/L3), and runbook references.

## Fail-Closed Behavior
If the agent is invoked without metadata, or if the metadata payload is malformed (e.g., missing the `telemetry` key or providing a non-list type), the agent immediately defaults to `FAIL_CLOSED`, escalating the failure as a CRITICAL/L3 event. This ensures that operational telemetry outages are immediately treated as high-priority incidents.

## Test Evidence
The agent is backed by an explicit test suite (`tests/test_operations_commander_agent.py`) proving:
- Valid info-level telemetry categorizes the system as `OK`.
- Missing or malformed telemetry data triggers `FAIL_CLOSED` and escalates.
- Incident payloads properly map to `P0`, `ERROR`, or `WARNING` severities.
- Escalation levels (L1/L2/L3) are correctly inferred from severity.
- Runbook references are correctly extracted and returned.
- The agent has zero execution or broker side-effects (validated by structural inspection).

## Future Integration Roadmap
In future phases, the Operations Commander Agent will be connected as a read-only listener to the centralized log stream defined in Phase 108C, continuously outputting situational awareness reports to the human operator without possessing any active mitigation controls itself.
