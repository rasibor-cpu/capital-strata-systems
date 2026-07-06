# Phase 154A - Canonical Multi-Broker Live Readiness Framework

Status: Implemented for review.

## Objective

Phase 154A generalizes the Phase 152-153 live readiness architecture so Coinbase and OANDA publish the same canonical broker readiness payload.

## Canonical Broker Readiness

`backend/runtime/broker_readiness_framework.py` defines the broker-neutral readiness interface:

- broker name
- broker type
- mode
- credentials present
- authenticated
- connected
- account loaded
- market data ready
- products loaded
- broker health
- infrastructure health
- credentials health
- authentication health
- connection health
- market data health
- account data health
- execution supported
- execution enabled
- last successful sync
- account balance
- equity
- buying power
- authority block reason
- readiness score

Both Coinbase and OANDA feed this same framework. Dashboard, startup summary, readiness state, and execution authority consume the framework instead of broker-specific readiness logic.

Health dimensions are reported independently. Infrastructure, credentials, authentication, connection, market data, and account data are separate readiness values; one dimension must not imply another.

## OANDA Read-Only Adapter

`backend/runtime/oanda_live_read_only_adapter.py` supports read-only OANDA validation only:

- authentication status
- account summary
- NAV
- balance
- margin
- positions
- open trades
- pricing
- instrument list
- server status
- heartbeat
- account metadata

The adapter exposes no order submission, order modification, trade close, cancel, market order, limit order, stop order, or other write-operation methods.

## Execution Authority

Execution authority remains broker-independent. `LiveExecutionAuthority` consumes the canonical broker readiness contract and common gate evidence only. It must not branch on Coinbase, OANDA, or any other broker name.

## Safety Boundary

Phase 154A does not enable live trading. Coinbase and OANDA remain fail-closed, broker execution remains disabled unless all canonical authority conditions pass, and Phase 152A CAD 20 Governor, Unified Trade Gate, Margin Gate, AntiBleedGuard, RBAC, Kill Switch, and Live Execution Authority remain authoritative.
