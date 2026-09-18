# CSS Sunday Production Closure Register

Target: Sunday, September 20, 2026 — 6:00 PM America/Toronto

Status rule:
- CLOSED = completed with acceptable evidence.
- READY FOR REVIEW = evidence package validates but still needs controlled human review/import.
- EXTERNAL BLOCKED = cannot be truthfully completed without an outside approver/provider/deployed environment.
- INTERNAL BLOCKED = unfinished application/automation work. This status is not acceptable at the Sunday deadline.

## Closure objective

By the target time, every known work item must be either:

1. CLOSED with evidence; or
2. EXTERNAL BLOCKED with an explicit owner, required artifact, acceptance criterion, and prepared request/template.

Production authorization is a separate decision and cannot be inferred from item closure.

## Current workstreams

| Workstream | Owner | Required evidence | Acceptance criterion | Current state |
| --- | --- | --- | --- | --- |
| Legal/regulatory | External counsel / compliance | JURISDICTION_LEGAL_REVIEW | Exact agreement/version/jurisdiction approved | EXTERNAL BLOCKED |
| Service modes | External counsel / compliance | SERVICE_MODE_APPROVALS | DISCOVER/CONFIRM/AUTO each determined | EXTERNAL BLOCKED |
| Independent pricing | Commercial owner + counsel | Initial launch pricing decision + counsel-confirmed agreement wording | No independent/customer-directed CSS charge at initial launch; future charge requires new version | INTERNAL CLOSED — COUNSEL WORDING CONFIRMATION REMAINS UNDER LEGAL REVIEW |
| Payment provider | Finance/payments | PAYMENT_PROVIDER | Production provider/merchant account approved | EXTERNAL BLOCKED |
| Payment authority | Finance + counsel | PAYMENT_COLLECTION_AUTHORITY | Exact agreement/version/jurisdiction approved | EXTERNAL BLOCKED |
| Notification provider | Operations/comms | NOTIFICATION_PROVIDER | Production provider/channel approved | EXTERNAL BLOCKED |
| Notification policy | Counsel/compliance | NOTIFICATION_POLICY | Timing/content approved for jurisdiction | EXTERNAL BLOCKED |
| Security/operations | Security/ops reviewer | SECURITY_OPERATIONS | All production controls independently verified | EXTERNAL BLOCKED |
| Backup/restore | Infrastructure/ops | BACKUP_RESTORE | Real environment encrypted off-site backup and restore/rollback drill | EXTERNAL BLOCKED |
| Incident response | Incident owner/ops | INCIDENT_TABLETOP | Operator tabletop completed and signed | EXTERNAL BLOCKED |
| Production UAT | UAT/business owner | PRODUCTION_UAT | Live-integration production-like UAT passes | EXTERNAL BLOCKED |
| Reconciliation | Finance/ops | RECONCILIATION | Provider settlement/customer ledger reconciliation passes | EXTERNAL BLOCKED |
| Release sign-off | Authorized release owner | OWNER_SIGNOFF | Explicit APPROVE after all evidence review | EXTERNAL BLOCKED |

## Internally completed foundations

- Full regression, expanded UAT and production-readiness drill are green.
- Backup/restore/rollback controls and tests are implemented.
- Customer/operator web integration is tested.
- Broker mutation boundaries are fail-closed.
- Production evidence validator/template is implemented.
- Sandbox evidence cannot satisfy production readiness.
- Period snapshots, override audit, posting-date governance and report export are implemented.
- No active backend TODO/FIXME/NOT_IMPLEMENTED production blocker remains for current V1 scope.

## Sunday closure command

Run:

    python scripts/report_css_production_closure.py       --internal-engineering-complete       --evidence-package <production-evidence.json>       --pricing-policy-approved

Exit code 0 means all identified workstreams have acceptable evidence ready for controlled review. It still does not authorize production.

## Final 5:00 PM closure audit

A final audit is scheduled one hour before the target. It must verify:
- branch convergence;
- all CI/UAT/readiness gates;
- evidence-package validity;
- pricing-policy approval evidence;
- zero INTERNAL BLOCKED workstreams;
- any remaining EXTERNAL BLOCKED workstream reported explicitly.
