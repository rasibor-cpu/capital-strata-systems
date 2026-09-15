# CSS Commercialization Must-Have / Release Blocker Register

Status: AUTHORITATIVE for commercialization completion on this branch.

A commercialization item in this register is not optional. CSS must not be
declared commercially complete while any BLOCKER remains open.

## BLOCKER 1 — Customer Legal Contract & Trial Conversion Framework

Status: OPEN — RELEASE BLOCKER

Technical foundation is implemented and regression-validated: versioned agreement snapshot, immutable trial enrollment, system-derived exact trial expiry, immutable cancellation evidence, fail-closed persisted conversion assessment, mandatory affirmative acceptance UX, and a counsel-review customer-agreement draft. Jurisdiction-specific counsel approval remains outstanding and must be evidenced per agreement version before production charging.

Before any production charging is enabled, CSS must have a jurisdictionally
reviewed customer agreement that clearly and prominently states:

- every fee, platform/service charge, performance-compensation rate, billing
  cadence, charging base, cap/minimum (if any), and tax treatment;
- the distinction between CSS-attributable performance fees and any separate
  independent/customer-directed platform-use charge;
- the high-water-mark / loss-recovery methodology and the rule that recovered
  historical CSS-attributable losses are not charged again as fresh gain;
- attribution rules for CSS-advised accepted trades, customer-directed trades,
  materially modified CSS advice, mixed/partial execution, and external trades;
- when a fee can and cannot arise, including zero-fee loss and recovery-only
  cases;
- trial duration, the exact trial-expiry date/time, and the paid terms that will
  apply after the trial;
- a prominent automatic-conversion disclosure stating that the paid service
  begins if the customer does not cancel before the stated trial expiry;
- cancellation method, cancellation deadline, effective cancellation time,
  post-cancellation access rules, refunds/credits (if any), and renewal terms;
- affirmative acceptance mechanics and the legal effect of acceptance;
- investment-risk, no-guarantee, advisory/execution-scope, dispute, privacy,
  data-use, governing-law, and jurisdiction-specific disclosures.

### Required product controls

Production commercialization must fail closed unless all of the following are
true:

1. The exact agreement version is identified by immutable contract/version ID.
2. The customer affirmatively accepted that exact version.
3. Acceptance timestamp, customer/account identity, displayed pricing,
   trial-start timestamp, trial-expiry timestamp, and acceptance evidence are
   retained immutably.
4. The customer was shown the exact date/time on which the free trial ends and
   the paid terms begin.
5. Cancellation before the trial-expiry cutoff prevents automatic conversion.
6. A cancellation event is timestamped and retained as immutable evidence.
7. Trial conversion cannot occur if the governing contract is missing,
   superseded without required re-acceptance, rejected, withdrawn, expired, or
   otherwise invalid.
8. Any material change to pricing or charging basis requires a new versioned
   agreement and the legally required notice/re-acceptance process.
9. Charging authority is separate from trading/execution authority.
10. Legal review is completed for every jurisdiction in which CSS is offered.

### Mandatory customer-facing trial disclosure

The final UX must communicate, in substance and with jurisdictionally compliant
wording:

"Your free trial ends on [EXACT DATE/TIME]. If you do not cancel before that
time, your paid CSS service will begin automatically under the pricing and
terms shown here."

This disclosure must not be hidden solely in linked terms or fine print.

## BLOCKER 2 — Commercial Accounting / Costing Integrity

Status: IMPLEMENTED AND FULL-REGRESSION VALIDATED — PRODUCTION CERTIFICATION PENDING

- CSS-attributable performance fees use qualifying new economic gain only.
- Prior CSS-attributable losses must be recovered before fresh gain is
  chargeable.
- Independent/customer-directed economics remain separate from CSS performance
  attribution and high-water-mark accounting.
- External trades are excluded from CSS economics.
- Customer-facing summaries must reconcile exactly to immutable canonical
  records.
- Cross-currency calculations fail closed without approved FX evidence.

## BLOCKER 3 — Customer Profitability Transparency

Status: IMPLEMENTED AND FULL-REGRESSION VALIDATED — PRODUCTION CERTIFICATION PENDING

Customer surfaces must separately show:

- CSS-attributable realized P&L;
- prior-loss recovery;
- fresh new economic gain;
- CSS performance fee;
- independent/customer-directed realized P&L;
- independent platform/service charge, where applicable;
- gross customer result;
- total CSS charges;
- net customer result after CSS charges;
- advice-level audit trail: advice → customer P&L → recovered loss → fresh gain
  → CSS fee → customer retained.

## BLOCKER 4 — Production Charging / Money-Movement Gate

