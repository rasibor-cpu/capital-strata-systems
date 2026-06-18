PHASE 90A — INSTITUTIONAL INSTRUMENT FRAMEWORK

Status: DRAFT

This phase establishes the governance, taxonomy, registry, and risk classification framework for institutional multi-asset support within Capital Strata Systems (CSS).

Scope is limited to:

- Instrument taxonomy
- Instrument registry
- Risk classification
- Dashboard readiness

This phase explicitly excludes:

- Broker execution
- Futures execution
- FX execution
- ETF execution
- Margin engines
- Swap engines
- Order routing

Implementation shall be framework-only and non-executing.

Institutional Asset Taxonomy

Approved CSS institutional asset classifications:

- EQUITY

- ETF

- OPTION

- FUTURE

- FX_SPOT

- FX_FUTURE

- FX_OPTION

- CRYPTO

- MACRO_ETF

- RATES_FUTURE

- BOND_ETF

- CREDIT_ETF

These classifications are governance-level canonical definitions and do not imply execution capability.

Institutional Instrument Registry

FX Futures

- 6E Euro FX
- 6B British Pound
- 6J Japanese Yen
- 6C Canadian Dollar
- 6A Australian Dollar

Rates Futures

- ZN 10-Year Treasury Note
- ZF 5-Year Treasury Note
- ZT 2-Year Treasury Note
- ZB 30-Year Treasury Bond

Macro ETFs

- UUP
- FXE
- FXY
- TLT
- HYG
- LQD
- EMB

Registry entries represent approved CSS-recognized institutional instruments and do not imply live broker support or execution capability.

Risk Classification Framework

FX Futures

- LEVERAGE_RISK
- MARGIN_RISK
- ROLL_RISK
- LIQUIDITY_RISK

FX Options

- DELTA_RISK
- GAMMA_RISK
- THETA_RISK
- VEGA_RISK
- EXPIRY_RISK

Macro ETFs

- MARKET_RISK
- MACRO_RISK
- LIQUIDITY_RISK

Rates Futures

- DURATION_RISK
- INTEREST_RATE_RISK
- ROLL_RISK

These classifications establish the future CSS institutional risk framework and do not represent implemented risk calculations.

Dashboard Readiness

The CSS dashboard shall recognize and render the following institutional classifications:

- FX_FUTURE
- FX_OPTION
- MACRO_ETF
- RATES_FUTURE

Dashboard recognition does not imply execution capability.

No broker integration is required for this phase.

Future Expansion Path

Potential future institutional expansion phases include:

- Futures Risk Engine
- Macro ETF Intelligence Engine
- Multi-Asset PnL Attribution
- Cross-Asset Opportunity Scoring
- FX Futures Execution Framework
- Institutional Risk Aggregation

These future phases are outside the scope of Phase 90A.

Success Criteria

After completion of Phase 90A, CSS shall be capable of identifying:

- Institutional asset classifications
- Institutional instrument registry members
- Institutional risk classifications
- Dashboard-recognized institutional categories

without enabling execution, order routing, broker connectivity, or live trading functionality.
