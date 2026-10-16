# CSS RC1 — integrated release candidate (branch `claude/css-rc1-signal-pipeline`)

**Paper only. PRODUCTION_GO=NO.** Nothing here deploys, enables live trading, arms a broker,
enrols keys, changes capital-governor ceilings or AntiBleed thresholds, or submits orders.
Stacked on `claude/css118-closeout` (PR #122, `09b2cbd1`), which itself carries #119, #120 and #121.

## 1. What RC1 adds
| Item | Closes | Change |
|---|---|---|
| R1 Real-data signal pipeline | B1 (engineering only) | `backend/signals/`: candle providers, calibration, approvals and the producer (detail in §1.1). |
| R2 Paper OMS | mandate 12 (in-repo part) | `backend/oms/paper_oms.py`: one immediate-or-cancel order per governed decision (detail in §1.2). |
| R3 Legacy retirement | B5, B6 | `select_cycle_candidates()` returns `[]`; launcher request-log records are labelled as non-orders (detail in §1.3). |

### 1.1 R1 — real-data signal pipeline

**Market data**
- Coinbase public candles.
- OANDA candles, **practice host only**.
- Strict validation (OHLC consistency, alignment, gaps) and freshness checks.
- A CSV cache with SHA-256 digests.

**Labelling and calibration**
- Leakage-free features.
- Two approved strategies: `TREND_BREAKOUT` and `MEAN_REVERSION`.
- Triple-barrier labels: entry at the next bar's open, a same-bar tie counts as a LOSS, explicit round-trip costs.
- Anchored walk-forward that trains only on trades closed before each fold.

**Release gates:**
- at least 100 OOS trades;
- one-sided 95% lower bound on net bps > 0;
- Brier score below the base rate;
- positive folds ≥ 60%. Folds with no trades count as not positive; this was fixed in RC1;
- maximum drawdown ≤ 2000 bps.

**Artifacts and approval**
- Artifacts are sealed with a digest.
- Approval needs **two distinct SUPER_USERs**; any revocation blocks the artifact.
- Approvals are recorded in a hash-chained ledger.

**Producer and routing**
- The producer emits a signal only for an approved artifact with positive calibrated expectancy, computed on fresh, complete bars.
- Provenance `REAL_DATA_CALIBRATED` is routable **only** through `CssEngineSignalBridge.publish_real_data`. That call re-verifies the approval at route time.

**Tools:** `tools/css_fetch_candles.py`, `tools/css_calibrate.py`, `tools/css_signal_shadow.py`.

### 1.2 R2 — paper OMS

**Orders**
- Each order is keyed by a deterministic `client_order_id`.
  - Resubmitting the same id is idempotent.
  - Reusing an id with different parameters is refused.
- The states are NEW, ACK, PARTIALLY_FILLED, FILLED, REJECTED, CANCELLED and UNKNOWN.
- Overfills are refused, and so are reported decreases in filled quantity.

**Reconciliation** resolves UNKNOWN orders and reports quantity mismatches and orphan venue orders.

**Emergency halt**
- The halt persists, cancels open orders and blocks new ones.
- Resuming needs a SUPER_USER and a clean reconciliation.

**Journal:** every transition is recorded in a hash-chained journal.

**Venue:** `SimulatedVenue` is deterministic and used for verification only.

**Router integration**
- `TradingRouter(oms=...)` is opt-in. With it, the router books only what the venue actually filled.
- The default behaviour is unchanged.

### 1.3 R3 — legacy retirement

- **Legacy loop:** `select_cycle_candidates()` returns `[]`. The legacy loop no longer opens random positions, and its exits for existing positions are unchanged.
- **Launcher request log:** records written by `/mobile/trade/paper` and `/operator-trade/request` now carry `record_kind=REQUEST_LOG_ONLY_NOT_AN_ORDER`, `order_submitted=false` and `governed_order_path=/trade`.
- **Routes kept:** the routes were not deleted, because the UI and about 10 dashboard tests read that log. Deleting them is a UX decision for the owner.

### 1.4 What RC1 does **not** prove
- **No real-data calibration has been run.** This build environment cannot reach market-data hosts: every request returned HTTP 000. No artifact exists, so no strategy has passed the gates, and no profitability is claimed.
- **No shadow paper record exists yet,** and no 72-hour endurance run has been done.
- **No broker sandbox has been exercised.** `SimulatedVenue` verifies the OMS logic, not a broker. A practice-broker adapter and credentials are still required.

All tests use **synthetic** candles, events and venues, labelled as synthetic, to verify mechanics only.

## 2. Feature → test matrix
| Requirement | Tests |
|---|---|
| Candle validation, freshness, practice-only OANDA, cache digest | `tests/test_css_rc1_signals.py` (validation, provider, cache tests) |
| No look-ahead; conservative labels; costs; walk-forward without leakage | `test_features_have_no_look_ahead`, `test_triple_barrier_*`, `test_walk_forward_*`, `test_folds_without_trades_count_against_positive_fold_fraction` |
| Each release gate can fail | `test_gates_each_check_can_fail` |
| Dual-control approval, revocation, tamper detection | `test_approvals_need_two_distinct_super_users_and_passing_gates`, `test_approved_artifact_becomes_unroutable_if_edited`, `test_artifact_digest_detects_tampering` |
| Producer refusals and signal fields | `test_producer_*` |
| Real-data signals reach the governed router only via approved bridge | `test_producer_emits_calibrated_signal_and_bridge_routes_it`, `test_bridge_refuses_real_data_signal_when_approval_missing_or_mismatched` |
| Shadow journal | `test_shadow_runner_journals_heartbeats_and_decisions` |
| Idempotency, rejection, partial fills, slippage, disconnects | `tests/test_css_rc1_oms.py` (OMS unit tests) |
| Reconciliation (UNKNOWN, mismatches, orphans, crash between fill and booking) | `test_disconnect_*`, `test_reconcile_*`, `test_router_books_fill_left_unbooked_by_a_crash` |
| Emergency shutdown (persists, cancels, blocks, resume control) | `test_emergency_shutdown_*`, `test_shutdown_with_venue_down_*`, `test_router_halt_rejects_before_evaluation` |
| Router books venue fills only | `test_router_*` in `test_css_rc1_oms.py` |
| Legacy retirement | `tests/test_css_rc1_retirement.py` |

## 3. Deployment (paper; on FINANCE, by the owner's operator — not performed here)
1. **Freeze and check out the exact commit.** Freeze the reviewed RC1 SHA and check it out into a **new** directory.
   - Do not touch the production checkout `9bc3c52` or the candidate `2b6ec7c3`.
2. **Install and run the full suite.**
   - `python -m venv .venv`
   - `.venv\Scripts\python -m pip install -r requirements.txt`
   - `.venv\Scripts\python -m pytest -q`
   - Archive the log.
3. **Confirm the safety flags:**
   - `execution_allowed=false`;
   - `live_trading_blocked=true`;
   - the kill switches observed;
   - `LEGACY_LOOP_BROKER_EXECUTION_PERMITTED=False`.
4. **Paper runtime state goes under `artifacts/trading_profiles/`:**
   - the existing CSS-118 files;
   - `calibration_approvals.jsonl`;
   - `oms/`, but only if the OMS is enabled.

## 4. Real-data calibration and shadow run (operator runbook)
Requires outbound HTTPS to `api.exchange.coinbase.com`. For FX it also requires `api-fxpractice.oanda.com` and an `OANDA_PRACTICE_TOKEN` read from the environment, never committed.

```
python tools/css_fetch_candles.py --source coinbase --instrument BTC-USD --granularity 3600 --bars 8000 --cache data/market_cache
python tools/css_calibrate.py --cache data/market_cache --source coinbase_exchange_public --instrument BTC-USD \
    --asset-class CRYPTO --granularity 3600 --out artifacts/calibration
```

**Reading the result.** Each artifact prints its OOS metrics and either `gates=PASS` or `gates=FAIL`.
- A FAIL is a valid and expected outcome; **do not tune thresholds to pass**.
- Only a PASS artifact can be approved.

**Approval needs two different SUPER_USERs.** Each must review:
- the artifact JSON: its data digest, code revision, OOS table and per-fold results;
- the cost assumptions: CRYPTO fees of 60 bps per side are the conservative taker default.

Each approver then calls `CalibrationApprovals(root).approve(artifact, actor_ctx=...)` with their own identity.

**Shadow run.** It is paper only, with wall-clock time and a JSONL journal:
```
python tools/css_signal_shadow.py --artifacts artifacts/calibration --instrument BTC-USD --source coinbase \
    --granularity 3600 --hours 72 --journal artifacts/shadow/rc1_shadow.jsonl
```

**Evidence to keep:**
- the candle CSV and its SHA-256;
- the artifacts;
- the approvals ledger;
- the shadow journal;
- the `paper_book.json` and attribution ledger extracts.

## 5. 72-hour endurance
Use the existing package unchanged; see `CSS064_ENDURANCE_RUN_PACKAGE.md`.
1. Run the `css064_endurance_package.py preflight` script.
2. Run the 72-hour monitor: `css_ov002_72h_endurance.py --target-hours 72`.
3. Run the `finalize` step.

It must run on FINANCE in genuine wall-clock time; it cannot be simulated. Running the shadow run (§4) during the same window yields a single combined record.

## 6. Broker sandbox verification (not yet possible)
**Missing:**
- a practice-broker adapter implementing the `Venue` protocol in `backend/oms/paper_oms.py` (`submit`, `status`, `cancel`, `all_orders`) against a broker **practice** endpoint;
- the practice credentials, which are owner-held.

**Scenarios to execute.** The same scenarios as `test_css_rc1_oms.py`, against the sandbox:
- rejection (invalid size);
- partial fill (a limit order away from the market);
- measured slippage;
- a duplicate `client_order_id`;
- a disconnect during submit, then reconciliation;
- a reconciliation diff;
- emergency halt and cancel.

**Evidence:** the OMS journal plus the broker's own order history export.

## 7. Monitoring and recovery
**Watch:**
- **Shadow journal:** a HEARTBEAT every cycle. A missing heartbeat for more than 2 × the poll interval is an incident.
- **PRODUCED reasons:** watch especially `market_data_unavailable:*` and `calibration_not_routable:*`.
- **Router outcomes:** the share of REJECTED decisions by stage.
- **OMS:**
  - any `UNKNOWN` order older than one poll;
  - `reconcile()["clean"] == false`;
  - any `EMERGENCY_HALT` event.
- **Ledger verification:** `tools/verify_css_ledger_anchors.py`. Until custody is decided (B3), the expected result is `UNANCHORED`.

**Recovery actions:**
- **Data outage:** the producer refuses by itself (stale data), so no action is needed beyond restoring access.
- **OMS uncertainty:** run `router.reconcile_orders()`. If the result is still not clean, call `emergency_shutdown`; resuming requires a SUPER_USER and a clean reconciliation.
- **Bad calibration:** a SUPER_USER calls `CalibrationApprovals.revoke(artifact)`. Routing stops at the next cycle.

## 8. Rollback
Every change is additive or fails closed.
1. **Revert RC1's three commits individually.**
   - R3 restores the random candidates in the legacy loop, which is not recommended.
   - R2 removes the OMS; the default router path is unchanged anyway.
   - R1 removes the producer; no signals are routed.
2. **Revoke artifacts instead of reverting code.** This stops real-data routing immediately.
3. **Data:** archive `artifacts/calibration/`, `artifacts/shadow/`, `calibration_approvals.jsonl` and `oms/`. Do not delete them.
