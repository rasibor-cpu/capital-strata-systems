# CSS Production Security & Operations Certification Checklist

Status: REQUIRED RELEASE EVIDENCE — NOT YET CERTIFIED

A production security/operations certification is APPROVED only when every
control below has current immutable evidence.

## Mandatory controls

1. Secrets management
   - no plaintext production secrets in source/configuration;
   - production credentials stored in approved secret storage;
   - rotation/revocation procedure tested.

2. TLS / transport security
   - production endpoints require approved TLS;
   - certificate lifecycle and expiry monitoring verified;
   - insecure transport fails closed.

3. Access control
   - least-privilege production roles;
   - privileged access auditable;
   - terminated/revoked access process verified.

4. Audit logging
   - contract, pricing, billing, approval, payment-readiness and admin changes
     are attributable and retained;
   - logs are tamper-resistant to the required standard.

5. Monitoring / alerting
   - release-readiness, reconciliation, provider, payment and security failures
     produce actionable alerts;
   - alert ownership/escalation documented.

6. Backup / restore
   - backup scope documented;
   - restore has been tested from production-like data;
   - recovery evidence retained.

7. Rollback
   - application/database rollback procedure tested;
   - billing/payment controls default disabled after rollback until revalidated.

8. Reconciliation
   - customer economics, invoices/receivables, external payment observations,
     and provider settlement can be reconciled;
   - discrepancies fail closed.

9. Incident response
   - security/payment incident owners and escalation paths documented;
   - customer/regulatory notification decision path documented.

10. Dependency/vulnerability review
    - dependency inventory reviewed;
    - material vulnerabilities resolved or explicitly risk-accepted before
      certification.

## Certification rule

The structured ProductionSecurityOperationalCertification record must show
APPROVED and every control above as verified. A legacy boolean or verbal
assertion cannot substitute for this record.

This certification does not grant trading/broker execution authority.
