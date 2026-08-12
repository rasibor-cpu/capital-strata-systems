---
id: TAI-001
status: COMPLETE
priority: 100
risk: HIGH
owner: Codex GPT-5 session
base_branch: css-v1.0.1-maintenance
starting_head: 4d6f27d868fd5be3aba197c666a63dc1b63ae4b0
branch: css-agent-orchestration-v1
started_utc: 2026-08-12T02:08:05Z
completed_utc: 2026-08-12T02:19:17Z
reviewed_utc: 2026-08-12T00:00:00Z
commit_authority: NONE
push_authority: NONE
live_trading_authority: NONE
---

# TAI-001 â€” Technical / Price-Action Intelligence Engine V1

## Objective

Add a production-quality Technical / Price-Action Intelligence subsystem to Capital Strata Systems (CSS). This is an intelligence-layer enhancement only. It must not enable live trading, place orders, access or alter funded broker credentials, weaken any execution/risk gate, change live/paper defaults toward live execution, or start endurance/runtime trading.

## Mandatory pre-change gate

Before editing application code:

1. Read `AGENTS.md`, `.codex-instructions.md`, `agent_tasks/README.md`, and this task completely.
2. Identify the authoritative CSS workspace/worktree and report repository path, branch, HEAD, upstream, ahead/behind, staged files, modified tracked files, untracked files, and active merge/rebase/cherry-pick state.
3. Inspect recent commits sufficiently to understand the current certified/development lineage.
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

`TAI-001 IMPLEMENTED â€” READY FOR INDEPENDENT REVIEW`

or


## Implementation record

Status: REVIEW

Files added:

- `backend/intelligence/technical_intelligence.py`
- `docs/TAI-001_TECHNICAL_INTELLIGENCE.md`
- `tests/test_tai001_technical_intelligence.py`

Files modified:

- `backend/trading/autonomous_opportunity_intelligence_engine.py`
- `backend/trading/opportunity_ranking_engine.py`
- `agent_tasks/STATUS.md`

Purpose:

- Added deterministic advisory-only technical intelligence over canonical OHLCV candles.
- Added typed output contracts for single-timeframe and multi-timeframe evidence.
- Integrated technical evidence into the existing autonomous opportunity intelligence diagnostics/ranking seam.
- Preserved all execution, broker, credential, and governance boundaries.

Validation:

- `.\\.venv\\Scripts\\python.exe -m pytest -q -p no:cacheprovider tests\\test_tai001_technical_intelligence.py tests\\test_autonomous_opportunity_intelligence_engine.py tests\\test_opportunity_ranking_engine.py` -> `20 passed in 2.38s`
- `.\\.venv\\Scripts\\python.exe -m py_compile backend\\intelligence\\technical_intelligence.py backend\\trading\\autonomous_opportunity_intelligence_engine.py backend\\trading\\opportunity_ranking_engine.py` -> PASS
- `.\\.venv\\Scripts\\python.exe -m pytest -q -p no:cacheprovider tests\\test_intelligence_orchestrator.py tests\\test_market_regime_engine.py tests\\test_opportunity_ranking_engine.py tests\\test_autonomous_opportunity_intelligence_engine.py tests\\test_tai001_technical_intelligence.py` -> `31 passed in 3.44s`
- `git diff --check` -> PASS; warnings only for unreadable `C:\\Users\\Larry/.config/git/ignore` and CRLF normalization notices.

Safety-boundary verification:

- `backend/intelligence/technical_intelligence.py` imports only standard-library modules.
- Technical snapshots and multi-timeframe payloads set `advisory_only=True`, `execution_allowed=False`, and `live_trading_blocked=True`.
- Integration adds evidence to diagnostics/ranking only; it does not modify Unified Trade Gate, Margin Gate, RBAC, Capital Governor, AntiBleedGuard, kill switches, broker credentials, or live/paper defaults.
- No commit, staging, push, dependency install, runtime trading, or broker operation was performed.

## R1 remediation record

Status: REVIEW

Remediated UTC: 2026-08-12T03:00:23Z

Review findings remediated:

