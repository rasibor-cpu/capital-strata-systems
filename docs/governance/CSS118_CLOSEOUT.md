# CSS-118 — Final integration and governed closeout (branch `claude/css118-closeout`)

**Paper only. PRODUCTION_GO=NO.** Nothing here deploys, enables live trading, arms broker
execution, changes production limits or submits orders. This builds on PR #119 (trading
profiles), and integrates PR #120 (ExecutionGate volatility sizing) and PR #121 (mobile audit
replay) by merge.

## 1. What the closeout adds
| Item | Owner direction | Change |
|---|---|---|
| C1 Gate sizing reaches fills | 4, 5 | `CanonicalExecutionResult.execution_gate_sizing`; the engine applies `min(notional, gate_scaled)`. It never upsizes; a reduction below AntiBleed's 50 is rejected; invalid scaling fails closed. One volatility stream per instrument. |
| C2 Engine signal bridge | 2 | `engine_bridge.py` is the only entry for engine signals. Only `ENGINE_LOOP_CALIBRATED` provenance is routable; legacy random candidates and uncalibrated signals are refused and recorded. `EngineLoop.css_signal_sink` is optional (default off). |
| C3 Market assessment | 3 | `market_assessment.py`: CSS's own view, recorded from engine signals per (symbol, side), fresh for 5 minutes. **The user decides** symbol, side, size and stop; the size is a cap and is never enlarged. **The price comes from CSS**, not the user. CSS-Assisted orders need approval per order. |
| C4 Bypasses closed | 2 | Mobile `/trade` routes through the router as a governed manual paper order; broker tickets are refused (`LIVE_TICKET_DISABLED_CSS118`); the legacy executor is not routed. The legacy loop's broker branch is closed by a code constant. `oanda_trade_smoketest.py` refuses to run; `run_live_manual.py` was already retired. |
| C5 AntiBleed vs CAD 20 | 6 | Evidence and a design for a paper-only exception (see `CSS118_ANTIBLEED_PAPER_EXCEPTION_DESIGN.md`). **Not enabled**; conflicting orders are rejected. |
| C6 Ledger anchoring | 9 | `ledger_anchor.py` plus `tools/verify_css_ledger_anchors.py`: signed, chained prefix checkpoints, external statements, an independent verifier. **No production key is enrolled.** |
| #120 / #121 | 4 | Merged unchanged: volatility sizing is reduce-only; `_safe_int` is defined. |

Unchanged and still binding (direction 1):
- the four modes and five personalities;
- the capital governors (5% per trade, 2% futures/options, 25% portfolio);
- AntiBleed (25 bps net edge, minimum 50, cooldown);
- R7 and R14F;
- the exposure limits and kill switches;
- the CAD pilot envelope (20 per parent, 40 aggregate, 2 parents);
- the canonical live caps;
- the empty trader registry with dual control (direction 7);
- the manual and consent flow (direction 8).

