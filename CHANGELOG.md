# Capital Strata Systems – Changelog

---

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

Transition path defined:
Research → Strength threshold runner → Portfolio replay → RiskGovernor integration

This marks transition from exploratory research to structurally coherent alpha layer.