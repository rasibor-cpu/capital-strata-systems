# Capital Strata Systems – Changelog

> **Canonical release status:** [`docs/release/CSS_CANONICAL_RELEASE_STATUS.md`](docs/release/CSS_CANONICAL_RELEASE_STATUS.md)  
> This changelog is historical. It does **not** authorize production certification or live trading.  
> Current production result: **NOT CERTIFIED**. Controlled paper: **GO**.

---
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