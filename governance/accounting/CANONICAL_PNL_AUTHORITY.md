# CSS Canonical PnL Authority

## Purpose
Defines the single institutional source of truth for PnL.

## Rules
1. Realized PnL must come from the canonical accounting authority.
2. Unrealized PnL must come from the canonical accounting authority.
3. Fees, spread, slippage, financing, and overnight costs must be modeled where applicable.
4. Dashboard must consume PnL; it must not independently calculate authoritative PnL.
5. Broker balances, ledger records, and dashboard state must reconcile.
6. Any PnL mismatch must trigger audit visibility and governance review.
