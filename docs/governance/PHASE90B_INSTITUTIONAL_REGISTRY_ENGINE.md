PHASE 90B — INSTITUTIONAL REGISTRY ENGINE

Status: DRAFT

Objective

Convert the Phase 90A institutional governance framework into a reusable CSS registry architecture.

This phase establishes a canonical institutional instrument registry capable of identifying and classifying supported institutional instruments.

No execution functionality is introduced.

Scope

This phase includes:

- Institutional registry architecture
- Canonical symbol mapping
- Asset classification mapping
- Dashboard classification support
- Registry governance standards

This phase excludes:

- Broker execution
- Futures execution
- FX execution
- ETF execution
- Order routing
- Margin engines
- Swap engines
- Position management changes

Registry Requirements

The institutional registry shall support classification of:

FX Futures

- 6E
- 6B
- 6J
- 6C
- 6A

Classification:

FX_FUTURE

Rates Futures

- ZN
- ZF
- ZT
- ZB

Classification:

RATES_FUTURE

Macro ETFs

- UUP
- FXE
- FXY

Classification:

MACRO_ETF

Bond ETFs

- TLT

Classification:

BOND_ETF

Credit ETFs

- HYG
- LQD
- EMB

Classification:

CREDIT_ETF

Registry API Objectives

Future CSS registry interfaces should support:

get_instrument(symbol)

get_asset_class(symbol)

is_fx_future(symbol)

is_rates_future(symbol)

is_macro_etf(symbol)

is_bond_etf(symbol)

is_credit_etf(symbol)

No implementation is required during this phase.

Dashboard Objectives

Future dashboard implementations should be capable of rendering:

- FX Futures
- Rates Futures
- Macro ETFs
- Bond ETFs
- Credit ETFs

without requiring broker connectivity.

Success Criteria

After completion of Phase 90B, CSS governance shall define:

- Canonical institutional registry structure
- Canonical symbol ownership
- Canonical asset classification mapping
- Dashboard readiness requirements

without modifying execution behavior.
