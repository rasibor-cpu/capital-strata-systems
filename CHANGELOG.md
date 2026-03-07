# Capital Strata Systems – Changelog

---
# Changelog

All notable changes to Capital Strata Systems (CSS) are documented here.

---

## [v54] - 2026-03-07
### Added
- Introduced `tools/css_autonomous_loop_v54.py` as the new **Safe Fast Trend Engine**.
- Added continuous autonomous paper-trading loop with:
  - live Coinbase market scanning
  - top-momentum asset ranking
  - autonomous paper position handling
  - trailing-stop based exit management
- Added visible **scan progress output** for each asset during each cycle.
- Added safer position-file cleanup logic to avoid crashes when deleting missing state files.
- Added stable cash-state reporting in the engine output.
- Added working dashboard integration through `tools/css_portfolio_dashboard_v51.py`.
- Added market scanner / ranking support through `tools/css_market_intelligence_v52.py`.

### Changed
- Reworked the trading engine from earlier autonomous-loop variants into a faster, safer v54 architecture.
- Reduced scan latency by lowering lookback depth and shortening per-asset sample delay.
- Lowered entry threshold for testing so paper trades can trigger more easily in live observation.
- Replaced simple fixed-profit exit logic with **trend-riding trailing-stop behavior**.
- Improved runtime visibility by printing:
  - current scan progress
  - ranked momentum assets
  - hold-state information
  - trailing-stop level
  - live cash balance
  - last update timestamp
- Aligned engine state persistence with the active dashboard workflow.

### Fixed
- Fixed repeated loop “looks frozen” behavior by adding visible scan-progress output and reducing cycle time.
- Fixed crash risk around `POSITION_FILE.unlink()` by introducing safe file-clear handling.
- Fixed dashboard/runtime mismatch by stabilizing the state file structure used during paper trading.
- Fixed operational confusion caused by slow scan cycles by making engine progress explicit in terminal output.

### Verified
- Verified autonomous loop runs continuously.
- Verified live ranking of scanned Coinbase assets.
- Verified open BTC paper position loaded and monitored successfully.
- Verified trailing-stop logic is active and updating.
- Verified dashboard reads live position state correctly.
- Verified trade summary and realized PnL display correctly.
- Verified commit, push, and version tag completed successfully.

### Repository / Version Control
- Commit created for autonomous trend-engine milestone.
- Remote push completed successfully.
- Tag created:
  - `css-engine-v54-trend`

---

## [v53] - 2026-03-06
### Added
- Introduced `tools/css_autonomous_loop_v53.py`.
- Added first fully connected autonomous paper-trading loop using ranked momentum assets.
- Added paper BUY/SELL logging to `audit_logs/trades.jsonl`.
- Added state persistence for open position in `backend/state/spot_position.json`.

### Changed
- Connected scanner output to autonomous engine behavior.
- Enabled basic automatic entry logic based on ranked momentum assets.

### Notes
- v53 served as the transition build between ranking-only logic and the working trend-engine architecture in v54.

---

## [v52] - 2026-03-06
### Added
- Introduced `tools/css_market_intelligence_v52.py`.
- Added market intelligence layer for:
  - Coinbase price polling
  - simple momentum scoring
  - top-asset ranking display
- Added faster replacement scanner version with visible progress output.

### Changed
- Improved responsiveness of the scanner by reducing sample count per asset.
- Improved usability by showing scan progress line by line.

### Verified
- Verified live ranking output for assets such as SOL, LINK, AVAX, MATIC, and ATOM.

---

## [v51] - 2026-03-06
### Added
- Introduced `tools/css_portfolio_dashboard_v51.py`.
- Added terminal dashboard showing:
  - entry price
  - position USD
  - open timestamp
  - total trades
  - realized PnL
  - refresh cycle output

### Changed
- Updated dashboard to match real `spot_position.json` schema:
  - `entry_price`
  - `size_usd`
  - `timestamp`

### Fixed
- Fixed `NoneType` crash in unrealized PnL calculation.
- Fixed schema mismatch between dashboard expectations and actual engine state file.

### Verified
- Verified dashboard refreshes continuously.
- Verified dashboard reads live open position correctly.

---

## [v49] - 2026-03-06
### Added
- Added `tools/css_autonomous_loop_v49.py`.
- Added higher-version autonomous loop baseline before v53/v54 transition.
- Added expanded research path toward:
  - top-5 asset universe
  - trend-aware hold logic
  - dashboard foundation
  - market selector integration

### Repository / Version Control
- Tag created:
  - `css-engine-v49`

---

## [Development Summary]
### Current Stable Baseline
- **Trading engine baseline:** `tools/css_autonomous_loop_v54.py`
- **Dashboard baseline:** `tools/css_portfolio_dashboard_v51.py`
- **Market intelligence baseline:** `tools/css_market_intelligence_v52.py`

