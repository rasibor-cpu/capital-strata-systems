# CSS final engineering closeout — 16 Oct 2026

**Paper only. LIVE_TRADING_AUTHORIZED = NO. PRODUCTION_GO = NO.** Nothing in this branch places
an order, contacts a broker for execution, moves money, merges a protected branch or deploys.

Branch `claude/css-final-closeout`, stacked on PR #124 (`claude/css-rc1-signal-pipeline`, itself on
#122 → #119 with #120 and #121) and carrying PR #123 (`css-final-integration`). Baseline `09b2cbd1`.

## 1. Reconciliation (Phase 1)

PRs #123 and #124 were both cut from `09b2cbd1` and solved the same problems differently. Both
are merged here; where they overlapped, the stricter implementation is canonical.

| Overlap | Resolution |
|---|---|
| Legacy random candidates (B5) | RC1's unconditional `return []` kept; #123's flag kept for the other branch it guards. |
| Signal producer (B1) | **Canonical: `backend/signals` (RC1).** Fresh real bars, two-SUPER_USER approval, routed only through `publish_real_data`. #123's `CalibratedSignalRunner` replays historical CSV bars; it is now confined to research books and refuses `artifacts/trading_profiles`. |
| Launcher paper routes (B6) | #123 routed them through the governed router but fabricated inputs: a unit **quantity was used as a currency notional**, a missing stop became **1 %**, and the session was synthesised (**session id = user id, created = now**), defeating R7's recent-sign-on check. All three removed; missing values now refuse. |

Other defects found and fixed with tests:
- **Forming bar used for signals.** Coinbase returns the in-progress candle; RC1 computed features on it. Bars that have not closed are now dropped in every provider and again in the producer.
- **Alpaca crypto "latest" bar was five weeks old** on the real endpoint (ascending order + page limit). Fixed by newest-first requests; freshness is enforced.
- **Position limits could be loosened by environment** (`CSS_MAX_TOTAL_OPEN_POSITIONS=50` raised the cap). Overrides can now only tighten.

## 2. Market data (Phase 2)

Implementation: `backend/signals/candles.py`, `backend/signals/market_data.py`.

Every series is classified `LIVE`, `DELAYED`, `INDICATIVE`, `REPLAY` or `SYNTHETIC`. The producer acts
on `LIVE` only by default; `REPLAY`, `SYNTHETIC` and unclassified data **cannot** be allowed for live
signals (constructor refuses). No feed is assumed to be consolidated or redistributable:
Coinbase, Alpaca crypto and OANDA are each one venue's prices; IEX is a single exchange and is
`INDICATIVE`.

Also implemented: provider failover with per-attempt provenance; symbol normalisation; UTC
timestamps and exchange clock-skew measurement; freshness and stale-data rejection; per-host rate
limiting and bounded exponential backoff (Retry-After honoured; 451/401/403 never retried);
candle completeness, realised volatility and volume metrics; best bid/ask, spread and ±25 bps
depth; cross-provider discrepancy check (fail closed); deterministic replay; explicit blocked
states for missing credentials, restricted jurisdictions and absent options/futures feeds.

### 2.1 Verified provider matrix

Live, read-only probe on a GitHub-hosted runner, CI run **38883160466** (commit `8a6296e`,
2026-10-16 ~09:50 UTC, `CSS_OPERATING_COUNTRY=CA`). PASS = fresh, validated, complete bars fetched
from the real endpoint in that run. Summaries are check-run annotations on that run.

