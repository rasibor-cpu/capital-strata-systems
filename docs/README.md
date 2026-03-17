# CSS Architecture Documents

This folder contains the core architecture and integration documents for
Capital Strata Systems (CSS).

These documents serve as the reference layer for current development,
future refactoring, and system hardening.

---

## Documents

### 1. Trade Decision Orchestrator Integration Plan
**File:** `trade_decision_orchestrator_integration_plan.md`

Defines how the TradeDecisionOrchestrator integrates with the existing
CSS signal classification layer without duplicating classification logic.

---

### 2. CSS System Flow
**File:** `css_system_flow.md`

Defines the official high-level system pipeline from market data intake
through intelligence analysis, orchestration, classification, risk
gating, position management, execution, and audit logging.

---

### 3. CSS Signal Quality Model
**File:** `css_signal_quality_model.md`

Defines the signal-quality philosophy of CSS, including confidence
scoring, classification thresholds, and execution policy for ELITE,
STRONG, WEAK, and NOISE signals.

---

## Architectural Intent

CSS is being developed as a governance-first, modular, institutional-grade
capital system.

The architecture is designed around:

- Clear separation of responsibilities
- Strong risk governance
- Modular signal intelligence
- Explicit classification logic
- Controlled execution flow
- Auditable system behavior

---

## Usage Rule

Future coding and refactoring work should remain aligned with these
documents unless a deliberate architecture change is approved and
documented.

---

## Current Focus

Current development is focused on improving:

- Trade decision orchestration
- Signal quality clarity
- Risk-controlled actionability
- Clean modular system flow
