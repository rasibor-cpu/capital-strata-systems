# CSS Commercialization Must-Have / Release Blocker Register

Status: AUTHORITATIVE for commercialization completion on this branch.

A commercialization item in this register is not optional. CSS must not be
declared commercially complete while any BLOCKER remains open.

## BLOCKER 1 — Customer Legal Contract & Trial Conversion Framework

Status: OPEN — RELEASE BLOCKER

Technical foundation implemented on `css-costing-improvements-2`: versioned agreement snapshot, immutable trial enrollment, exact trial expiry, immutable cancellation evidence, fail-closed persisted conversion assessment, and no payment/money-movement authority. Final contract drafting, jurisdiction-specific legal review, customer UX acceptance flow, and production certification remain outstanding.

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

Status: IMPLEMENTED IN BRANCH — VALIDATION / CERTIFICATION PENDING

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

Status: IMPLEMENTED IN BRANCH — VALIDATION / CERTIFICATION PENDING

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

Status: OPEN

Current commercialization work remains documentary/shadow/read-only.

No production release may enable fee debit, broker withdrawal, automatic
payment execution, settlement, receivable collection, or other customer-funds
movement until the legal-contract blocker, regulatory review, charging
authorization controls, reconciliation, and production certification are all
complete.

## Release rule

CSS may be described as technically advanced while these blockers remain open,
but it must not be described as fully commercially complete or production
charging-ready until every required blocker is independently verified and
closed.
