# QT-005: Questrade activity reconciliation (clean-main engine)

This clean-main change provides the **architecture-independent reconciliation
engine only**. It is a pure comparison under `backend/reconciliation`. It does
not call a broker, persist outcomes, mutate positions, or promote P&L.

## Current-main scope

- Current `origin/main` has **no Questrade live activity provider** and **no**
  Questrade activity presentation source.
- This commit therefore **does not** wire QT-005 into `/api/v1/frontend-state`.
- Live Questrade integration remains **outside** this clean-main change.
- Feature-branch `launcher/` / always-on runtime files are **not** restored.
- R8.12 (canonical owner / LAN hosting) is **not** included.

Callers that exist only on other branches (Mission Control cache, TradeOutcome
repository, launcher frontend assembly) are not part of this port.

## Matching contract

Symbol, trade/transaction calendar date, absolute nonzero quantity and positive
finite exit price identify candidates. Settlement dates alone cannot establish
trade dates. Known currency and closing-action conflicts exclude candidates;
opening-only actions are excluded. Missing currency or closing-action evidence
makes an economic/date candidate AMBIGUOUS. CORROBORATED requires complete
evidence and a unique candidate that is not shared with another activity row.
It never means authoritative fill confirmation. No stable broker activity ID
exists or is fabricated (`stable_broker_activity_id_available=False`).

Questrade ACTIVITIES are **ACCOUNT_HISTORY / corroboration-only** evidence.
They must not be treated as an authoritative real-time fill feed
(`real_time_fill_feed=False`).

Non-trades are NOT_APPLICABLE. Signed cash amounts remain separated by currency
and classification, including an UNSPECIFIED currency bucket. There is no silent
cross-currency aggregation. Trade consideration is not realized P&L; dividends
are investment income, interest is financing or investment cash flow, fees are
costs, taxes are tax cash flows/costs, and transfers are capital movements.
Candidate payloads deliberately omit realized P&L. The engine does not write
outcomes, mutate portfolios, or promote canonical realized/session P&L.

Unavailable activity history or an unavailable outcome source is explicitly
UNAVAILABLE. Execution and write authorities remain closed:
`execution_authority=False`, `execution_allowed=False`,
`live_trading_blocked=True`, `broker_execution_armed=False`,
`advisory_only=True`.
