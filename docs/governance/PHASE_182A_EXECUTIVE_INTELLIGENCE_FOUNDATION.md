# Phase 182A — Executive Intelligence Suite Foundation

## Scope

Phase 182A establishes the read-only Capital Strata Systems Executive
Intelligence Suite (EIS) and the canonical Enterprise PDF subsystem. It does
not add a trading dashboard, execution capability, broker access, runtime
mutation, authentication change, RBAC change, readiness change, or service
restart.

Baseline:

- Branch: `css-unified-consolidation-2026-07-13`
- HEAD: `4ea738d86c167373deccbe4edf217e929de4414d`
- Release baseline: RC1.1 Certified
- Phase 181A worktree changes were preserved and not staged.

## Architecture

The suite uses one-way, read-only flow:

```text
Canonical runtime snapshot or injected evidence
  -> ExecutiveMetricEngine
  -> Financial statements / scorecard / run-rate / risk / commentary
  -> ExecutiveIntelligenceService package
  -> ExecutiveReport canonical model
  -> PDF (canonical)
  -> Print Preview / HTML / API derived views
```

All EIS responses carry immutable safety declarations:

- `read_only=true`
- `advisory_only=true`
- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`
- `runtime_mutation_allowed=false`
- `broker_access_attempted=false`

## Executive Intelligence Layer

`backend/executive` contains pure models and calculation services:

- `executive_models.py`: canonical serializable contracts.
- `executive_metrics.py`: single EIS metric calculation pass.
- `executive_kpis.py`: KPI projection without recalculation.
- `executive_income_statement.py`: income statement.
- `executive_balance_sheet.py`: balance sheet and balance validation.
- `executive_cashflow.py`: cash-flow statement and reconciliation.
- `executive_scorecard.py`: weighted Executive Score.
- `executive_run_rate.py`: profitability target monitor.
- `business_calendar.py`: weekends, market holidays, and exchange extension.
- `executive_commentary.py`: deterministic non-LLM narrative rules.
- `executive_capital.py`, `executive_risk.py`, `executive_forecast.py`, and
  `executive_alerts.py`: derived read-only projections.
- `executive_service.py`: one-snapshot orchestration.
- `executive_api.py`: GET-only API.
- `executive_rendering.py`: derived HTML, print-preview, API, and canonical PDF
  outputs from `ExecutiveReport`.

The package does not import broker adapters or execution services.

## Canonical Metric Engine

`ExecutiveMetricEngine` computes the complete EIS metric map once. Consumers
receive immutable `MetricValue` objects and do not repeat formulas.

The foundation includes:

- gross, operating, and net profit;
- daily, weekly, monthly, quarterly, annual, YTD, and MTD return;
- NAV, available cash, buying power, equity, and exposure;
- capital utilization and capital efficiency;
- liquidity, cash, and leverage ratios;
- win rate, profit factor, and expectancy;
- Sharpe and Sortino ratios;
- current and maximum drawdown;
- annualized volatility;
- realized and unrealized PnL;
- broker, strategy, and asset allocation validation.

The engine operates on a copied mapping and never mutates source evidence.
Legacy Financial Reporting remains available as an upstream evidence source;
future convergence should adapt it into the EIS snapshot rather than
recalculate metrics in presentation code.

## Executive Score

The weighted score uses ten categories:

- Financial Health: 16%
- Risk Health: 14%
- Execution Quality: 10%
- Capital Efficiency: 10%
- Operational Health: 10%
- Compliance: 10%
- Readiness: 8%
- Infrastructure: 7%
- Broker Health: 8%
- Data Freshness: 7%

Weights total 100%. Scores at or above 75 are GREEN, scores from 50 through
74.99 are AMBER, and scores below 50 are RED.

## Business Calendar

The canonical calendar supports:

- configurable weekend days;
- explicit additional holidays;
- observed holidays;
- NYSE/NASDAQ United States market holidays;
- Good Friday;
- business-day ranges;
- next-business-day calculation;
- exchange name as an extension boundary.

Future exchange implementations can supply a holiday set without changing the
run-rate engine.

## Run Rate Definitions

Inputs:

- annual, quarterly, and monthly targets;
- current profit;
- current date;
- configured trading-day count;
- canonical business calendar.

Outputs:

- remaining required daily, weekly, and monthly profit;
- observed profit per elapsed trading day;
- plan variance through the current date;
- projected year-end profit;
- deterministic probability of meeting target;
- GREEN, AMBER, or RED status;
- deterministic executive commentary.

No statistical claim is made beyond the documented deterministic trajectory
method.

## Executive API

The canonical launcher registers exactly these GET-only routes:

- `/executive/summary`
- `/executive/kpis`
- `/executive/scorecard`
- `/executive/income`
- `/executive/balance-sheet`
- `/executive/cashflow`
- `/executive/run-rate`
- `/executive/risk`
- `/executive/commentary`

The provider is `runtime_snapshot_state_provider()`, which reads the canonical
runtime snapshot contract. The router has no POST, PUT, PATCH, or DELETE
operation and introduces no authentication or RBAC behavior.

Missing evidence returns a degraded, execution-blocked response without raw
exception details.

## PDF Architecture

`backend/reporting/pdf` is the sole PDF renderer:

- `pdf_renderer.py`: canonical renderer and two-pass page-count build.
- `pdf_layout_engine.py`: A4/A3 configuration and automatic orientation.
- `pdf_page_templates.py`: document metadata and bookmarks.
- `pdf_header.py`: branded header.
- `pdf_footer.py`: Page X of Y, copyright, classification, versions, and
  timestamp.
- `pdf_watermark.py`: every-page Branding Service watermark.
- `pdf_tables.py`: wrapped cells, repeated headers, row splitting.
- `pdf_charts.py`: vector chart primitives.
- `pdf_styles.py`: embedded font registration and typography.
- `pdf_assets.py`: Branding Service-only asset resolution.
- `pdf_export_service.py`: in-memory export without filesystem or delivery
  mutation.
- `pdf_legacy_adapter.py`: compatibility bridge for pre-182A text reports.

The previous handwritten US Letter PDF writer was removed. Existing Daily
Executive Brief and Reports Center paths now delegate through the canonical
renderer by way of `build_text_pdf`.

ReportLab 5.0.0 is pinned in both dependency manifests.

## Rendering Pipeline

Rendering priority and ownership:

1. PDF — canonical `EnterprisePDFRenderer`.
2. Print Preview — derived from `ExecutiveReport`.
3. HTML Viewer — derived from `ExecutiveReport`.
4. Executive Dashboard — future projection of the same model.
5. Excel — future model adapter.
6. PowerPoint — future model adapter.
7. Email — future delivery adapter.
8. JSON/API — `ExecutiveReport.as_dict()` or EIS package projection.

Calculations occur before rendering. Renderers never call brokers, alter
runtime state, or calculate financial KPIs.

## ISO Paper Standard

Default:

- ISO A4 portrait;
- 210 mm × 297 mm;
- 42-point side margins;
- reserved header and footer bands.

Automatic landscape:

- tables with more than seven columns; or
- aggregate column-header width greater than the configured threshold.

Future A3 is configuration-backed. US Letter is not a default or fallback.

## Header, Footer, and Watermark Standard

Every canonical PDF page contains:

- Branding Service logo;
- Capital Strata Systems;
- report title and subtitle;
- classification;
- report ID and UUID;
- runtime and document versions;
- generation timestamp and reporting period;
- Page X of Y;
- copyright and confidentiality banner;
- centered proportional Branding Service watermark.

No PDF source embeds an `assets/branding` path. Assets are resolved only by
`CSSBrandService`.

## Typography and PDF Quality

- ReportLab Vera TrueType fonts are embedded.
- Text is searchable and selectable.
- Section headings produce outline bookmarks.
- Score charts are vector drawings.
- Tables wrap, split across pages, and repeat headers.
- Metadata includes title, author, subject, creator, keywords, report ID, and
  UUID.
- PDF export remains compatible with future digital-signature processing.

The available CSS logo is currently a Branding Service raster asset. The
renderer preserves aspect ratio. A future vector branding asset can replace it
through the Branding Service without changing PDF code.

## Performance

Controlled in-memory smoke evidence:

- 3-page A4 Executive Summary;
- approximately 404 KB;
- approximately 1.2 seconds including first font/image initialization;
- no filesystem write;
- no network call;
- no broker access;
- no runtime access.

The renderer uses a two-pass build to guarantee correct `Page X of Y`. Asset
and font reuse are delegated to ReportLab.

## Testing

Phase 182A focused coverage includes:

- metric formulas and source immutability;
- income statement;
- balanced balance sheet;
- reconciled cash flow;
- business-day and holiday behavior;
- run-rate calculation;
- scorecard weights and status;
- deterministic commentary;
- serialization;
- GET-only API responses;
- no runtime mutation;
- no broker imports;
- A4 portrait geometry;
- automatic A4 landscape;
- embedded fonts;
- metadata;
- outline bookmarks;
- every-page header, footer, and watermark;
- long-table pagination;
- large and empty reports;
- derived HTML and print preview.

Focused result: 12 passed.

Compatibility and report regressions:

- Phase 182A + Phase 180B + Phase 176G + Phase 175: 59 passed.
- Launcher and runtime launcher regression: 74 passed.

## Future Extension Points

- Canonical adapters from Phase 177 Financial Reporting contracts.
- Exchange-specific calendar providers.
- A3 and other ISO page profiles.
- Vector logo asset supplied by Branding Service.
- Excel and PowerPoint model adapters.
- Board-pack composition and report registry integration.
- Investor and regulatory schemas.
- Digital signing and signature validation.
- AI Executive Assistant consuming serialized EIS models only.

## Certification

Phase 182A is certified as a read-only foundation:

- no broker access;
- no execution path;
- no runtime mutation;
- no authentication or RBAC change;
- no readiness or execution-gate change;
- no live trading enablement;
- no service restart;
- no staging, commit, or push.

Deployment remains subject to final compile, regression, dependency, and Git
review and to disposition of pre-existing worktree certification blockers.
