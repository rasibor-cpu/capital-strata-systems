# Phase 95 — Institutional Margin Governance Framework

## Purpose

Phase 95 defines the governance framework for institutional margin oversight within Capital Strata Systems.

This phase is documentation and governance only.

It does not calculate margin.
It does not call brokers.
It does not approve leverage.
It does not execute trades.

## Margin as a Capital and Risk Layer

Margin is treated as a cross-asset capital and risk-control layer, not as an asset class.

The framework applies across:

- FX
- Futures
- Options
- Crypto
- Equities
- ETFs
- Future onboarded instruments

## Margin Authority

CSS recognizes margin oversight as a controlled institutional authority area.

Margin authority belongs to the capital, risk, execution-governance, and broker-control layers jointly.

No single asset engine may independently approve or override margin usage.

## Margin Classifications

CSS margin states are classified as follows:

| Classification | Meaning |
|---|---|
| NO_MARGIN | Instrument or mode does not use margin |
| INFORMATIONAL_MARGIN | Margin data is displayed but not used for decisions |
| GOVERNED_MARGIN | Margin exposure is monitored by CSS controls |
| RESTRICTED_MARGIN | New exposure is limited by margin governance |
| CRITICAL_MARGIN | Defensive action, escalation, or trade blocking required |

## Margin Governance Principles

CSS margin governance follows these principles:

1. Margin must be visible before it becomes actionable.
2. Broker margin data must never be treated as authoritative unless source and timestamp are known.
3. Margin usage must be assessed across the whole portfolio, not only per position.
4. Margin pressure must influence new-trade gating before forced exits are considered.
5. Margin controls must fail closed if margin state is unknown in live mode.
6. Paper mode may simulate margin, but must label it clearly as simulated.
7. Margin escalation must be auditable.

## Margin Threshold Bands

Initial institutional threshold bands:

| Band | Margin Utilization | CSS State |
|---|---:|---|
| GREEN | 0% to 40% | Normal |
| YELLOW | >40% to 60% | Monitor |
| ORANGE | >60% to 75% | Restrict new risk |
| RED | >75% to 90% | Defensive mode |
| BLACK | >90% | Critical block |

These bands are governance defaults. Broker-specific margin rules may be stricter.

## Margin Escalation States

| State | Action |
|---|---|
| NORMAL | No margin restriction |
| MONITOR | Display and audit margin usage |
| RESTRICT_NEW_RISK | Limit new position opening |
| DEFENSIVE_ONLY | Permit exits and risk reduction only |
| CRITICAL_BLOCK | Block new exposure and escalate |

## Asset-Class Margin Treatment

### FX

FX margin is broker-driven and leverage-sensitive.

CSS must track:

- notional exposure
- required margin
- available margin
- margin utilization
- broker margin mode

### Futures

Futures margin must distinguish:

- initial margin
- maintenance margin
- intraday margin
- overnight margin

CSS must treat futures margin as high-priority because adverse movement may create rapid margin escalation.

### Options

Options margin depends on strategy, direction, and account permissions.

CSS must distinguish:

- long premium-paid options
- short options
- spreads
- covered strategies
- undefined-risk structures

Undefined-risk short-option exposure must default to restricted treatment until explicitly governed.

### Crypto

Crypto margin is not enabled by default.

CSS treats crypto spot as non-margin unless a broker or exchange explicitly reports margin or leverage.

### Equities and ETFs

Equity and ETF margin is reserved for future broker support.

Until implemented, these instruments default to NO_MARGIN or INFORMATIONAL_MARGIN.

## Live Mode Rules

In live mode:

- Unknown margin state must fail closed.
- Missing broker margin data must block new margin-dependent exposure.
- Simulated margin data must not authorize live trades.
- Margin escalation must be recorded in audit logs.
- Defensive exits may remain permitted when new trades are blocked.

## Paper Mode Rules

In paper mode:

- Margin may be simulated.
- All simulated outputs must be labelled SIMULATED.
- Paper margin must not be confused with broker-authoritative values.
- Paper margin is permitted for testing dashboards, gates, and stress logic.

## Audit Requirements

Every margin escalation must record:

- timestamp
- asset class
- symbol if applicable
- selected broker
- broker mode
- margin source
- margin utilization
- escalation state
- decision outcome
- session id
- user id

## Governance Boundaries

Phase 95 does not:

- calculate margin
- fetch broker margin
- enforce margin gates
- liquidate positions
- modify portfolio state
- alter dashboard execution flow

Those functions are reserved for later phases.

## Planned Successor Phases

| Phase | Scope |
|---|---|
| Phase 96 | Margin Engine |
| Phase 97 | Broker Margin Integration |
| Phase 98 | Margin-Aware Trade Gate |
| Phase 99 | Margin Dashboard Console |

## Phase 95 Acceptance Criteria

Phase 95 is complete when:

- Margin is formally defined as a cross-asset risk layer.
- Margin classifications are documented.
- Escalation states are documented.
- Asset-class margin treatment is documented.
- Live and paper mode margin rules are documented.
- Future implementation boundaries are clearly defined.