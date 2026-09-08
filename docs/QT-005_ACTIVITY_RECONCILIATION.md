# QT-005: Questrade activity reconciliation

The launcher reads the existing TradeOutcomeRepository and projects Questrade
ACCOUNT_HISTORY into broker_activity_reconciliation. The reconciliation module
is a pure comparison under backend/reconciliation; it does not call the broker
or persist outcomes, positions, or P&L.

## Matching contract

Symbol, trade/transaction calendar date, absolute nonzero quantity and positive
finite exit price identify candidates. Settlement dates alone cannot establish
trade dates. Known currency and closing-action conflicts exclude candidates;
opening-only actions are excluded. Missing currency or closing-action evidence
makes an economic/date candidate AMBIGUOUS. The present canonical repository
schema does not persist currency or closing action, so its economic/date matches
remain AMBIGUOUS with explicit limitations. No schema changes or inferred values
were introduced. CORROBORATED requires complete evidence and a unique candidate
that is not shared with another activity row. It never means authoritative fill
confirmation. No stable broker activity ID exists or is fabricated.

Non-trades are NOT_APPLICABLE. Signed cash amounts remain separated by currency
and classification, including an UNSPECIFIED currency bucket. Trade consideration
is not realized P&L; dividends are investment income, interest is financing or
investment cash flow, fees are costs, taxes are tax cash flows/costs, and transfers
are capital movements. Candidate payloads deliberately omit realized P&L.

Unreadable/missing outcome storage is explicitly UNAVAILABLE. Unavailable
activity history cannot corroborate retained rows. All nine safety invariants
remain closed. The existing position reconciliation and canonical lifecycle are
unchanged.

## Validation (2026-09-08)

- QT-005: 15 passed, including repository read-only integration and malformed evidence.
- Required QT-002/003/004, R8.11, QT-005 and security set: 69 passed.
- Broader Questrade/reconciliation/canonical lifecycle/outcome regression: 230 passed.
- Standalone secure read-only suite: 22 passed.
- Existing Starlette/httpx deprecation warning only; successful runs exited 0.
- Python compilation and git diff --check passed.

The original Windows pytest-current cleanup problem is avoided with an explicit
unique --basetemp and -p no:cacheprovider. For the broad suite use a dedicated
external temporary directory: DPAPI tests correctly reject secret storage inside
the repository (20 failures in the initial repo-local broad run, all resolved by
changing only the test temp location). No production security rule was weakened
and no pre-existing temp directory was deleted.

Live broker acceptance was not performed. The configured DPAPI store exists,
but activating a new OAuth session rotates/persists credentials outside this
workspace. Automated acceptance uses injected read-only broker data; it does not
establish current live account connectivity.

Final production review: no broker write methods/endpoints, order/execution
capability, or authority grants added. Execution capability diff count: 0.
TradeOutcomeRepository and canonical realized/session P&L remain unchanged.

Proposed commit: QT-005 add read-only Questrade activity reconciliation
No commit or push performed.
