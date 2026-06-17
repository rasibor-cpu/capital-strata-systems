# CSS Operational Risk Register

## Overview
This document categorizes and tracks the primary operational risks facing Capital Strata Systems (CSS) in a production environment, defining required controls and severity levels.

## 1. Operational Risks
* **Description:** Risks arising from internal process failures, operator error, or misconfigured runtime states.
* **Severity Classification:** SEV2 (Moderate) to SEV1 (Critical)
* **Mitigation Controls:** Strict RBAC, execution gates, the operator kill switch, and dual-authorization deployment frameworks.
* **Ownership Assignment:** Operations Manager

## 2. Broker Risks
* **Description:** Risks associated with the downstream broker connection (e.g., IBKR), including API changes, margin limit breaches, or rejected orders.
* **Severity Classification:** SEV1 (Critical)
* **Mitigation Controls:** Continuous reconciliation, the Margin Trade Gate, and explicit fail-closed runtime behaviors on unknown broker states.
* **Ownership Assignment:** Head of Execution

## 3. Technology Risks
* **Description:** System downtime, resource exhaustion, database corruption, or compute infrastructure failure.
* **Severity Classification:** SEV1 (Critical)
* **Mitigation Controls:** Automated health monitoring, read-only dashboard decoupling, stateless containerized workloads, and rigorous recovery validations.
* **Ownership Assignment:** Lead Engineer

## 4. Data Risks
* **Description:** Stale, corrupt, or missing market data feeds and loss of internal ledger accuracy.
* **Severity Classification:** SEV1 (Critical)
* **Mitigation Controls:** Stale data detection thresholds, canonical persistence contracts, and immutable audit trails.
* **Ownership Assignment:** Data Engineering Lead

## 5. Security Risks
* **Description:** Unauthorized access, credential leakage, or exploitation of system vulnerabilities.
* **Severity Classification:** SEV1 (Critical)
* **Mitigation Controls:** Environment sanitization (no production secrets in lower environments), separated credentials per broker tier, and comprehensive audit ledgering.
* **Ownership Assignment:** Security Officer
