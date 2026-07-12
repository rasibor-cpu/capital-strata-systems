# Supervised Live Micro-Pilot Pre-Flight Certification — Phase 163B.3C

This certification document evaluates the pre-flight readiness and safety controls for initiating the first supervised live micro-pilot trade on the Capital Strata Systems (CSS) platform.

---

## Repository Integrity & Audit Trail

A pre-flight repository audit was performed to confirm code cleanliness, correct commit ordering, and compliance with institutional secret-handling constraints:

1. **Branch & Working Tree Status**:
   - Current active branch: `css-evening-consolidation-2026-06-09`
   - Working tree state: **Clean** (all modified files are committed).
2. **Commit History Sequencing**:
   - **Commit 1 (Phase 163B.3A)**: `ae02ccb5542a5973293e045980934143ce4d7aa9` (Normalized interfaces, credentials correction, TypeError crash hardening).
   - **Commit 2 (Phase 163B.3B)**: `00036c4e356c8bdd323897899a5fb721ca631576` (10 consecutive read-only operational validation cycles successfully executed).
3. **Secret-Handling Verification**:
   - The `.env` file is explicitly ignored in git (`.gitignore` line 18) and is untracked by the repository.
   - Verification confirms that **no API keys, private keys, passwords, or personal credentials** were checked into the repository or exposed in the codebase.
4. **Execution Authority Control**:
   - A codebase-wide scan confirms that all runtime flags permitting live order routing are securely disabled (`execution_allowed` is hardcoded to `False` across the read-only operational validators, readiness modules, and adapter wrappers).

---

## A. Execution Firewall Controls

To maintain the institutional advisory-only state, the runtime engine implements multiple levels of execution blocking:

### 1. Guarded Firewall Status
- **`execution_allowed`**: `False`
- **`live_trading_blocked`**: `True`
- **`broker_execution_armed`**: `False`
- **`advisory_only`**: `True`

### 2. Authorization Mechanism
For a temporary, operator-supervised micro-pilot, the engine must transition from the read-only adapter wrappers to the base execution adapters. The exact mechanism requires:
1. Configuring `OANDA_ENABLE_LIVE_TRADING = "1"` or `COINBASE_ENABLE_LIVE_ORDERS = "1"` in `.env`.
2. Setting `broker_execution_armed = True` via database control or supervisor configurations.
3. Explicit `operator_requested_live = True` boolean assertion inside the active audit user context.
4. Passing the **AntiBleedGuard**, **MarginGate**, and **UnifiedTradeGate** evaluations.

### 3. Fail-Closed Reset
Any authorization is structurally temporary. The firewall automatically returns to a **fail-closed state** under any of the following conditions:
- Operator toggle of the live execution authorization switch to `False`.
- Triggering of the `CSS_LIVE_ORDER_KILL_SWITCH`.
- Connectivity drop or heart-beat timeout (> 10 seconds).
- AntiBleedGuard detecting total capital drawdown exceeding 1%.

---

## B. Pilot Limits

To prevent capital exposure, the micro-pilot is governed by strict boundaries:

- **Maximum Pilot Capital**: CAD 20.00
- **Maximum Order Count**: Exactly 1 order.
- **Maximum Open Position**: Exactly 1 position.
- **Leverage Policy**: 1:1 (No leverage permitted).
- **Margin Policy**: No margin borrowing or collateral dependency.
- **Derivative Restriction**: No futures, options, swaps, or synthetic products.
- **Directional Restrict**: Long only (No short selling allowed).
- **Averaging Policy**: No averaging down or grid trading.
- **Re-entry Restriction**: No automatic re-entry on exit.
- **Operator Requirement**: Strictly attended operation. An operator must remain actively monitoring the terminal throughout the run.

---

## C. Instrument Eligibility

The safest eligible instruments supported by OANDA and Coinbase have been evaluated:

| Broker | Eligible Instrument | Minimum Size | Notional Value (CAD) | Eligibility Verdict |
| :--- | :--- | :--- | :--- | :--- |
| **OANDA** | `EUR_USD` | 1 unit | ~CAD 1.50 | **RECOMMENDED (Lowest Risk)** |
| **Coinbase** | `ETH-USD` | 0.001 ETH | ~CAD 4.10 | Eligible (Low Risk) |
| **Coinbase** | `BTC-USD` | 0.0001 BTC | ~CAD 8.20 | Eligible (Medium Risk) |

**OANDA EUR_USD** is selected as the optimal instrument for the pre-flight pilot because its minimum unit size allows a position notional of ~CAD 1.50, keeping the risk exposure minimal and comfortably within the CAD 20.00 budget.

---

## D. Order Controls

Supervised execution enforces standard transaction controls:

1. **Manual Confirmation**: The operator must review and confirm the order details (symbol, size, side, price) in a pre-execution pop-up/prompt immediately before dispatch.
2. **Market-Data Freshness**: Pricing data must be updated within the last **3.0 seconds**.
3. **Maximum Spread Threshold**: Spread must not exceed **2.0 pips** for EUR_USD.
4. **Slippage Tolerance**: A maximum slippage threshold of **0.05%** from the mid-market price is enforced.
5. **Idempotency Protection**: Every order request includes a unique, client-side transaction identifier (`client_order_id`) to prevent duplicate submissions on networking retries.
6. **Order Timeout**: If the broker does not return a execution receipt within **10.0 seconds**, the order status is queried, and a cancellation request is issued.
7. **Post-Trade Reconciliation**: Immediate database audit check comparing the filled volume/value returned by the broker with the expected order request to ensure 100% parity.

---

## E. Emergency Controls & Rollback

Under any abnormal condition, the system executes fail-closed actions:

1. **Kill-Switch Engaged**: An operator can press the global Kill Switch to immediately cancel any pending order and close the active position using market orders.
2. **Broker Disconnect**: If a heartbeat is missed, the system blocks all execution pipelines and transitions to alert state.
3. **Unexpected Position**: If an un-audited or duplicate position is discovered during reconciliation, an emergency close order is automatically routed, and the operator is alerted.
4. **Immediate Halt**: Immediate pause of all automated trading systems and escalation to core developers.

---

## F. Pre-Flight Report & Checklist

### Pilot Parameters (OANDA EUR_USD Run)
- **Broker**: OANDA (Live Mode)
- **Instrument**: `EUR_USD`
- **Quantity**: 10 units (~CAD 15.00 notional)
- **Expected Commissions/Fees**: None (Spread-based, expected transaction cost < CAD 0.01)
- **Maximum Loss Exposure**: ~CAD 0.15 (under a highly conservative 1% market move)
- **Rollback Procedure**: Route a manual close order for 10 units of EUR_USD, toggle `OANDA_ENABLE_LIVE_TRADING = "0"`, and restart supervisor.

### Operator Pre-Flight Checklist
- [ ] Verify database connectivity and clean working tree.
- [ ] Confirm no error warnings on the operational dashboards.
- [ ] Verify that `OANDA_ENABLE_LIVE_TRADING` is set to `"0"` (confirming advisory mode default).
- [ ] Review current live spread on EUR_USD is under 1.5 pips.
- [ ] Perform a pre-flight test call to verify latency is under 4 seconds.

---

## GO / NO-GO Recommendation

**GO** (Controlled/Supervised Live Micro-Pilot). 

All technical safeguards are implemented, verified, and hardened. The code resides in a clean, versioned repository with no credentials leaks. Once the operator is ready, they may proceed to perform a supervised execution of a single 10-unit EUR_USD order within the CAD 20.00 budget.