- HIGH: Future-timestamped candles now fail closed when any candle timestamp is later than the supplied/current evaluation time. The snapshot exposes `freshness="FUTURE_TIMESTAMP"`, records `FUTURE_TIMESTAMP` and `future_timestamped_market_data` warnings, suppresses confidence and directional score, and does not expose support/resistance or breakout evidence from future data.
- HIGH: Insufficient-data snapshots now neutralize derived directional/market-state fields: `trend_direction="INDETERMINATE"`, `trend_strength=0.0`, `breakout_state="INSUFFICIENT"`, `regime="INSUFFICIENT_DATA"`, `volume_score=0.0`, `volume_anomaly=False`, and zero-confidence/zero-weighted diagnostic contributions.

Additional review coverage added:

- Deterministic future-timestamp anti-lookahead test proving a future candle cannot influence current technical intelligence.
- Deterministic insufficient-data neutralization assertions for trend, regime, breakout, volume, observations, component contributions, confidence, and directional score.
- Trade-authority isolation coverage proving TAI has no order/authorization methods, advisory payload flags remain locked, and OpportunityRankingEngine preserves an existing gate denial.
- Volume anomaly coverage proving configured threshold behavior at `2.0x` baseline volume and proving malformed/insufficient volume cannot create high-confidence evidence.

Files modified in R1:

- `backend/intelligence/technical_intelligence.py`
- `tests/test_tai001_technical_intelligence.py`
- `agent_tasks/STATUS.md`
- `agent_tasks/REVIEW/TAI-001_TECHNICAL_INTELLIGENCE.md`

Validation:

- `.\\.venv\\Scripts\\python.exe -m pytest -q -p no:cacheprovider tests\\test_tai001_technical_intelligence.py` -> `11 passed in 1.32s`
- `.\\.venv\\Scripts\\python.exe -m pytest -q -p no:cacheprovider tests\\test_autonomous_opportunity_intelligence_engine.py tests\\test_opportunity_ranking_engine.py tests\\test_intelligence_orchestrator.py tests\\test_market_regime_engine.py tests\\test_market_regime_intelligence.py tests\\test_tai001_technical_intelligence.py` -> `38 passed in 3.58s`
- `.\\.venv\\Scripts\\python.exe -m py_compile backend\\intelligence\\technical_intelligence.py tests\\test_tai001_technical_intelligence.py backend\\trading\\autonomous_opportunity_intelligence_engine.py backend\\trading\\opportunity_ranking_engine.py` -> PASS

Safety-boundary verification:

- No live trading was enabled.
- No broker accounts or credentials were accessed.
- No execution, broker, RBAC, Unified Trade Gate, Margin Gate, Capital Governor, AntiBleedGuard, kill switch, emergency-stop, or live/paper default code was modified in R1.
- No staging, commit, push, merge, dependency install, or runtime trading command was performed.

## R2 remediation record

Status: REVIEW

Remediated UTC: 2026-08-12T03:27:05Z

Review findings remediated:

- HIGH: Generic computed insufficient-data snapshots now neutralize derived technical conclusions consistently. When `insufficient_data=True`, returned support/resistance, support/resistance distances, candlestick patterns, breakout state, trend direction/strength, regime, volume score/anomaly, directional score, component scores/confidence/weighted scores, and structure/pattern observations are fail-closed.
- LOW: Neutralized component contributions no longer retain pre-neutralization directional reason text. Insufficient-data component reasons are replaced with the neutral reason `insufficient_history`.

Regression coverage added:

- Deterministic 33-candle generic insufficient-history case, independent of future timestamps, with enough history to derive pre-neutralization structure, volume, trend, and bullish engulfing evidence. The regression proves no support, resistance, support/resistance distance, bullish/bearish pattern, directional component reason, positive component confidence, or weighted technical evidence is exposed after neutralization.

Files modified in R2:

- `backend/intelligence/technical_intelligence.py`
- `tests/test_tai001_technical_intelligence.py`
- `agent_tasks/STATUS.md`
- `agent_tasks/REVIEW/TAI-001_TECHNICAL_INTELLIGENCE.md`

Validation:

- `.\\.venv\\Scripts\\python.exe -m pytest -q -p no:cacheprovider tests\\test_tai001_technical_intelligence.py` -> `11 passed in 1.45s`
- `.\\.venv\\Scripts\\python.exe -m pytest -q -p no:cacheprovider tests\\test_tai001_technical_intelligence.py tests\\test_autonomous_opportunity_intelligence_engine.py tests\\test_opportunity_ranking_engine.py tests\\test_intelligence_orchestrator.py tests\\test_market_regime_engine.py tests\\test_market_regime_intelligence.py` -> `38 passed in 4.02s`
- `.\\.venv\\Scripts\\python.exe -m py_compile backend\\intelligence\\technical_intelligence.py tests\\test_tai001_technical_intelligence.py backend\\trading\\autonomous_opportunity_intelligence_engine.py backend\\trading\\opportunity_ranking_engine.py` -> PASS

