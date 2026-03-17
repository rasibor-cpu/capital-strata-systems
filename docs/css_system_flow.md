# CSS System Flow

## Purpose

This document defines the official high-level processing flow for Capital
Strata Systems (CSS). It serves as the architectural reference point for
future development, refactoring, and integration work.

---

## Core System Flow

Market Data  
→ Asset Loader / Symbol Universe  
→ Candle Builder / Historical Context  
→ Feature Builder  
→ Intelligence Engines  
→ Trade Decision Orchestrator  
→ Signal Classification Layer  
→ Risk Gating Layer  
→ Position Manager  
→ Execution / Paper Trading Layer  
→ Logging / Audit / Analytics  

---

## Module Descriptions

### 1. Market Data
Responsible for ingesting live and historical market information from
supported providers such as Coinbase, OANDA, Alpaca, and future adapters.

### 2. Asset Loader / Symbol Universe
Determines which instruments are eligible for scanning and analysis during
a given runtime session.

### 3. Candle Builder / Historical Context
Builds the time-series context required for signal analysis, including
recent candles, rolling windows, and derived historical structures.

### 4. Feature Builder
Transforms raw market data into structured features usable by intelligence
modules.

### 5. Intelligence Engines
Includes specialized analytical engines such as:
- Market regime analysis
- Liquidity sweep detection
- Opportunity pressure analysis
- Pressure acceleration analysis
- Signal confluence analysis
- AI opportunity scoring
- Quant optimization support

### 6. Trade Decision Orchestrator
Aggregates intelligence-engine outputs into a normalized decision object
containing confidence, direction, regime context, and rationale.

### 7. Signal Classification Layer
Converts the orchestrator output into official CSS signal classes such as:
- ELITE
- STRONG
- WEAK
- NOISE

### 8. Risk Gating Layer
Applies portfolio, policy, session, and instrument-level constraints before
a signal can become actionable.

### 9. Position Manager
Controls position lifecycle management, including entry, monitoring,
holding-period logic, exits, and portfolio tracking.

### 10. Execution / Paper Trading Layer
Handles execution routing for paper testing today and broker execution in
future production-safe environments.

### 11. Logging / Audit / Analytics
Captures decision logs, trade logs, runtime diagnostics, audit trails, and
performance metrics for review and refinement.

---

## Architectural Rules

- Each layer should have a clear responsibility.
- Classification logic should not be duplicated inside the orchestrator.
- Risk controls must remain independent from signal creation.
- Execution must remain downstream of all governance checks.
- Logging should capture both decisions and outcomes.

---

## Current Development Direction

CSS is currently evolving toward a cleaner modular pipeline in which
decision logic is centralized, classification remains explicit, and risk
governance continues to operate independently from signal generation.

---

## Next Refactor Objective

Align current dashboard and live-scanning components with this official
system flow so that each runtime stage maps cleanly to a distinct layer.