### Current Working Architecture
1. Market Scanner
2. Momentum Ranking
3. Autonomous Trend Engine
4. Position State File
5. Trade Log
6. Portfolio Dashboard

### Current Known Next Step
- Build **v55 Adaptive Market Discovery**
  - expand beyond fixed asset list
  - filter tradable / liquid Coinbase pairs
  - rank and select best opportunities automatically
# Phase 15 – Global Reporting Architecture

- Introduced global reporting gateway (backend/app/reporting_api.py)
- Added reusable report center screen (print from any screen)
- Implemented ageing engine (AR/AP/GL) with bucket logic
- Centralized authority-gated report registry
- Standardized regulator sign-off block
- Enabled timeframe + filters + explicit sections
- CLI + backend callable report engine[Unreleased]

# Added

FinCon-grade reporting architecture (ReportRequest, registry, authority gating)

Deterministic governance_summary report with timeframe + explicit sections

Sign-off metadata embedded in all regulator-facing outputs

CLI reporting surface with role/permission simulation

PCC governance decisions fully reproducible from JSONL log

Security

Fail-closed authority model for all registered reports

Governance reports restricted to ADMIN / SUPER_USER / FINCON_REPORTING

Architecture

Central report registry

Structured ReportRequest model (timeframe + sections + caller identity)

Separation of report registration and generation logic
## 2026-02-23 – Volatility-Gated Breakout Alpha Milestone (H1)

### Research Breakthrough
Validated volatility-conditioned breakout alpha across multiple FX instruments on H1 timeframe.

Key findings:
- Volatility gate: vol_pct >= 0.60
- Vol window: 100
- Lookback: 30
- Hold: 6
- Rank mode: simple
- Regime filter: ABS_LOGRET fallback supported

### Decile Validation Results
Across tested instruments:

- Monotonicity ratio: 1.0 (9/9 non-decreasing steps)
- D10 > D1 consistently
- Strength ranking becomes predictive only under elevated volatility
- Alpha concentrated in upper deciles (D8–D10)

Observed structural pattern:
- D1–D5: negative expectancy
- D6: transitional
- D7–D10: positive expectancy
- D8–D10 frequently win-rate near 1.0 in filtered regime

### Architectural Additions

Added / Updated:

- tools/run_breakout_deciles_alpha.py
- tools/run_strength_deciles_alpha.py
- tools/run_governance_retention_equal.py
- tools/run_full_allow_smoke.py
- tools/download_oanda_m5_1year.py
- tools/download_oanda_m5_multi.py
- tools/build_h1_from_m5.py
- engine/engine_loop.py (stability updates)

### Data Pipeline

Established reproducible research pipeline:
- OANDA M5 downloader
- M5 → H1 builder
- Decile diagnostics
- Volatility gating validation

### Strategic Conclusion

Breakout alpha is:
- Regime-conditional
- Volatility-sensitive
- Strength-ranked
- Tail-concentrated

---

### Detailed Commit Snapshot – Volatility-Gated Breakout Research Batch

**Development Scope:**
Implementation of volatility-conditioned breakout diagnostics and supporting research pipeline.

**Files Added:**
- tools/build_h1_from_m5.py  
- tools/download_oanda_m5_multi.py  
- tools/run_breakout_deciles_alpha.py  
- tools/run_governance_retention_equal.py  
- tools/run_strength_deciles_alpha.py  

**Files Modified:**
- engine/engine_loop.py  
- tools/download_oanda_m5_1year.py  
- tools/run_full_allow_smoke.py  

**Functional Enhancements:**

1. Volatility Percentile Gating
   - Introduced vol_pct threshold (>= 0.60)
   - Configurable rolling window (default 100)
   - ABS_LOGRET fallback when OHLC unavailable

2. Decile Diagnostics Framework
   - Equal-population strength decile construction
   - Expectancy and winrate per decile
   - Monotonicity scoring (non_decreasing_steps, ratio)
   - Structural validation via D10 > D1 check

3. Data Pipeline Stabilization
   - Multi-instrument OANDA M5 downloader
   - Deterministic M5 → H1 builder
   - Reproducible research flow

4. Governance Diagnostics
   - Retention analysis under ExecutionGate
   - Full-allow smoke testing harness

**Research Outcome:**
Under elevated volatility regimes:
- Strength ranking becomes predictive
- Alpha concentrated in D8–D10
- Cross-instrument monotonic decile structure observed

This batch establishes the breakout alpha layer as regime-conditional and strength-ranked.

Transition path defined:
Research → Strength threshold runner → Portfolio replay → RiskGovernor integration

This marks transition from exploratory research to structurally coherent alpha layer.