| Asset class | Provider | Verdict | Evidence / exact reason |
|---|---|---|---|
| Crypto | Coinbase Exchange public | **PASS** (LIVE) | 349 × 1h bars, last closed bar 08:00 UTC, completeness 1.0, 0 zero-volume bars; book spread 0.001 bps, ±25 bps depth ≈ $6.6M bid / $7.7M ask; 8,000 × 1h, 8,000 × 6h, 4,106 × 1d BTC-USD and 8,000 / 8,000 / 3,801 ETH-USD bars cached with SHA-256. |
| Crypto | Alpaca crypto public (v1beta3) | **PASS** (LIVE) | 176 × 1h bars, last closed bar 08:00 UTC; spread 2.8 bps, ±25 bps depth ≈ $0.74M per side; 8,000 × 1h BTC-USD history. Thin venue (median bar volume 0.015 BTC). |
| Crypto | Cross-provider check | **PASS** | Coinbase vs Alpaca BTC-USD, 176 overlapping bars: median 0.34 bps, max 4.9 bps, last 0.11 bps. |
| — | Clock | **PASS** | Coinbase `/time` skew 0.016 s (limit 5 s). |
| Crypto | Binance Spot public | **BLOCKED** | `binance_jurisdiction_restricted:CA` — Binance.com does not serve Canada; refused before any request. Adapter (klines, depth, server time, 451 handling) is implemented and unit-tested. Not worked around via the runner's location. |
| Equities/ETFs | Alpaca IEX | **BLOCKED** | `alpaca_credentials_missing`. Adapter implemented; classified INDICATIVE (single exchange). |
| FX | OANDA v20 practice | **BLOCKED** | `oanda_practice_token_missing`. Adapter refuses the live host. |
| Options | — | **BLOCKED** | `no_authorized_options_feed` (IBKR adapter is a placeholder). |
| Futures | — | **BLOCKED** | `no_authorized_futures_feed`. |

## 3. Signal path and strategy evidence (Phase 3)

Traced path, each hop with a test:

```
real feed (Coinbase public, LIVE)          market_data / candles: validate, drop forming bar, classify
 → fresh, complete, LIVE bars              producer: check_fresh, classification, volume, spread, depth
 → features (no look-ahead)                research.compute_features
 → approved strategy rules                 TREND_BREAKOUT / MEAN_REVERSION
 → calibrated probability & net EV         artifact (walk-forward, costs, data_source pinned)
 → dual-control approval check             CalibrationApprovals (2 distinct SUPER_USERs)   ← stops here today
 → CssEngineSignalBridge.publish_real_data → TradingRouter: consent, mode, personality, limits,
   R14F, R7 unified gate, ExecutionGate/AntiBleed, capital governors → PaperBook / PaperOMS
 → exit cycle → commercial fee ledger → hash-chained ledgers
```

**Real-data calibration (CI run 38883160466).** The two approved strategies were walk-forward
calibrated on Coinbase BTC-USD and ETH-USD at 1h, 6h and 1d, and on Alpaca BTC-USD at 1h —
14 artifacts, unchanged gates (≥100 OOS trades, one-sided 95 % lower bound on net bps > 0, Brier
below base rate, ≥60 % positive folds, max drawdown ≤ 2,000 bps), costs 135 bps round trip
(60 bps/side taker fee).

**Result: 0 of 14 artifacts pass. No strategy is routable and no profitability is claimed.**

| Horizon | Labelled events (mean gross → net bps) | OOS outcome |
|---|---|---|
| 1h (BTC, ETH; Coinbase and Alpaca) | 116–151 per strategy; gross −22 to +4 bps → net −131 to −157 bps | Calibrated EV never positive → 0 OOS trades selected |
| 6h (BTC, ETH) | 124–144; gross −37 to +2 → net −133 to −172 | 0 OOS trades selected |
| 1d MEAN_REVERSION | 46–54; gross −197 to −276 → net −332 to −411 | 0 OOS trades selected |
| 1d TREND_BREAKOUT BTC | 106; gross +163 → net +28 | 57 OOS trades, mean +2.8 bps, lower bound −192 bps, drawdown 7,632 bps |
| 1d TREND_BREAKOUT ETH | 85; gross +324 → net +189 | 53 OOS trades, mean +64.6 bps, lower bound −210 bps, drawdown 5,511 bps |

Reading: at intraday horizons the strategies have no gross edge at all, so costs dominate. Daily
trend-following shows positive in-sample averages but too few trades, too much variance and
too deep a drawdown to pass. Twelve artifacts were tested, so even a single future PASS must be
treated as a possible false discovery. Thresholds were not changed.

**Real-data producer cycle (same run).** For BTC-USD and ETH-USD the producer fetched fresh LIVE
Coinbase bars (last closed bar 08:00 UTC), measured the live spread (0.001 / 0.04 bps) and refused
every artifact with `calibration_not_routable:gates_not_passed`. The approvals ledger was empty,
as it must be: approvals are human-only. **The real-data path is verified up to the calibration
gate; no real-data signal has reached the router, by design.**

## 4. Product features (Phase 4)