Safety-boundary verification:

- No live trading was enabled.
- No broker accounts or credentials were accessed.
- No execution, broker, RBAC, Unified Trade Gate, Margin Gate, Capital Governor, AntiBleedGuard, kill switch, emergency-stop, or live/paper default code was modified in R2.
- No staging, commit, push, merge, dependency install, or runtime trading command was performed.

## R3 final acceptance review record

Status: COMPLETE

Reviewed UTC: 2026-08-12T00:00:00Z

Reviewer: independent acceptance-review agent (bounded acceptance verification, not implementation).

Scope: verified the seven acceptance areas from the R3 final acceptance review request — future data, generic insufficient data, valid-data behavior, anti-lookahead, volume anomaly, execution authority, and integration/regression — via direct code inspection and independent reproduction scripts against `TechnicalIntelligenceEngine`, not solely by trusting recorded R1/R2/R3 results.

Independent verification performed:

- Reproduced a 25-candle extreme-uptrend/volume-spike case (below the 34-sample floor) and confirmed every public field required to be neutralized under `insufficient_data=True` was in fact `None`/`0.0`/`INSUFFICIENT`/`INDETERMINATE`/empty, matching the full acceptance checklist.
- Reproduced a 60-candle clean-uptrend case and confirmed valid-data evidence is NOT suppressed (`rsi=100.0`, non-zero MACD, `trend_direction=UP`, `confidence=0.9`, `breakout_state=BREAKOUT_CONFIRMED`).
- Confirmed the 34/33-sample sufficiency boundary behaves as designed.
- Injected a future-timestamped candle mid-series (not just appended) and confirmed full fail-closed neutralization regardless of position in the series.
- Confirmed volume-anomaly threshold is inclusive (`2.00x -> True`, `1.99x -> False`) and negative volume fails closed before scoring.
- Confirmed `technical_intelligence.py` imports only the standard library, exposes no order/authorization methods, and hardcodes `advisory_only=True` / `execution_allowed=False` / `live_trading_blocked=True`.
- Re-ran `tests/test_tai001_technical_intelligence.py tests/test_autonomous_opportunity_intelligence_engine.py tests/test_opportunity_ranking_engine.py tests/test_intelligence_orchestrator.py tests/test_market_regime_engine.py tests/test_market_regime_intelligence.py` independently -> `38 passed`, matching the recorded R3 result.
- Located additional untested consumers of the two modified engines (`test_trade_tab_opportunity_ranking.py`, `test_trade_quality_pipeline.py`, `test_production_pipeline.py`, `test_phase153a_pre_live_nogo_cleanup.py`, `test_css_mobile_launcher.py`) and ran them; 2 failures in `test_css_mobile_launcher.py` were reproduced identically against the clean pre-TAI-001 base commit via a reversible `git stash`/`git stash pop`, confirming they are a pre-existing, unrelated environment issue (`runtime_mode` resolution) and not a TAI-001 regression. Working tree was fully restored after the stash test.
- Confirmed `git diff` for the TAI-001 integration into `opportunity_ranking_engine.py` is limited to a 14-line addition to `_fallback_intelligence_payload`; the pre-existing `CSSUnifiedTradeGate.approve_trade` call path is untouched.
- Re-ran `test_trade_authority_isolation_and_existing_gate_denial_is_preserved`, confirming a mocked high-confidence `ALLOW` decision is still overridden to `BLOCK` by a denying gate, independent of technical evidence.

Findings: none CRITICAL/HIGH/MEDIUM. One INFORMATIONAL observation recorded (top-level snapshot `confidence` is capped at <=0.34 rather than forced to exactly 0.0 when `insufficient_data=True`; component-level confidence and directional score are still forced to 0.0, and this is within the letter of the charter, which does not require top-level confidence to be exactly zero).

