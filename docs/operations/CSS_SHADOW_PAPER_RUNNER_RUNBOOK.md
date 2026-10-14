# CSS Live-Data Shadow Paper Runner — Runbook

Status: **REVIEW CANDIDATE (draft PR). Observation only.**
`LIVE_TRADING_ALLOWED=FALSE` · `PRODUCTION_GO=NO`

## What it is

`scripts/css_shadow_paper_runner.py` feeds **real** Coinbase public BTC-USD / ETH-USD
quotes into the existing V1 price-driven `SignalEngine` and gates. It records every
decision in an append-only, hash-chained journal. Fills, positions and P&L are
**simulated**, and costs are **estimated** from the engine's existing bps settings.
It has no broker connection and no order-submission code. If a broker-capable
module is ever loaded into the process, the runner refuses to run.

Per instrument, per 5-minute bar, the runner does the following:

1. It validates the real quote. Stale (>120 s), future-dated, missing, malformed,
   crossed or implausible quotes are rejected. Prices are never substituted.
2. It runs `SignalEngine`.
3. It checks exits using the `PositionBook` rules. Exits fill at the real bid/ask
   plus the estimated slippage and fee.
4. It runs the entry gates. All must pass:
   - runner permission (reconciled, not halted)
   - signal direction
   - min signal strength 0.61
   - no pyramiding
   - RegimeGate (40 bars)
   - **R7** `CSSUnifiedTradeGate` (SAFE)
   - **R14F** (SAFE, loaded verbatim from `scripts/css_live_dashboard.py`)
   - `ExecutionGate` (**AntiBleedGuard** 25 bps / 50 minimum → MarginTradeGate →
     sizing → RiskGovernor)
   - PortfolioCapitalController
   - final notional ≥ 50
5. If every gate passes: paper order intent → `SIMULATED_FILL` → paper position.

No thresholds, limits or flags are changed. The runner verifies them at startup and
again on every cycle.

### Reviewer decisions embedded in the design

- **R7/R14F inputs are proxies.** The price-driven engine produces only a 0–1
  `strength`, while R7 and R14F expect dashboard-scale inputs.
  - The proxy uses probability := strength and R14F signal := strength × 20.
  - Both gates are **enforced**, so the proxy can only block entries, never admit one.
  - Every R7 and R14F result is journaled with `input_basis=PROXY_UNCALIBRATED`.
- **The R7 session is the runner's own operator context.** It records the
  operator id, uses role `TRADER`, and is renewed after each passing per-cycle
  safety recheck. It is not a Mission Control sign-on.
- **Margin.** `EngineLoop`'s legacy `MarginEngine` snapshot is rejected by the
  canonical `MarginTradeGate` (`MARGIN_SNAPSHOT_UNAVAILABLE`).
  - The runner therefore uses the existing `CoinbaseMarginAdapter` in SIMULATED
    mode: spot, unlevered, built from paper equity and open paper notional.
  - Consequence for V1 itself: `EngineLoop` cannot open any position on V1. That
    pre-existing defect is not changed here.
- **Costs are optimistic.** The engine's fee/slippage settings are 1 bps each.
  Real Coinbase retail fees are much higher, so treat simulated P&L as an upper
  bound.

## Stage B — Windows host: connectivity and safety validation

Run in PowerShell from the repository root. The evidence folder must be **outside**
the repository.

```powershell
cd C:\rasib\source\capital-strata-systems
git fetch origin claude/css-project-closure-jkhwyg
git checkout --detach <PR_HEAD_SHA>
git rev-parse HEAD ; git status --porcelain          # expect the SHA and an empty status
py -3.11 -m venv .venv-shadow
.venv-shadow\Scripts\python.exe -m pip install -r requirements.txt pytest

# 1. Offline tests on the host (must all pass)
$env:CSS_TEST_MODE="1"
.venv-shadow\Scripts\python.exe -m pytest -q tests\test_shadow_paper_runner.py
.venv-shadow\Scripts\python.exe -m pytest -q tests *> C:\CSS_Evidence\shadow_full_regression.txt
Remove-Item Env:CSS_TEST_MODE

# 2. Safety preflight + read-only feed probe (expect exit code 0)
$Ev = "C:\CSS_Evidence\SHADOW_" + (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
.venv-shadow\Scripts\python.exe scripts\css_shadow_paper_runner.py preflight --evidence-dir $Ev --operator-id <OPERATOR_ID>
$LASTEXITCODE    # 0 = ready; 2 = unsafe flag/control; 3 = journal integrity; 5 = feed not ready
```

Stage B passes when the following all hold:

- The tests pass.
- `preflight` exits `0` with `"passed": true`.
- Both `feed_probe` entries show `"accepted": true` with `age_seconds` < 120.
- `commit_sha` equals the PR head with no `-dirty` suffix.

Any other result: **stop** and report the output.

## Stage C — supervised 24-hour shakedown

```powershell
.venv-shadow\Scripts\python.exe scripts\css_shadow_paper_runner.py run --evidence-dir $Ev --operator-id <OPERATOR_ID>
```

- Leave the console window open. Stop with **Ctrl+C**, which journals `RUN_STOPPED`.
- Open paper positions stay open and are reconciled on the next start. A close is
  never invented.
- Perform **one controlled restart** at about 12 h. Press Ctrl+C, then rerun the
  same `run` command with the same `$Ev`.
- Do not edit, pull or switch branches during the run.
- At the end, run:

```powershell
.venv-shadow\Scripts\python.exe scripts\css_shadow_paper_runner.py verify --evidence-dir $Ev > "$Ev\VERIFY.json"
Get-FileHash "$Ev\shadow_journal.jsonl" -Algorithm SHA256
```

### Stage C acceptance criteria (all from `VERIFY.json`)

| # | Area | PASS condition |
|---|---|---|
| C1 | Journal integrity | `journal_integrity == "PASS"` |
| C2 | Feed freshness/continuity | `feed.acceptance_rate >= 0.99`; every `max_gap_seconds_by_instrument <= 900`; `max_accepted_quote_age_seconds <= 120` |
| C3 | Trade-gate enforcement | `gates.decisions_on_stale_or_unknown_price == 0`; `opens_without_full_gate_pass == []`; `opens_below_anti_bleed_minimum == []` |
| C4 | Position/limit compliance | Every open passed `portfolio_capital_controller` and R7 position limits (C3); at most 1 concurrent crypto position at 1,000 equity (10% class cap) |
| C5 | Paper-order lifecycle | `lifecycle.orphan_closes == []`, `duplicate_closes == []`, `arithmetic_errors == []`, `closes_without_real_tick == []` |
| C6 | Ledger and restart | `ledger.reconciliation_difference <= 0.01`; `ledger.restarts >= 1`; `ledger.reconciliations_completed == ledger.starts_passing_preflight` (preflight-only starts are not counted as restarts) |
| C7 | Safety | `safety.safety_halts == 0`, `safety.errors == 0`, `safety.entries_halted_events == 0`; no `SAFETY_PREFLIGHT_FAILED` after the first `RUN_STARTED` of the run |
| C8 | Stability | `stability.span_seconds >= 86400` and `stability.cycle_coverage >= 0.98` |

These are **not** acceptance criteria: number of trades, win rate, or P&L. Zero
trades in 24 h is a valid outcome. Simulated P&L is never evidence of live
profitability.

## Stage D — 7-day observation

Start Stage D only after Stage C has been accepted in writing. Use the same
commands and the same criteria, with C8 changed to `span_seconds >= 604800`. Use
a new evidence folder.

## Out of scope

This runbook does not cover broker execution, live orders, flag changes, merges or
production deployment.
