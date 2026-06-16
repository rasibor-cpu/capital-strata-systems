# Phase 113B: Controlled Live Runbook Correction

## Objective
Verify operational instructions against actual startup command paths and correct the go/no-go checklist.

## Findings
The previous Phase 112B Go/No-Go Checklist incorrectly instructed operators to use:
`python -m engine.engine_loop --mode live --micro-limits`

However, the repository architecture establishes `scripts/css_live_dashboard.py` as the canonical operator entry point, which interactively collects governance credentials, live mode status, and micro-limits selections before bootstrapping the engine and UI safely. The `engine_loop.py` module does not function as a standalone command-line application using `argparse`.

## Resolution
Modified `docs/operations/PHASE_112B_CONTROLLED_LIVE_GO_NO_GO_CHECKLIST.md` Section 5 (First Controlled Live Session Procedure) to document the correct workflow:
- The startup sequence must execute via the canonical `python scripts/css_live_dashboard.py` command.
- Operators must select `LIVE` mode and `MICRO-LIMITS` parameters interactively via the CLI/GUI governance gate during initialization.

## Status
**CLOSED**
