---
id: TAI-001
status: READY
priority: 100
risk: HIGH
owner: UNCLAIMED
base_branch: css-v1.0.1-maintenance
starting_head: DISCOVER
commit_authority: NONE
push_authority: NONE
live_trading_authority: NONE
---

# TAI-001 — Technical / Price-Action Intelligence Engine V1

## Objective

Add a production-quality Technical / Price-Action Intelligence subsystem to Capital Strata Systems (CSS). This is an intelligence-layer enhancement only. It must not enable live trading, place orders, access or alter funded broker credentials, weaken any execution/risk gate, change live/paper defaults toward live execution, or start endurance/runtime trading.

## Mandatory pre-change gate

Before editing application code:

1. Read `AGENTS.md`, `.codex-instructions.md`, `agent_tasks/README.md`, and this task completely.
2. Identify the authoritative CSS workspace/worktree and report repository path, branch, HEAD, upstream, ahead/behind, staged files, modified tracked files, untracked files, and active merge/rebase/cherry-pick state.
3. Inspect recent commits sufficiently to understand the current certified/development lineage.
4. If workspace authority is ambiguous, existing modifications overlap this task, or repository state conflicts with this task, stop with `TAI-001 BLOCKED` before editing.
5. Claim the task per `AGENTS.md` before application-code changes.

## Architecture discovery

Identify and document the canonical locations/interfaces for:

- market data and OHLCV/time-series models/ingestion;
- existing technical indicators, including any Bollinger implementation;
- opportunity/signal models and scoring/confidence framework;
- market-regime logic;
- options intelligence;
- telemetry/observability;
- configuration;
- persistence/evidence and replay/backtest facilities;
- Unified Trade Gate, Margin Gate, RBAC, Capital Governor, AntiBleedGuard, kill switches/emergency stops, and final execution authorization boundary.

Reuse existing abstractions. Do not create a parallel trading architecture.

## Required technical intelligence

Implement deterministic machine-readable features from canonical OHLCV/time-series data.

### Trend

- SMA
- EMA
- moving-average relationships/crossovers
- trend direction
- trend strength
- higher-high/lower-low structure where safely determinable

### Momentum

- RSI
- MACD
- rate of change / momentum
- momentum acceleration/deceleration where justified

### Volatility

- ATR
- Bollinger Bands
- normalized volatility
- volatility regime/percentile only when sufficient history exists

### Volume

- relative volume
- volume anomaly detection
- volume confirmation of price moves

### Price structure

- support/resistance
- breakout/breakdown detection
- breakout confirmation
- distance from support/resistance
- gaps where meaningful

### Conservative candlestick observations

At minimum:

- doji
- hammer
- shooting star
- bullish engulfing
- bearish engulfing

Pattern detection is descriptive evidence only. Do not assign predictive value merely because a pattern exists.

## Multi-timeframe design

Support multiple timeframes where canonical data permits, such as 5m, 15m, 1h, 4h, and 1d. Do not fabricate missing data.

Produce per-timeframe observations plus:

- agreement/disagreement;
- dominant direction;
- confidence;
- higher-timeframe confirmation;
- conflict indicators.

## Output contract

Create a stable typed output contract conceptually covering:

- timestamp, instrument, timeframe, freshness, sample count;
- trend direction/strength;
- RSI, MACD state, Bollinger position, ATR, volatility state;
- volume score/anomaly;
- support/resistance and breakout state;
- pattern observations;
- directional score, confidence, regime, and evidence/reasons.

Normalize directional evidence where practical to `[-1.0, +1.0]`, with 0 neutral/indeterminate. Confidence must be distinct from direction. Missing or insufficient data must remain explicit and must not silently become neutral high-confidence evidence.

## Composite scoring

Implement an explainable configurable composite Technical Intelligence Score.

Requirements:

- configurable weights;
- deterministic identical-input output;
- expose component contributions;
- explicit insufficient-data state;
- confidence informed by data quality/history/agreement;
- avoid obvious double-counting of highly correlated indicators where practical;
- no hard-coded claim that any indicator predicts returns.

Technical intelligence is evidence, never trade authorization.

## CSS integration

Integrate at the narrowest appropriate existing intelligence/opportunity seam. It may enrich opportunity ranking, directional conviction, timing assessment, market-regime assessment, options opportunity analysis, or entry-quality assessment.

It must never directly authorize or submit an order. All existing governance remains authoritative.

## Options awareness

Where compatible with current options architecture, expose underlying trend, momentum, breakout confirmation, volatility state, timing quality, and higher-timeframe agreement. Do not confuse realized/technical volatility with option implied volatility. Never invent IV data.

## Anti-lookahead / data leakage

Mandatory fail gate. At time T, features may use only information available at T.

Prevent and test against:

- future candle access;
- centered rolling windows;
- future extrema leaking into support/resistance;
- future-confirmed pivots being represented as historically known;
- accidental forward fill from future observations.

Add explicit anti-lookahead tests.

## Outcome-attribution hooks

Preserve at signal time enough structured information for later empirical evaluation:

- raw indicator observations;
- normalized component scores;
- composite technical score;
- confidence;
- timeframe agreement;
- detected patterns;
- configuration/version;
- timestamp and instrument.

Do not claim profitability or optimize weights against test fixtures.

## Fail-closed data quality

Safely handle missing candles, duplicate timestamps, out-of-order observations, NaN/Infinity, malformed OHLC, negative volume, insufficient history, stale data, zero/constant-price sequences, and extreme values. Bad data must never accidentally create high-confidence trade evidence.

## Telemetry / explainability

Expose structured reasons/component contributions so Mission Control or later observability can explain why a score exists. The engine must not require rendered charts to operate.

## Mandatory tests

Add deterministic tests for:

- SMA/EMA;
- RSI;
- MACD;
- Bollinger;
- ATR;
- volume;
- trend/structure;
- support/resistance;
- breakout/breakdown;
- candlestick patterns;
- normalization;
- composite scoring;
- multi-timeframe behavior;
- stale/malformed data;
- insufficient history;
- repeatability;
- anti-lookahead;
- integration contract;
- trade-authority isolation.

Run relevant existing regression suites. Never report PASS for suites not run.

## Safety proof

Explicitly demonstrate through code inspection/tests that the subsystem cannot place orders, authorize trades, override RBAC, Unified Trade Gate, Margin Gate, Capital Governor, AntiBleedGuard, kill switches, credentials, or live-mode controls.

## Documentation

Document architecture, indicators/formulas or references, output contract, normalization/scoring, multi-timeframe behavior, data-quality rules, anti-lookahead rules, integration point, safety boundary, and outcome-attribution approach.

## Change control

- Do not commit.
- Do not push.
- Do not stage unless the environment requires staging solely for a non-committing validation and the task record clearly documents it; prefer no staging.
- Do not start CSS trading runtime.
- Do not install dependencies without stopping and reporting the requirement.
- Keep changes tightly scoped to TAI-001.

## Final report

Report:

A. workspace path
B. branch
C. HEAD
D. pre-change git state
E. architecture discovered
F. files added
G. files modified
H. indicators/features implemented
I. integration seam
J. output contract
K. tests added
L. exact test results
M. regression results
N. safety-boundary verification
O. `git diff --stat`
P. `git status --short`
Q. known limitations
R. recommended next step

End exactly with one of:

`TAI-001 IMPLEMENTED — READY FOR INDEPENDENT REVIEW`

or

`TAI-001 BLOCKED — <reason>`
