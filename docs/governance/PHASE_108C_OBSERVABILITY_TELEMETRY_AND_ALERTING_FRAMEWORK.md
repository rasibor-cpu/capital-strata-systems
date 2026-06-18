# Phase 108C Observability, Telemetry, and Alerting Framework

## A. Observability Objectives

The primary objective of the CSS Observability Framework is to guarantee that the system's strict fail-closed operations are deeply visible to operators in real-time. Since CSS relies on denying unsafe states intrinsically, operators require external alerts when risk bounds are hit, ensuring the silence of the application is due to safety, not a silent failure.

## B. Telemetry Inventory

CSS strictly categorizes telemetry to ensure that sensitive capital boundaries are logged safely:
- **Runtime Telemetry**: Process memory limits, boot states, environment variable presence bounds (e.g., `REA_ENGINE_MODE`).
- **Broker Telemetry**: Gateway ping times, connection timeouts, adapter resolution outputs (`NotImplementedError` captures).
- **Execution Telemetry**: Block rates inside the `ExecutionGate`, dummy payload rejections, API response payloads from external hubs.
- **PnL Telemetry**: Real-time snapshot diffs, canonical metric evaluations, and persistence sync rates.
- **Regime Telemetry**: Active market state, detected volatility spikes, macro mutation events.
- **Risk Telemetry**: Margin bound evaluations, `AntiBleedGuard` activation triggers.
- **Security Telemetry**: Session validation failures, RBAC token drops, unauthenticated execution attempts.

## C. Alerting Inventory

- **Critical Alerts**: `AntiBleedGuard` threshold breached; Core API unreachable; `DATABASE_URL` unreachable; Broker token revocation; Engine crashed and cannot restart.
- **Warning Alerts**: Elevated execution latency; Single-order margin rejection; PnL snapshot sync lag; Non-fatal retry attempts triggered.
- **Informational Alerts**: Daily PnL summary; Regime mutation identified; Session created safely; Application booted in `SIMULATION` mode.

## D. Alert Severity Model

- **P0 (Critical)**: Total system failure or unauthorized capital exposure attempt. Requires immediate manual operator intervention via kill-switches.
- **P1 (High)**: Core dependencies unreachable (e.g., Broker APIs down). System is safely failed-closed but requires operator acknowledgment.
- **P2 (Medium)**: Component degradation (e.g., specific telemetry feed missing). System continues operating safely under degraded metrics.
- **P3 (Low)**: Informational boundary hits (e.g., ordinary margin blocks on oversized sizing). Evaluated during daily operational review.

## E. Operational Ownership Matrix

- **L1 Support (Automated Systems)**: Triggers fail-closed evaluations intrinsically, suppressing downstream actions and logging locally.
- **L2 Support (Risk Officers)**: Responsible for reviewing P1 and P2 latency metrics to ensure network topologies are sound.
- **L3 Support (Core Engineering)**: Responsible for responding to P0 fatal breaks or structural API mismatches forcing engine halts.

## F. Approved Alert Destinations

To support real-time execution bounds, telemetry is explicitly authorized to be routed to the following remote hubs (via securely injected integration tokens):
- **PagerDuty**: For P0 and P1 incident escalation.
- **Slack (Risk Channel)**: For P2 warnings and major informational regime mutations.
- **Email**: For daily summary rollups and offline audits.
- **SMS**: For emergency L3 paging on hard-halts.
- **Dashboard**: For real-time visual inspection of local persistence states.

## G. Telemetry Retention Requirements

- **Execution/Risk Telemetry**: Retained for 7 years to comply with institutional trade auditing bounds.
- **Security Telemetry**: Retained for 1 year for intrusion detection forensics.
- **Broker/Network Latency**: Retained for 30 days for infrastructure optimization.

## H. Incident Escalation Model

1. **System Halt**: Application intrinsically blocks execution due to missing limit/token.
2. **P0 Trigger**: Log adapter pushes a P0 payload to the PagerDuty integration hook.
3. **Paging**: PagerDuty initiates SMS/Phone tree to L3 engineering.
4. **Resolution**: Operator validates bounds, remediates the environment variable (e.g. rotates the broker key), and restarts the CSS execution container.
5. **Post-Mortem**: Telemetry logs are reviewed against `AntiBleedGuard` structures to ensure capital was never exposed during the degradation.

## I. Production Readiness Status

With this framework codified, GAP-108-02 is officially closed from a structural governance perspective. The CSS operational architecture fully supports routing native Python logs to explicit off-site ingestion endpoints for paging, removing the reliance on local dashboard tailing.
