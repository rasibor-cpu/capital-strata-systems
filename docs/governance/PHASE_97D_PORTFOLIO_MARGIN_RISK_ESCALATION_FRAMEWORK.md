# PHASE 97D: PORTFOLIO MARGIN RISK ESCALATION FRAMEWORK

## Objective
Establish an institutional portfolio margin risk escalation monitor. This framework evaluates portfolio-level margin snapshots and maps them to an authoritative risk escalation level and response message.

## Read-Only Governance Policy
This phase is explicitly an **observability-only** implementation.
- No execution authority is granted.
- No broker behavior is changed.
- No risk gate behavior is changed.
- No order-routing behavior is changed.

## Authoritative Data Flow
The framework exclusively consumes the `PortfolioMarginSnapshot` (the canonical contract) and leverages the `PortfolioMarginSummaryBuilder` to evaluate margin stress without creating any synthetic values or engaging live execution systems.

## Escalation Model

| Margin State       | Escalation Required | Escalation Level | Action |
| ------------------ | ------------------- | ---------------- | ------ |
| `NORMAL`           | False               | 0                | None. Portfolio margin is healthy. |
| `WARNING`          | True                | 1                | Monitor closely. |
| `RESTRICTED`       | True                | 2                | New risk must be restricted. |
| `CRITICAL`         | True                | 3                | Prepare for possible intervention. |
| `LIQUIDATION_RISK` | True                | 4                | Immediate intervention required. |

## Outputs
The monitor produces a unified risk assessment dictionary:
```json
{
    "risk_state": "...",
    "risk_banner": "...",
    "escalation_level": 0,
    "escalation_required": false,
    "escalation_message": "...",
    "timestamp": "..."
}
```
This data drives institutional visibility on desktop and mobile dashboards while respecting Phase 1/Phase 2 governance boundaries.
