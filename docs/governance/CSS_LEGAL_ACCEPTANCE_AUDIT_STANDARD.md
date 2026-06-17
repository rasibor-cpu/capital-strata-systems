# CSS Legal Acceptance Audit Standard

## 1. Acceptance Audit Requirements
The system must generate a strict audit trail for all legal acceptance events. The schema must adhere to the following payload definition:

```json
{
  "event_type": "LEGAL_ACCEPTANCE",
  "user_id": "example_user_id",
  "session_id": "example_session_id",
  "risk_disclosure_version": "v1.0",
  "liability_policy_version": "v1.0",
  "live_acknowledgement_version": "v1.0",
  "accepted": true,
  "timestamp_utc": "2026-05-30T00:00:00Z",
  "ip_address": "optional_if_available",
  "user_agent": "optional_if_available"
}
```

## 2. Evidence Retention
Audit records must be retained permanently within the deployment environment's secure compliance storage. They may not be deleted or truncated during routine database maintenance.

## 3. Audit Reporting Requirements
Auditors must be able to retrieve the legal acceptance status of any session or user prior to trade execution authorization. The `legal_acceptance.py` module handles the in-memory validation of this audit evidence.

## 4. Compliance Verification Procedure
1. System checks `LegalAcceptanceRecord` matching the current user and session.
2. System validates `acceptance_version` against the current enforced version.
3. If missing, invalid, or outdated, return `AcceptanceValidationStatus.BLOCK`.
