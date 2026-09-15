# CSS Payment Provider Integration Specification

Status: PROVIDER-AGNOSTIC FOUNDATION COMPLETE — LIVE PROVIDER NOT SELECTED

## Current safety posture

CSS contains:

- a PaymentCollectionProvider port;
- a default DisabledPaymentCollectionProvider that always refuses collection;
- immutable payment-provider configuration evidence;
- a read-only payment collection preflight;
- a production charging gate that must already be green.

CSS intentionally contains no live collection endpoint/provider adapter yet.

## Requirements for any live provider adapter

A future provider implementation must support:

- idempotency keys;
- exact amount/currency preservation;
- customer/account and invoice reference;
- external transaction identifier;
- deterministic success/failure/pending result;
- webhook/event verification;
- refunds/chargebacks where applicable;
- settlement/reconciliation evidence;
- safe retries without duplicate collection;
- provider sandbox/prod environment separation;
- credential isolation and rotation;
- audit trail.

## Required activation evidence

Before an adapter can be enabled:

1. provider/commercial contract approved;
2. merchant/account configuration approved;
3. jurisdiction/customer payment authorization approved;
4. provider configuration persisted as APPROVED;
5. production charging gate green;
6. structured security certification green;
7. payment integration UAT passed;
8. reconciliation and rollback tested.

## Prohibited coupling

Payment readiness, trial conversion, invoice status, or a positive customer
balance must never by themselves initiate collection.

Trading and broker execution remain separate from payment collection.