No commit, staging (beyond the task-tracking files listed below), push, merge, dependency install, live trading, broker access, or credential access was performed during this review. Two `git stash`/`git stash pop` operations were used solely to compare behavior against the clean base commit; the working tree was verified restored via `git status --short` immediately afterward.

Files modified in this review:

- `agent_tasks/REVIEW/TAI-001_TECHNICAL_INTELLIGENCE.md` (this record; file subsequently relocated to `agent_tasks/COMPLETE/`)
- `agent_tasks/STATUS.md`

Final disposition: **TAI-001 R3 FINAL ACCEPTANCE PASSED**. Ready for controlled integration/certification.

## R3 remediation record

Status: REVIEW

Remediated UTC: 2026-08-12T03:44:10Z

Review findings remediated:

- HIGH: Computed insufficient-data snapshots now neutralize public raw/derived indicator fields before snapshot construction. When `insufficient_data=True`, `rsi`, MACD line/signal/histogram, Bollinger upper/middle/lower/width/position, `atr`, and `normalized_volatility` are `None`; Bollinger and volatility states are `INSUFFICIENT`.
- HIGH: Insufficient-data indicator observations no longer retain pre-neutralization values or actionable indicator states. RSI and ATR observation values are `None`; MACD and Bollinger observation payloads are neutral/None with `INSUFFICIENT` state; volume, structure, SMA/EMA, and candlestick observation payloads are also non-authoritative.

Downstream consumer inspection:

- `rg -n "\brsi\b|\bmacd\b|\bbollinger\b|\batr\b|normalized_volatility|volatility_state|technical_intelligence" backend dashboard launcher scripts tests --glob *.py` reviewed TAI consumers.
- TAI integration consumers remain `AutonomousOpportunityIntelligenceEngine` and `OpportunityRankingEngine`; they use top-level multi-timeframe directional/confidence payloads and do not require single-timeframe RSI/MACD/Bollinger/ATR fields to be numeric.
- Other RSI/MACD/ATR/volatility matches are separate legacy/runtime contracts, risk utilities, UI market-state fields, or tests; no TAI public-payload consumer adjustment was required.

Regression coverage added:

- Deterministic insufficient-history assertions now prove `rsi`, MACD values, Bollinger numeric values/width/position, `atr`, `normalized_volatility`, and `volatility_state` are fail-closed.
- Observation assertions now prove RSI/MACD/Bollinger/ATR values are neutralized and all insufficient-data observation confidence and directional scores are zero.
- Recursive public snapshot scanning now proves no bullish/bearish actionable indicator state such as `ABOVE_UPPER`, `BELOW_LOWER`, `BREAKOUT_CONFIRMED`, `BREAKDOWN_CONFIRMED`, `UP`, `DOWN`, `HIGH`, `LOW`, `NORMAL`, `OK`, or candlestick pattern names remains in public insufficient-data snapshots.

Files modified in R3:

- `backend/intelligence/technical_intelligence.py`
- `tests/test_tai001_technical_intelligence.py`
- `agent_tasks/STATUS.md`
- `agent_tasks/REVIEW/TAI-001_TECHNICAL_INTELLIGENCE.md`

Validation:

- `.\\.venv\\Scripts\\python.exe -m pytest -q -p no:cacheprovider tests\\test_tai001_technical_intelligence.py` -> `11 passed in 1.52s`
- `.\\.venv\\Scripts\\python.exe -m pytest -q -p no:cacheprovider tests\\test_tai001_technical_intelligence.py tests\\test_autonomous_opportunity_intelligence_engine.py tests\\test_opportunity_ranking_engine.py tests\\test_intelligence_orchestrator.py tests\\test_market_regime_engine.py tests\\test_market_regime_intelligence.py` -> `38 passed in 3.74s`
- `.\\.venv\\Scripts\\python.exe -m py_compile backend\\intelligence\\technical_intelligence.py tests\\test_tai001_technical_intelligence.py backend\\trading\\autonomous_opportunity_intelligence_engine.py backend\\trading\\opportunity_ranking_engine.py` -> PASS

Safety-boundary verification:

- No live trading was enabled.
- No broker accounts or credentials were accessed.
- No execution, broker, RBAC, Unified Trade Gate, Margin Gate, Capital Governor, AntiBleedGuard, kill switch, emergency-stop, or live/paper default code was modified in R3.
- No staging, commit, push, merge, dependency install, or runtime trading command was performed.
