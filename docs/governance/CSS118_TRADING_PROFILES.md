# CSS-118 — Startup modes, copy-trading risk personalities and trader mandates

Status: **review-only implementation (paper/simulation). Not live-trading authorization.**
Integration parent: `24805875821747542b7ffa0007db6bcd583068db` (frozen CSS-065 candidate + #116 repair).
Safety boundary unchanged: `execution_allowed=false`, `live_trading_blocked=true`,
`broker_execution_armed=false`, `advisory_only=true`. PRODUCTION_GO=NO.

## 1. Startup operating modes (exactly three)

| Mode | Signals accepted | Authority needed | Route | Fills |
|---|---|---|---|---|
| Simulated Trading | any | none | canonical gates, then a no-route stub (the validation pipeline is not called) | simulated |
| Copy a CSS Trader | the mandated trader's signals only | risk personality, current disclosure, valid signed mandate | canonical paper chain | simulated |
| CSS Autonomous Trading | `CSS_AUTONOMOUS_ENGINE` signals only | risk personality, current disclosure | canonical paper chain | simulated |

How the selection works:
- It is stored per user (`PreferencesStore`), so users do not pick a strategy at every start.
- `startup_state()` returns the stored choice and anything that still needs selecting or renewing.
- **No mode permits a live or broker order path** (`ModePermissions` invariant, tested).

## 2. Copy-trading risk personalities (exactly five) — proposed defaults for owner review

| | Safe | Conservative | Balanced | Aggressive | Ultra Aggressive |
|---|---|---|---|---|---|
| Asset classes | FX | FX, Crypto | FX, Crypto, Futures | all | all |
| Trade-quality recommendation | EXECUTE | EXECUTE, PREFERRED | EXECUTE, PREFERRED | EXECUTE, PREFERRED | EXECUTE, PREFERRED, WATCH |
| Min trade-quality score | 80 | 72 | 65 | 58 | 50 |
| Min probability | 0.66 | 0.62 | 0.58 | 0.55 | 0.53 |
| Min CAIE score | 130 | 120 | 110 | 100 | 90 |
| Margin state accepted | NORMAL | NORMAL | NORMAL | NORMAL, WARNING | NORMAL, WARNING |
| Risk per trade (% equity at stop) | 0.25 | 0.50 | 1.00 | 1.50 | 2.00 |
| Max stop distance % | 1.0 | 1.5 | 2.0 | 2.5 | 3.0 |
| Max position % equity | 2 | 4 | 6 | 8 | 10 |
| Max symbol exposure % equity | 2 | 4 | 6 | 8 | 10 |
| Max total exposure % equity | 5 | 10 | 20 | 30 | 40 |
| Max open copied positions | 2 | 3 | 5 | 7 | 8 |
| Daily-loss halt % | 1 | 2 | 3 | 4 | 5 |
| Drawdown halt % | 3 | 5 | 8 | 12 | 15 |
| Take profit (R multiple) | 1.5 | 1.75 | 2.0 | 2.5 | 3.0 |
| Trailing activation R / giveback | 1.0 / 30% | 1.0 / 35% | 1.25 / 40% | 1.5 / 45% | 2.0 / 50% |
| Time stop (hours) | 24 | 48 | 72 | 120 | 168 |

**How the table is applied:**
- **Sizing.** Notional = equity × risk / stop. It is then capped by the position, symbol, total-exposure and mandate-allocation limits.
  - Sizing is **never scaled up** to reach a gate minimum. A personality-sized order below AntiBleedGuard's 50 minimum is rejected, not enlarged.
- **Global caps still apply.** The 10-position hard cap and the R7 per-asset caps (crypto 3, FX 3, futures 2, options 2) apply on top of every personality.

**Legacy engine modes are separate.** SAFE / CONSERVATIVE / BALANCED / AGGRESSIVE / EXPANSION are not touched:
- R7 and R14F keep using the engine mode in force, with unchanged thresholds.
- `LEGACY_ENGINE_MODE_MAPPING` is deliberately empty. "Ultra Aggressive" is not EXPANSION. Tests show R7 and R14F follow the engine mode in force, not the personality; a mutation that maps Ultra Aggressive to EXPANSION fails 3 tests.
- Any mapping requires a separate owner decision.

## 3. Gate order for every copied / autonomous / simulated trade

1. **Safety:**
   - the observed safety-flag verdict must be SAFE (not fail-closed, execution not allowed, live blocked);
   - live-order kill switch;
   - global and per-pair kill switch;
   - known legacy engine mode.
   Paper copies now also honour the kill switches.
2. **Profile:** persisted mode, risk personality, current disclosure version.
3. **Authority:**
   - Copy mode needs a mandate that is signed (HMAC-SHA256), unrevoked and unexpired, matches the trader and personality, covers the asset class, and has been reauthorized on time.
   - Autonomous mode accepts CSS engine signals only.
4. **Personality eligibility** and the drawdown and daily-loss halts.
5. **Sizing** and exposure caps; personality open-position limit; global cap of 10.
6. **TradeQualityScoringEngine** and **CAIE** scoring floors. This is these engines' first runtime caller.
7. **R14F** (`backend/governance/r14f_profitability_gate.py`):
   - same thresholds as `scripts/css_live_dashboard.py`;
   - parity is proven by executing the dashboard's own functions in `tests/test_r14f_gate_parity.py`.
8. **`CanonicalExecutionIntegration`** (the documented paper authority):
   - **R7** `CSSUnifiedTradeGate`, with real per-asset counts;
   - **ExecutionGate**: AntiBleedGuard (net edge ≥ 25 bps, minimum size 50, per-follower cooldown), MarginTradeGate, compounding, drawdown scaler, RiskGovernor;
   - `UnifiedExecutionPipeline`: validation only, rejects live, never dispatches to a broker.
9. **Deterministic simulated fill** and a hash-chained attribution record.

## 4. Mandates, reauthorization, attribution, disclosures

**Mandates**
- **Contents:** one active mandate per follower, recording the trader, personality, asset-class scope, allocation ceiling, currency and expiry (≤ 90 days).
- **Reauthorization:** `EACH_SIGN_ON` (bound to a hash of the session) or `INTERVAL` (hours).
- **Changes:** revocation, supersession and reauthorization are written to a hash-chained audit log.
- **Expired, revoked or mismatched mandates** block new copies. Existing positions keep their stop, take-profit, trailing and time-stop protection until they exit.
- **Signing key:** read from `CSS_COPY_MANDATE_SIGNING_KEY` (hex, ≥ 32 bytes). There is **no default key**; without it the API returns 503 and copying is blocked.

**Attribution**
- A `SOURCE_SIGNAL` record holds the trader's signal.
- `FOLLOWER_DECISION` records hold each follower's own decision, size and fill. `FOLLOWER_EXIT` records hold each follower's own exit and PnL.
- `reconcile()` proves:
  - each follower decision maps to exactly one source signal;
  - a fill exists only for copied decisions, which went through the governed pipeline;
  - exits only close the follower's own positions;
  - there are no duplicate exits.
- The follower statement shows the trader's signal next to the user's own fills and PnL.

**Disclosures:** a versioned text is shown before use. It explains:
- paper/simulation only;
- personality-driven differences from the trader;
- the gates;
- no reimbursement of ordinary losses;
- mandate expiry and revocation.

## 5. User-facing API (mounted on the mobile app)

`/api/v1/trading-profiles/`:
- `catalog`
- `me` (startup state)
- `mode`
- `personality`
- `disclosure/acknowledge`
- `mandates`
- `mandates/{id}/reauthorize`
- `mandates/{id}/revoke`
- `statement`

Identity comes only from the server-side mobile session. No endpoint places orders.

## 6. Integration status and open items (not claimed as done)

- **Not wired yet:**
  - No trader-signal feed exists yet. A signal source that publishes `SourceSignal`s from CSS traders is needed before copying produces activity.
  - The legacy dashboard loop (path B) and the mobile ticket path (path A) are unchanged and do not call this engine.
- **Owner decisions:**
  - The parameter values in §2.
  - A trader registry and eligibility (who counts as a "CSS trader"; `trader_id` is free text today).
  - The default reauthorization frequency.
  - Signing-key provisioning and custody.
- **Recommended follow-up:** make the dashboard import `backend/governance/r14f_profitability_gate.py` so that only one copy of the R14F thresholds exists. The parity test protects against drift until then.
- **Ceilings that don't exist in code:** CAD20 exists in code (`order_limit_config.py`, `live_micro_pilot_governor.py`). **CAD40 aggregate and "two concurrent parents" do not**, so they cannot be enforced here. This layer never produces live orders, so the pilot ceilings are not reachable from it.
- **Profitability:** no profitability claim is made. The tests prove behaviour, not edge. Cost-adjusted out-of-sample evidence is still required.

## 7. Rollback

The change is additive:
- the new packages `backend/trading_profiles/` and `backend/governance/r14f_profitability_gate.py`;
- tests;
- this document;
- one router mount (29 lines) in `dashboard/mobile/mobile_app.py`.

To roll back, revert the commit or remove the router mount. Persisted data lives only under `artifacts/trading_profiles/` and can be archived.
