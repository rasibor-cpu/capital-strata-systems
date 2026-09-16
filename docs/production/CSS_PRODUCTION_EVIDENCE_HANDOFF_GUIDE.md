# CSS Production Evidence Handoff Guide

Status: READY FOR EXTERNAL EVIDENCE COLLECTION — NO PRODUCTION AUTHORIZATION

## Purpose

The codebase is internally complete for the current V1 controlled-test scope.
The remaining production blockers require evidence generated outside the
application: counsel/regulatory decisions, provider contracts/configuration,
deployed-environment drills, reconciliation and owner sign-off.

Use:

    python scripts/validate_css_production_evidence_package.py <package.json>

The validator checks completeness, production scope and basic consistency. It
does not import the package into CSS and cannot authorize production charging,
money movement or trading.

## Required evidence categories

- CUSTOMER_AGREEMENT
- JURISDICTION_LEGAL_REVIEW
- SERVICE_MODE_APPROVALS
- PAYMENT_PROVIDER
- PAYMENT_COLLECTION_AUTHORITY
- NOTIFICATION_PROVIDER
- NOTIFICATION_POLICY
- SECURITY_OPERATIONS
- BACKUP_RESTORE
- INCIDENT_TABLETOP
- PRODUCTION_UAT
- RECONCILIATION
- OWNER_SIGNOFF

## Key safety rules

- TEST_ONLY, test: and SANDBOX references are rejected.
- Payment and notification providers must identify environment=production.
- Agreement ID/version and jurisdiction must match the package scope.
- Service modes must each have a legal/compliance determination. A mode may be
  APPROVED, RESTRICTED or PROHIBITED; the validator does not convert a
  restriction/prohibition into authority.
- Security evidence must affirm every required control.
- Owner sign-off must be an explicit APPROVE decision.
- A package that validates is only READY FOR HUMAN REVIEW.
- Validating a package never creates payment, trading, broker or production
  authority.

## Controlled import principle

After a package validates, an authorized human reviewer should compare every
reference against the underlying signed/provider/environment evidence. Only
then should the existing canonical approval repositories be populated through
a separately controlled administrative procedure.

No automatic evidence-to-production activation is intentionally provided.
