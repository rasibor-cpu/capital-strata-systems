# CSS Trade Warehouse

## Purpose

The Trade Warehouse stores clear, auditable records of every trade taken by CSS, separated by asset class.

## Asset Categories

- `crypto/`
- `fx/`
- `futures/`
- `options/`
- `reports/`

## Core Rule

The warehouse must be append-only.

Historical trade records must not be silently overwritten or deleted. Corrections should be recorded as adjustment events.

## Standard Trade Record Fields

Each trade record should eventually include:

- timestamp
- trade_id
- asset_class
- symbol
- side
- entry_price
- exit_price
- quantity
- fees
- slippage
- broker
- broker_mode
- engine_mode
- strategy_source
- signal_score
- probability
- expected_value
- realized_pnl
- unrealized_pnl
- holding_time
- exit_reason
- market_regime
- governance_decision
- audit_reference

## Long-Term Flow

execution engines  
→ position managers  
→ trade warehouse  
→ summaries/reports  
→ dashboard rendering

## Governance Principle

The dashboard must render warehouse outputs. It must not become the trade-record authority.