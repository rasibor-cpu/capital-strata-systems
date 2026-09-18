# CSS Provider Decision Brief — Canada Baseline

Status: TECHNICAL SHORTLIST — CONTRACT / ACCOUNT APPROVAL PENDING
Research date: 2026-09-17

## Payment provider shortlist

### Provisional technical leader: Stripe

Why it is the current integration lead:
- Canada pricing page lists standard online domestic-card pricing of
  2.9% + CA$0.30 per successful transaction;
- Canadian pre-authorized debits are supported;
- Stripe Billing supports recurring/subscription billing and customer portal
  functionality;
- multi-currency and broad payment-method support are available;
- the existing CSS provider abstraction already requires idempotency,
  reconciliation evidence, refunds/chargebacks and production/sandbox
  separation.

Current published pricing also lists Stripe Billing pay-as-you-go at 0.7% of
Billing volume. Pricing and eligibility must be rechecked during onboarding.

Official references:
- https://stripe.com/en-ca/pricing
- https://stripe.com/en-ca/billing/pricing
- https://stripe.com/en-ca/pricing/local-payment-methods

Required before selection becomes APPROVED:
- merchant/entity eligibility;
- underwriting acceptance for CSS business model;
- production account ID;
- permitted charge/fee structure;
- settlement currencies;
- webhook signing;
- dispute/refund flow;
- production credentials/secret-storage plan;
- reconciliation/export capabilities;
- contract/terms review.

### Enterprise alternative: Adyen

Adyen publishes transaction-based pricing with no setup or monthly fee and
lists Canada among supported locations. It remains a useful enterprise
alternative where volume, payment-method breadth or settlement architecture
makes it preferable.

Official reference:
- https://www.adyen.com/pricing

## Notification provider shortlist

### Transactional email lead: Twilio SendGrid

SendGrid's Email API supports transactional email, event webhooks, analytics
and deliverability tooling. Current published plan information provides trial
and paid Email API options.

Official references:
- https://sendgrid.com/solutions/email-api/
- https://sendgrid.com/en-us/marketing/sendgrid-services-cro

### SMS option: Twilio

Twilio publishes Canadian SMS pricing and supports delivery through Canadian
long-code/toll-free/short-code options. Carrier and segment fees may apply.

Official reference:
- https://www.twilio.com/en-us/sms/pricing/ca

## Provisional architecture recommendation

Until account underwriting and counsel approval are complete:

- Payment: keep Stripe as the primary technical onboarding candidate and Adyen
  as the enterprise fallback.
- Notification: keep SendGrid as the primary transactional email candidate and
  Twilio SMS as an optional secondary channel.
- Do not enable any vendor adapter in production until the provider evidence
  package validates and credentials are stored through approved secret
  management.

This brief is a technical shortlist, not authorization to open an account,
accept provider terms, incur material charges or enable live collection.
