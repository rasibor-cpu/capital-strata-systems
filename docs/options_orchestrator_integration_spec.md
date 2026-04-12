# CSS Options Orchestrator Integration – Master Specification
## Phase 1 Sandbox Orchestrator Governance Lock

### Purpose
Defines how the CSS options module integrates into the TradeDecisionOrchestrator during Phase 1 sandbox deployment.

This governs orchestration flow between:

- options_pricing_engine.py
- options_greeks_engine.py
- options_contract_selector.py
- options_execution_adapter.py
- options_position_manager.py
- options_expiry_lifecycle_spec.md rules

---

## Phase 1 Scope

Supported strategies:
- Long CALL only
- Long PUT only

Supported underlyings:
- SPY
- QQQ
- AAPL

Sandbox only.

No live broker routing.

---

## Orchestrator Integration Trigger

Options path activates only when:

1. asset_class == OPTIONS
2. symbol in approved options universe
3. signal_decision == TRADE
4. AI score >= options threshold
5. risk governor approves allocation

Otherwise:
- route remains standard spot/futures path

---

## Integration Sequence

### Step 1: Receive Approved Signal

TradeDecisionOrchestrator passes:

- symbol
- direction
- confidence score
- capital allocation

Example:
symbol = SPY
direction = CALL
allocation = 500

---

### Step 2: Price Snapshot

Call:

options_pricing_engine.price_option()

Inputs:
- symbol
- spot price
- strike candidate
- expiry days
- option type

Output:
- premium estimate

---

### Step 3: Greeks Evaluation

Call:

options_greeks_engine.compute_greeks()

Output:
- delta
- gamma
- theta
- vega

Reject if:
- theta too high
- delta too weak

---

### Step 4: Contract Selection

Call:

options_contract_selector.generate_candidate_contracts()

Select best candidate by:
1. liquidity preference
2. acceptable premium
3. target delta band

---

### Step 5: Risk Validation

Before execution:
PortfolioRiskGovernor validates:
- max premium risk
- position concentration
- symbol exposure cap

---

### Step 6: Execution Adapter Entry

Pass selected contract into:

options_execution_adapter.open_position()

Creates:
- sandbox fill simulation
- premium debit booking

---

### Step 7: Position Registry

Immediately register into:

options_position_manager.register_position()

Track:
- contract metadata
- premium paid
- Greeks snapshot
- expiry date

---

## Live Monitoring Loop

Each cycle:

1. mark-to-market repricing
2. Greeks refresh
3. unrealized PnL update
4. expiry state check

---

## Exit Triggers

Position exits when any occurs:

### A. Profit Target Hit
Example:
+25%

### B. Stop Loss Hit
Example:
-20%

### C. Expiry Rule Triggered
Handled by expiry lifecycle engine

### D. Manual Strategy Override

---

## Expiry Engine Hook

Every cycle call:

check_expiry_status(position)

If expiry reached:
- execute expiry handling path
- close/archive position

---

## Error Handling Rules

If pricing fails:
→ abort trade

If Greeks fail:
→ abort trade

If selector returns none:
→ no trade placed

If execution adapter rejects:
→ log failure + cancel signal

---

## Logging Requirements

Must log:

- signal received
- contract selected
- premium paid
- Greeks values
- open timestamp
- close timestamp
- realized PnL

---

## Non-Regression Rule

This integration must NOT alter:
- crypto execution path
- futures execution path
- spot execution path

Options orchestration must remain isolated.

---

## Laptop 1 Next Coding Target

Implementation file target:

backend/intelligence/trade_decision_orchestrator.py

Add:
integrate_options_trade_path()

after sandbox validation review.
