# CSS UAT Cycle 1 — Formal Acceptance Matrix

Baseline under test: css-full-test-ready-2026-09-15
UAT branch: css-uat-cycle1-2026-09-16
Date: 2026-09-16

## Acceptance rule

UAT passes only when every mandatory scenario below has executable evidence and
all required CI gates are green on the same candidate SHA.

A failure, blocked scenario, missing scenario, broken customer/operator smoke
flow, or regression failure makes the cycle NOT ACCEPTED.

## Mandatory scenarios and evidence

| Scenario | Acceptance criterion | Primary evidence |
| --- | --- | --- |
| TRIAL_SIGNUP | Customer can enroll only against the exact governing agreement; expiry is system-derived. | tests/test_trial_contract_enrollment_service.py |
| TRIAL_CANCEL_BEFORE_EXPIRY | Timely cancellation blocks conversion. | tests/test_trial_conversion_assessment_service.py |
| TRIAL_CONVERSION | Expired uncancelled trial is documentarily eligible but cannot itself move money. | tests/test_trial_conversion_assessment_service.py |
| CSS_LOSS_PERIOD | CSS fee is zero on attributable loss. | tests/test_advice_profitability.py |
| CSS_RECOVERY_ONLY | Recovery of prior loss alone earns no CSS fee. | tests/test_advice_profitability.py |
| CSS_FRESH_GAIN_FEE | Fee applies only to qualifying fresh gain after recovery. | tests/test_advice_profitability.py |
| INDEPENDENT_CUSTOMER_DIRECTED | Independent activity stays outside CSS performance fee/HWM accounting. | tests/test_independent_trade_economics.py |
| FX_CONVERSION | FX conversion evidence is required and fee selection remains reconciled. | tests/test_com002vw_fx_and_final_fee_selection.py |
| CORRECTION_REVERSAL | Corrections/reversals preserve immutable accounting lineage. | tests/test_com002m_invoice_correction.py; tests/test_com002o_receivable_reversal.py |
| DISPUTE_REFUND | Credit/refund/dispute handling does not silently rewrite prior economics. | tests/test_com002s_receivable_credit.py |
| CUSTOMER_STATEMENT_RECONCILIATION | Customer-level totals reconcile across CSS and independent paths. | tests/test_customer_profitability_summary_service.py |
| CONTRACT_VERSION_MISMATCH_BLOCKED | Unknown/stale contract version cannot enroll. | tests/test_trial_contract_enrollment_service.py |
| RESTART_PERSISTENCE | Governing agreement survives close/reopen of the persistent DB. | tests/test_uat_restart_persistence.py |
| PAYMENT_SANDBOX_IDEMPOTENCY | Duplicate sandbox payment request with same key produces one deterministic simulated result. | tests/test_sandbox_commercial_providers.py |
| NOTIFICATION_SANDBOX_IDEMPOTENCY | Duplicate sandbox notification produces one deterministic simulated result. | tests/test_sandbox_commercial_providers.py |
| SANDBOX_PROVIDER_CANNOT_UNLOCK_PRODUCTION | Sandbox provider cannot make production commercialization ready. | tests/test_full_test_readiness_runner.py |
| LAUNCH_OPS_READ_ONLY | Launch dossier and notification preflight surfaces are GET-only; Launch Ops exposes no money movement. | tests/test_final_launch_readonly_routers.py; tests/test_full_test_readiness_runner.py |
| CUSTOMER_WEB_SMOKE | Customer/operator pages, required API routes, disclosures and safety labels render. | dashboard/web/web_smoke_test.py |
| BROKER_EXECUTION_FAIL_CLOSED | Broker env flag alone cannot execute; canonical RBAC/live-arm and mutation wall remain mandatory. | tests/test_security_phase_alpha.py |

## Required CI gates

- CSS Governance Validation
- CSS Full Regression Remote
- CSS Commercialization UAT
- CSS Full Test Release Candidate
- CSS Simulator Academy when triggered by touched scope

## Safety expectations

Even after UAT passes:

- production_commercial_ready must remain false in the synthetic sandbox fixture;
- broker_execution_authority must remain false;
- trading_execution_authority must remain false;
- external money movement must remain false; and
- no real payment, notification, or broker credentials are used.

## Defect handling

Any reproducible UAT defect is fixed on the UAT branch, retested in the focused
scenario, then the full applicable CI gates are rerun before acceptance.

No production approval is inferred from successful UAT.
