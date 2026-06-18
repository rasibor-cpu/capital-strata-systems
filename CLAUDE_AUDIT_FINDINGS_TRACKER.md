# Claude Audit Findings Tracker – CSS

## Baseline
FBL_RECOVERED_DASHBOARD_NO_REGRESSION_2026_05_04

## Rule
No profitability tuning until all critical/high audit findings are reviewed and either:
- fixed,
- confirmed already fixed,
- deferred with reason,
- marked not applicable.

---

## A. Orchestrator / Governance
- [x] CSS high-confidence path cannot override governance veto - FIXED
- [x] probability approve_trade remains part of final execution decision - FIXED
- [x] raw score vs clamped score corrected or confirmed - FIXED
- [x] CSS component floors reviewed for weak signal admission - FIXED

## B. Governance Gate
- [x] no synthetic session fallback without audit clarity - FIXED (Phase 113A)
- [x] unknown asset class rejected explicitly - FIXED
- [x] expected_value required - FIXED
- [x] cost required - FIXED
- [x] negative cost rejected - FIXED
- [x] probability bounded between 0 and 1 - FIXED
- [x] empty portfolio_state handled fail-closed - FIXED
- [x] rejection details include useful audit context - FIXED
- [x] risk exposure/notional check reviewed - FIXED

## C. PnL Engine
- [x] entry cost deducted - FIXED
- [x] exit cost deducted - FIXED
- [x] spread included - FIXED
- [x] slippage included - FIXED
- [x] fees included - FIXED
- [x] zero-cost defaults reviewed - FIXED
- [x] realized/unrealized separation confirmed - FIXED
- [x] no double counting - FIXED
- [x] mark price vs executable price reviewed - FIXED

## D. Dashboard / PnL Reporting
- [x] dashboard uses same PnL values as engine - FIXED
- [x] start-of-cycle vs end-of-cycle labels clear - FIXED
- [x] no stale PnL displayed as current - FIXED
- [x] balances persist correctly - FIXED
- [x] no random PnL remains in live/paper-real mode - FIXED

## E. Options
- [x] full option symbol key used everywhere - FIXED
- [x] options_pnl/options_trades/options_wins aligned - FIXED
- [x] no stub/full-key double counting - FIXED
- [x] restart merge does not inflate options PnL - FIXED

## F. Persistence / Crash Safety
- [x] state files saved correctly - FIXED
- [x] save failures logged - FIXED
- [x] no silent persistence failure - FIXED
- [x] per-trade vs end-cycle save policy decided - FIXED
- [x] futures_lifetime_total consistency confirmed - FIXED

## G. Risk / Bleed Governor
- [x] asset-class bleed governor active - FIXED
- [x] total portfolio drawdown guard reviewed - FIXED
- [x] all-asset-loss scenario handled - FIXED
- [x] freeze logic uses stable cycle snapshot - FIXED

## H. Regression Prevention
- [x] no duplicate execute_trade definitions - FIXED (Phase 110)
- [x] no duplicate display_dashboard definitions - FIXED (Phase 113C)
- [x] no missing imports - FIXED
- [x] no parallel unreconciled state models - FIXED
- [x] no dead/comment-only modules treated as active - FIXED