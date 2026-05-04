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
- [ ] CSS high-confidence path cannot override governance veto
- [ ] probability approve_trade remains part of final execution decision
- [ ] raw score vs clamped score corrected or confirmed
- [ ] CSS component floors reviewed for weak signal admission

## B. Governance Gate
- [ ] no synthetic session fallback without audit clarity
- [ ] unknown asset class rejected explicitly
- [ ] expected_value required
- [ ] cost required
- [ ] negative cost rejected
- [ ] probability bounded between 0 and 1
- [ ] empty portfolio_state handled fail-closed
- [ ] rejection details include useful audit context
- [ ] risk exposure/notional check reviewed

## C. PnL Engine
- [ ] entry cost deducted
- [ ] exit cost deducted
- [ ] spread included
- [ ] slippage included
- [ ] fees included
- [ ] zero-cost defaults reviewed
- [ ] realized/unrealized separation confirmed
- [ ] no double counting
- [ ] mark price vs executable price reviewed

## D. Dashboard / PnL Reporting
- [ ] dashboard uses same PnL values as engine
- [ ] start-of-cycle vs end-of-cycle labels clear
- [ ] no stale PnL displayed as current
- [ ] balances persist correctly
- [ ] no random PnL remains in live/paper-real mode

## E. Options
- [ ] full option symbol key used everywhere
- [ ] options_pnl/options_trades/options_wins aligned
- [ ] no stub/full-key double counting
- [ ] restart merge does not inflate options PnL

## F. Persistence / Crash Safety
- [ ] state files saved correctly
- [ ] save failures logged
- [ ] no silent persistence failure
- [ ] per-trade vs end-cycle save policy decided
- [ ] futures_lifetime_total consistency confirmed

## G. Risk / Bleed Governor
- [ ] asset-class bleed governor active
- [ ] total portfolio drawdown guard reviewed
- [ ] all-asset-loss scenario handled
- [ ] freeze logic uses stable cycle snapshot

## H. Regression Prevention
- [ ] no duplicate execute_trade definitions
- [ ] no duplicate display_dashboard definitions
- [ ] no missing imports
- [ ] no parallel unreconciled state models
- [ ] no dead/comment-only modules treated as active