| Area | Status | Evidence |
|---|---|---|
| 4 operating modes × 5 risk personalities | PASS (paper) | `tests/test_css_closeout_mode_personality_matrix.py`: every cell through consent, R14F, R7, ExecutionGate/AntiBleed and the book; plus the CSS-118 suites. |
| R7 unified gate, R14F, AntiBleed | PASS (paper) | CSS-118/RC1 suites (`test_r14f_gate_parity.py`, router and gate tests); AntiBleed cooldown observed rejecting a re-entry in the commercial integration test. |
| Position limits 10 (crypto 3, FX 3, options 2, futures 2) | PASS | `tests/test_css_closeout_position_limits.py`; env overrides tighten only. |
| Commercial model | PASS (accrual only) | `backend/commercial/fee_ledger.py`, `tests/test_css_closeout_commercial.py` (18 tests). Commission only on CSS-attributable profit above the loss-recovery high-water mark; independent-trade platform fee; idempotent; reversals with deterministic replay and reconciliation; bounded refunds; tamper-evident. Wired into the canonical router's exit cycle. **No money is collected or moved.** |
| Paper OMS, reconciliation, emergency halt | PASS against `SimulatedVenue` | `tests/test_css_rc1_oms.py`. No broker sandbox adapter exists (blocker). |
| Operator surfaces | Added | `GET /paper/fees` (own statement only), `GET /market-data/status` (no network, no secrets). |

## 5. Testing (Phase 5)

Commands (CI, Python 3.11): `python -m pytest -q -p no:cacheprovider -rfEs` (full suite, Linux and
Windows); targeted + Playwright UX: `pytest tests/test_css118_*.py tests/test_css_rc1_*.py
tests/test_css_closeout_*.py tests/test_r14f_gate_parity.py tests/engine/test_execution_gate_volatility_sizing.py
tests/test_mobile_audit_replay_limit.py`. Workflow `css118-validation.yml`; counts are published as
check annotations.

| Run | Commit | Linux full | Windows full | Targeted + UX (Playwright) |
|---|---|---|---|---|
| 38882199876 | `M1` (market data) | success | success | success |
| 38883133131 | `60616ae` | success | in progress at writing | success |
| 38883160557 | `8a6296e` | in progress at writing | in progress at writing | **440 passed** |
| local (Python 3.13) | `3c13abe` (merge only) | 4,521 passed, 1 failed*, 9 skipped | — | — |

\* The single local failure was `test_phase151…deprecated_utc_clock_references`, triggered by a helper
named `_utcnow` added mid-run; renamed to `_now_utc` and re-verified. Skips: Playwright not installed
locally, Windows-only probes, a module not on this branch, no live session file.

Previously reported counts (Linux 4,457 / Windows 4,451 / UX 319) are superseded by the runs above;
this branch adds ~140 tests. Environment limitations: this build host cannot reach market-data
hosts or download CI artifacts/logs; real-data evidence and counts were therefore produced on
GitHub runners and read back through check annotations.

## 6. Operator setup

1. Fresh directory at the reviewed commit; never the production checkout.
   ```
   git clone https://github.com/rasibor-cpu/capital-strata-systems css-closeout && cd css-closeout
   git checkout <reviewed SHA of claude/css-final-closeout>
   python -m venv .venv && .venv\Scripts\python -m pip install -r requirements.txt
   .venv\Scripts\python -m pytest -q            # archive the log
   ```
2. Configuration: copy `.env.paper.example` to `.env.paper`; keep every live flag false. Market data:
   `CSS_OPERATING_COUNTRY=CA` (Binance then reports BLOCKED by design); optionally
   `OANDA_PRACTICE_TOKEN` and `APCA_API_KEY_ID`/`APCA_API_SECRET_KEY`. Never commit values.
3. Check feeds: `python tools/css_market_data_matrix.py --probe --out artifacts/market_data_matrix.json`.
   Only PASS rows may be used; BLOCKED rows state the exact reason.
4. Calibrate (reports only; never tune thresholds to pass):
   ```
   python tools/css_fetch_candles.py --source coinbase --instrument BTC-USD --granularity 86400 --bars 8000 --cache data/market_cache
   python tools/css_calibrate.py --cache data/market_cache --source coinbase_exchange_public --instrument BTC-USD --asset-class CRYPTO --granularity 86400 --out artifacts/calibration
   ```
5. Only an artifact with `gates=PASS` can be approved, by **two different SUPER_USERs**, each after
   reviewing data digest, code revision, OOS table, folds and cost assumptions.
6. Shadow (paper): `python tools/css_signal_shadow.py --artifacts artifacts/calibration --instrument BTC-USD --source coinbase --granularity 86400 --hours 72 --journal artifacts/shadow/run.jsonl`.

