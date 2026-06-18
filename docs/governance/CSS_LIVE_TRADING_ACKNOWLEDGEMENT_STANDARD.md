# CSS Live Trading Acknowledgement Standard

## 1. Live Trading Acknowledgement Workflow
The system operates under a fail-closed principle for live deployment. Live Mode activation is blocked unconditionally unless a valid, unexpired legal acknowledgement is present in the runtime state.

## 2. Required User Acceptance Events
Before Live Mode activation, the user must explicitly and affirmatively acknowledge the following truths:
- I understand that trading and investing involve substantial risk.
- I understand I may lose some or all invested capital.
- I understand CSS does not guarantee profits, returns, or successful outcomes.
- I understand all trading decisions remain my responsibility.
- I understand market, software, broker, exchange, API, data feed, and network failures may occur.
- I voluntarily assume all risks associated with using CSS.

## 3. Acceptance Logging Requirements
Each affirmative acceptance must be logged and cryptographically or structurally sealed with the timestamp, user identification, and the specific version of the disclosure accepted.

## 4. Expiration / Re-acceptance Requirements
Acceptances are version-bound. If the Risk Disclosure Policy or Limitation of Liability Policy receives a major version bump, all prior acceptances are invalidated, and the system must revert to a fail-closed blocked state until re-acceptance occurs.

## 5. Audit Trail Requirements
The acknowledgement must trigger an immutable audit event (`LEGAL_ACCEPTANCE`) written to the canonical compliance ledger.