Status: TECHNICAL GATE IMPLEMENTED — APPROVAL EVIDENCE / PRODUCTION CERTIFICATION PENDING

A conjunctive fail-closed production charging gate is implemented. It requires canonical evidence of customer acceptance and paid-service eligibility, jurisdiction-specific legal approval for the exact agreement version, production commercialization certification, reconciliation verification, a structured production security/operations certification covering secrets, TLS, access control, audit logging, monitoring, backup/restore, rollback, incident response and dependency review, charging-control verification, and separately evidenced payment-collection authority.

Missing, pending, rejected, expired, stale, or scope-mismatched evidence blocks charging. The readiness API is GET/read-only and does not initiate payment.

Commercial release readiness additionally requires a named payment provider configuration to pass the read-only collection preflight. CSS ships with a disabled provider by default and exposes no live collection endpoint. An approved live adapter requires provider contract/account approval, idempotency, webhook verification, reconciliation, refund/chargeback controls, credential isolation, payment UAT, and rollback evidence.

No production release may enable fee debit, broker withdrawal, automatic payment execution, settlement, receivable collection, or other customer-funds movement until the remaining external approvals and production certification are complete.

## BLOCKER 5 — Production-like UAT & Launch Operations

Status: INTERNAL TOOLING IMPLEMENTED — REAL PRODUCTION-LIKE EVIDENCE / EXTERNAL APPROVALS PENDING

Commercial launch requires successful evidence for every mandatory production-like UAT scenario:

- trial signup;
- pre-expiry cancellation;
- automatic trial conversion;
- CSS loss period;
- loss-recovery-only period;
- fresh-gain performance fee;
- independent/customer-directed activity;
- FX conversion;
- correction/reversal;
- dispute/refund handling; and
- customer-statement reconciliation.

Missing, failed, pending, or blocked UAT scenarios prevent UAT completion.

Launch operations must also maintain:

- jurisdiction-approved customer-notification policies;
- immutable notification intents;
- jurisdiction/service-mode approval status;
- launch evidence dossier completeness; and
- a read-only commercialization operations console exposing blockers.

The launch dossier requires approved evidence for the customer agreement, jurisdiction legal review, technical validation, security certification, reconciliation certification, payment-provider/collection authority, production UAT, rollback plan, and owner sign-off.

A dedicated commercialization-UAT CI workflow now exercises the core trial, attribution, loss-recovery, independent-charge, FX, correction/reversal, payment-observation, security, and charging-gate test families. This automated evidence does not replace production-like environment UAT.

Customer notification delivery is provider-gated and disabled by default. CSS exposes a read-only notification delivery preflight but no send endpoint until a provider/channel is separately approved.

The canonical launch dossier can be exported through a read-only API and compared against the required evidence categories.

## Release-status evidence

CSS now has an evidence-based commercialization release assessment. The release status requires an immutable technical-validation record plus a successful canonical production-charging assessment. The read-only `/api/v1/commercialization-release/readiness` surface reports explicit blocker codes and never grants trading or broker execution authority.

## Full-test release-candidate status

Status: RELEASE-CANDIDATE TOOLING IMPLEMENTED — VALIDATION PENDING

CSS now has a guarded isolated full-test mode with deterministic sandbox payment
and notification providers, synthetic TEST_ONLY evidence, a disposable database,
and an integrated readiness runner.

Full-test readiness is intentionally distinct from production-commercial
readiness. The sandbox provider is prohibited from satisfying production
payment preflight, so a full-test release candidate must show:

- ready_for_full_testing = true;
- production_commercial_ready = false;
- mandatory UAT complete;
- synthetic launch dossier complete;
- sandbox payment and notification simulations successful;
- trading/broker execution authority = false; and
- external money movement = false.

The release-candidate workflow must pass governance, full regression, dedicated
commercialization UAT, and integrated full-test readiness on the candidate SHA.

## External evidence still required

The remaining blockers cannot be truthfully self-approved by the application:

- jurisdiction-specific counsel/regulatory approval for the exact customer
  agreement and each service mode offered;
- final approval of the independent/customer-directed platform-charge policy;
- production security/operations certification based on real environment
  evidence, including restore and rollback tests;
- selection/contracting/configuration of a live payment provider and approved
  collection authority;
- approval of jurisdiction-specific customer notification policies and a live
  delivery provider;
- production-like UAT evidence for all mandatory scenarios;
- reconciliation certification against the selected provider/environment; and
- authorized owner/release sign-off.

Until these records exist and are approved, the system remains fail-closed for
commercial release and live collection.

## Release rule

CSS may be described as technically advanced while these blockers remain open,
but it must not be described as fully commercially complete or production
charging-ready until every required blocker is independently verified and
closed.
