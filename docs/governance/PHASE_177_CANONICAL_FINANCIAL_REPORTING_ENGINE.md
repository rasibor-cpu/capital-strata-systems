# PHASE 177 — Canonical Financial Reporting Engine Foundation

**Repository:** `C:\rasib\source\capital-strata-systems`  
**Branch:** `css-unified-consolidation-2026-07-13`  
**Phase type:** Implementation — read-only foundation  
**Status:** COMPLETE (pending commit authorization)  
**Date:** 2026-07-19  
**Baseline HEAD:** `24f476f185de7aa76b1a242d18ecc74afc28e587`

---

## Objective

Establish a single authoritative, Decimal-safe, advisory financial reporting
layer for CSS that can later serve Executive Reporting, Mission Control,
Executive Intelligence, Board Reporting, Treasury, Portfolio Operations, Risk,
Options Income, and periodic reporting.

This phase does **not** alter trading, brokers, execution, portfolio
allocations, credentials, runtime scheduling, or live authority.

**Explicit boundary:** this is a **management-reporting foundation**, not a
substitute for audited statutory financial statements.

---

## Architecture

New package: `backend/financial_reporting/`

| Module | Role |
|--------|------|
| `models.py` | `FinancialAmount`, enums, Decimal helpers |
| `periods.py` | `ReportingPeriod` (UTC-aware) |
| `data_contracts.py` | Canonical input contract |
| `income_statement.py` | P&L with explicit signs |
| `balance_sheet.py` | BS with variance (no force-balance) |
| `cash_flow.py` | Summarized CF + reconciliation |
| `profitability_run_rate.py` | Target vs actual traffic lights |
| `readiness.py` | NOT_READY > RED > AMBER > GREEN |
| `engine.py` | `CanonicalFinancialReportingEngine` |
| `adapters.py` | MC state → contract + summary flatten |

API: `dashboard/runtime/api/financial_reporting.py`  
UI: Executive Overview card `#canonical-financial-reporting`  
Launcher: `css_mobile_launcher.py` mounts the router (same pattern as 176J).

---

## Source-of-truth model

- **Canonical for Phase 177+ management reporting:** `backend/financial_reporting/`
- **Not replaced:** `backend/app/financial_statements.py` / `trial_balance.py` (float GAAP journal helpers)
- **Not replaced:** `engine/ledger` Decimal PnL (trading ledger)
- **Not replaced:** Reports Center catalogue / producers
- **Consumes (thin):** Mission Control portfolio snapshot via adapter when explicit `financial_reporting` block is absent

Upstream producers should eventually populate `FinancialDataContract` (or
`state["financial_reporting"]`) rather than inventing parallel P&L models.

---

## Reporting periods

Types: `DAILY`, `WEEKLY`, `MONTHLY`, `QUARTERLY`, `YEAR_TO_DATE`, `ANNUAL`, `CUSTOM`.

Each period carries start/end (timezone-aware UTC), label, comparison window,
calendar/elapsed/remaining days, and open/closed status. Display timezone
conversion is available via `to_display_timezone`.

---

## Financial data contract

`FinancialDataContract` holds revenue/gains, costs/losses, balance-sheet,
cash-flow, target profit, and metadata.

`FinancialAmount` distinguishes:

| State | Semantics |
|-------|-----------|
| present + 0 | true zero |
| missing / unavailable / not_applicable | excluded from totals (never silent healthy zero) |

---

## Income-statement logic

Sections: revenue & gains → trading/direct costs → operating expenses → tax → net profit.

Calculated: gross/net trading income, total revenue, total direct costs, gross
profit, opex, operating profit, PBT, tax, net profit, margin.

**Sign convention:** gains/income positive increase profit; losses/costs are
**positive magnitudes** that reduce profit. Negative gains warn and are not
reclassified into the loss line (avoids double-counting).

---

## Balance-sheet logic

Assets / liabilities / equity totals; `liabilities_plus_equity`;
`accounting_equation_variance`; `balanced`. Unbalanced statements are reported,
never silently force-balanced.

---

## Cash-flow logic

Summarized operating / investing / financing nets; net change; expected vs
reported closing cash; reconciliation variance. No invented accrual adjustments.

---

## Profitability run-rate model

Inputs: actual net profit, target profit, reporting period, as-of.

Outputs: remaining required, elapsed/remaining days, actual/required daily run
rates, projected period-end profit & variance, % of target, traffic light,
confidence status.

Traffic lights (configurable thresholds, default amber max 1.5× actual pace):

- **GREEN** — achieved or projected with buffer
- **AMBER** — required pace ≤ configured multiple of actual
- **RED** — required pace materially exceeds tolerance
- **NOT_AVAILABLE** — missing target/dates/inputs

Edge cases: remaining days = 0; target already exceeded (required daily = 0);
negative actual profit; positive and negative targets; Decimal only.

---

## Decimal policy

All money math uses `decimal.Decimal` with `ROUND_HALF_UP` to cents
(`0.01`). Ratios quantize to `0.0001`. Serialization emits decimal strings.

---

## Readiness model

Evaluates income/expense/BS/CF availability, target, period validity, currency,
accounting equation, cash reconciliation.

Precedence (aligned with Phase 176J): **NOT_READY > RED > AMBER > GREEN**.

Numeric scores may not contradict NOT_READY (≤40) or RED (≤55).

---

## API schema

| Method | Path |
|--------|------|
| GET | `/api/financial-reporting/summary` |
| GET | `/api/financial-reporting/income-statement` |
| GET | `/api/financial-reporting/balance-sheet` |
| GET | `/api/financial-reporting/cash-flow` |
| GET | `/api/financial-reporting/profitability-run-rate` |

Summary includes net profit, target, % achieved, required daily run rate,
projected period-end profit, traffic light, readiness, nested statements,
`advisory_only=true`, `trading_impact=false`. Degrades safely on provider failure.
No credentials, tokens, or stack traces.

Schema version: `css.canonical_financial_report.v1`.

---

## UI integration

Executive Overview adds a minimal card:

- Reporting period, net profit, target, % achieved, required daily run rate,
  projected period-end profit, traffic light, readiness
- Link to `GET /api/financial-reporting/summary`
- Exception-isolated (EO never fails because of this card)

---

## Safety boundaries

- Read-only / advisory only
- `trading_impact=false`
- No broker credentials
- No execution side effects
- Exception-isolated statement generation
- Desktop-local untracked files not staged: `CSS_Overnight_Runtime_Review.txt`,
  `dashboard/runtime/__init__.py`

---

## Testing

`tests/test_phase177_financial_reporting.py` covers periods, income, run-rate,
balance sheet, cash flow, engine, API, and UI rendering.

---

## Known limitations

- Adapter mapping from MC portfolio is **partial** (P&L split + cash/equity);
  full BS/CF require explicit contract producers
- Not statutory / audited GAAP close
- No board-pack PDF generation (later phase)
- Does not replace journal-based `financial_statements` helpers
- Target profit rarely present in live MC state today → often NOT_AVAILABLE / AMBER

---

## Phase 178 and Executive Reporting Suite

Phase 178 should wire richer producers into `FinancialDataContract`, deepen
Executive Reporting Suite consumption, and optionally feed 176J evidence keys
(`income_statement` / `balance_sheet` / `cash_flow`) from this engine — without
duplicating run-rate or readiness logic.