## 7. Deployment runbook (paper environment only)

1. Freeze the reviewed SHA; record it with the CI run IDs (Linux, Windows, UX, real-data evidence).
2. Deploy to a **new** directory on FINANCE; leave production `9bc3c52` and candidate `2b6ec7c3` untouched.
3. Run the full suite; confirm safety flags: `execution_allowed=false`, `live_trading_blocked=true`,
   kill switches observed, `LEGACY_LOOP_BROKER_EXECUTION_PERMITTED=False`.
4. New paper state appears under `artifacts/trading_profiles/`: `commercial/` (fee ledger),
   `calibration_approvals.jsonl`, `oms/` (if enabled).
5. Start the shadow run and the 72-hour endurance package together (`CSS064_ENDURANCE_RUN_PACKAGE.md`).
6. Monitor: shadow heartbeats; `market_data_unavailable:*`, `market_quality:*`, `data_source_mismatch:*`
   reasons; OMS reconcile clean; `fee_posting_errors` empty; ledger verification.

## 8. Rollback

All changes are additive or fail closed.
1. **Stop routing without code changes:** revoke the calibration artifact (one SUPER_USER) — routing stops next cycle.
2. **Revert commits individually** (`git revert <sha>`), newest first. Reverting M2 removes fee accrual
   (the router works without it); reverting M1 restores RC1's providers (and the forming-bar defect).
3. **Data:** archive `artifacts/trading_profiles/commercial/`, `artifacts/calibration/`,
   `artifacts/shadow/`, approvals and OMS journals. Never delete hash-chained ledgers.
4. Re-run the full suite on the reverted SHA before resuming paper operation.

## 9. Outstanding blockers and required human action

Engineering work that could be done without credentials, licences or approvals is done. What remains:

| # | Blocker | Who | Exact action |
|---|---|---|---|
| 1 | **No strategy passes the release gates on real data** (§3). | Owner / quant research | Decide the research direction (lower-cost venue tier or maker execution to change the 135 bps cost assumption — only with the broker's actual fee schedule; new strategy candidates). Never relax gates to pass. |
| 2 | Dual-control approval of a passing artifact | Two SUPER_USERs | Only after #1 yields a PASS artifact. |
| 3 | OANDA FX data | Owner | Issue an OANDA **practice** token; add as `OANDA_PRACTICE_TOKEN` (repo secret for CI evidence, `.env.paper` on FINANCE). |
| 4 | Alpaca equities data | Owner | Issue Alpaca data keys (read-only use); add `APCA_API_KEY_ID` / `APCA_API_SECRET_KEY` the same way. IEX remains INDICATIVE. |
| 5 | Binance | Owner + counsel | Binance.com does not serve Canada; status stays BLOCKED unless counsel confirms a lawful, eligible jurisdiction. Do not use VPNs or foreign runners to bypass. |
| 6 | Options / futures feeds | Owner | Select and license an authorized feed; until then both stay BLOCKED (governed caps 2/2 remain). |
| 7 | Broker sandbox adapter for the OMS | Owner + engineering | Practice-broker credentials and authorization to build a `Venue` adapter; then run the §6 scenarios of the RC1 package. |
| 8 | 72-hour shadow + OV-002 endurance on FINANCE | Owner's operator | Wall-clock only; needs #1–#2 for a signal-bearing shadow (an empty-signal shadow can run now). |
| 9 | Owner decisions B2 (AntiBleed vs CAD 20), B3 (anchor key custody), B4 (approved traders), B7 (personality caps) | Owner | As recorded in `docs/governance/CSS118_CLOSEOUT.md`. |
| 10 | Commercial policy | Owner + counsel | Confirm: copy-trader trades not CSS-attributable (current default), rounding down, high-water mark per user across all CSS trades, refund authority. No billing integration exists; nothing is charged. |
| 11 | Independent code review of #119–#124 and this branch; compliance review | Reviewer, counsel | Required before any merge or live consideration. |
| 12 | Live trading | Owner | Separate written authorization naming account, capital, instruments and limits. **Not given. Not requested here.** |

**Resume command** (paper; on a host with market-data access):
```
python tools/css_market_data_matrix.py --probe --out artifacts/market_data_matrix.json
```
or re-run the GitHub workflow "CSS real-data evidence" (workflow_dispatch) on `claude/css-final-closeout`.