## 2. Feature → test matrix
| Requirement | Tests |
|---|---|
| Four modes and five personalities | `test_css118_trading_profiles.py`, `test_css118_router.py::test_css_engine_signal_routes_by_mode` |
| Most restrictive limit wins; capital governors binding | `test_css118_trading_profiles.py::test_same_signal_produces_personality_specific_outcomes`, `test_css118_closeout_governance.py::test_capital_governor_ceilings_unchanged`, `test_css118_router.py::test_capital_governor_gate_rejection_is_enforced` |
| Engine signals → governed router | `test_css118_engine_bridge.py` (19) |
| Manual orders keep user authority under CSS limits | `test_css118_manual_orders.py` (20) |
| CSS-Assisted per-order approval | `test_css118_manual_orders.py::test_assisted_manual_order_needs_per_order_approval_at_the_users_size`, `test_css118_router.py::test_assisted_*` |
| Copy trading (approved trader, signed feed) | `test_css118_trader_registry_feed.py`, `test_css118_router.py` |
| Bypasses closed (mobile ticket, legacy loop, direct scripts) | `test_css118_bypass_closure.py` (12), `test_css118_signin_enforcement.py` |
| Volatility sizing reduce-only (#120 + C1) | `tests/engine/test_execution_gate_volatility_sizing.py` (5), `test_css118_gate_sizing.py` (9) |
| Audit replay (#121) | `tests/test_mobile_audit_replay_limit.py` (14) |
| AntiBleed 50 kept; no automatic CAD 20 exception | `test_css118_closeout_governance.py`, `test_css118_pilot_envelope.py` |
| Registry empty, dual control, suspension, replay | `test_css118_trader_registry_feed.py`, `test_css118_closeout_governance.py` |
| Manual, scroll-gated acceptance, receipts, renewal, emergency actions | `test_css118_consent.py`, `test_css118_onboarding_ux.py` (Playwright), `test_css118_signin_enforcement.py`, `test_css118_bypass_closure.py::test_emergency_risk_reduction_still_works_without_acceptance` |
| Ledger tamper evidence and anchoring | `test_css118_ledger_anchor.py` (11), `test_css118_trader_registry_feed.py` |

Mutation checks on the closeout controls: 16 of 16 caught.

## 3. Remaining blockers
| # | Blocker | Type | Needed |
|---|---|---|---|
| B1 | **No calibrated real-data CSS signal producer.** The legacy loop's candidates are random. `EngineLoop` has real direction and edge but no probability or R14F-scale score, and runs only in replay. Until a calibration is approved, Autonomous and Assisted users get no engine signals, and manual orders have no fresh assessment (rejected). | engineering + owner | Approve a calibration and a live data source (e.g. scanner candles → `IntelligenceOrchestrator`), then wire `EngineLoop.css_signal_sink` in a governed runner. |
| B2 | AntiBleed minimum 50 vs CAD 20 pilot envelope: every pilot order is rejected. | owner | Choose option A, B or C in the exception design. |
| B3 | Anchor key custody: no production anchor key enrolled; ledgers report `UNANCHORED`. | owner | Choose the key holder and storage (HSM or offline signer), the publication channel for statements, and the checkpoint cadence. |
| B4 | Real traders: the registry is empty. | owner | Independent vetting, approval of signing-key custody, two SUPER_USER approvers. |
| B5 | Legacy dashboard loop still opens **operator paper simulations** from random candidates. These are not user accounts and have no broker path. | owner | Retire the loop, or replace its candidate source with the bridge (B1). |
| B6 | The launcher's `POST /mobile/trade/paper` and `/operator-trade/request` append to a request file that nothing consumes (no execution). | engineering, low | Remove the routes, or route them through the router. |
| B7 | Personality values above the capital governors (6/8/10%, 30/40%) are capped at 5% / 25%. | owner | Keep the governors binding (current state), or lower the personality values. |
| B8 | Live trading, the CAD 20 pilot and the 72-hour endurance run. | owner | Not authorized; PRODUCTION_GO=NO. |

## 4. Rollback
Every change is additive or fail-closed, so rollback is safe at any point. From least to most:
1. **Revert closeout commits individually.** They are independent (C1–C6, plus two merge commits for #120 and #121).
2. **Reopen paths only by source change.** The legacy-loop broker branch and the direct-broker scripts are closed by code constants. Reopening them is a reviewed source change, which is not recommended.
3. **Restore the old mobile ticket behaviour.** Revert C4. Note this reopens the ungoverned paper ticket path.
4. **Remove the closeout branch entirely.** Delete `claude/css118-closeout`. PR #119, #120 and #121 are untouched by it.
5. **Data.** New artifacts live only under `artifacts/trading_profiles/`:
   - `css_market_assessments.json`;
   - `ledger_anchor_checkpoints.jsonl`.

   Archive them rather than deleting them.
