# Phase 105D: Entry Point Canonicalization Certification

## 1. Objective
Establish and certify the single authoritative CSS startup and runtime entry path across Engine, API, and Dashboard components.

## 2. Discovered Entry Points & Categorization

The following entry points were audited via global `__main__` and `uvicorn` search:

### Authoritative Production Entry Points
* **Core Trading Engine:** `run_css.py`
* **API Server:** `backend/run_api.py`
* **Live Dashboard:** `scripts/css_live_dashboard.py`

### Development & Utility Entry Points
* `run_engine_loop.py`
* `run_paper_simulation.py`
* `backend/app/simulator.py`
* `tools/*` (various utility runners)
* `scripts/css_live_monitor.py`
* `scripts/css_session_analyzer.py`

### Test Harnesses
* `test_*.py` (various test suites)
* `engine/testing/structured_test_harness.py`
* `analytics_harness.py`
* `api_server_stub.py`

### Archive / Legacy (Non-Authoritative)
* `css_live_dashboard_v5.py`
* `css-gemini/gemini-dashboard.py`
* `css-gemini/dashboard.py`
* `CSS-CLAUDE/main.py`
* `CSS-CLAUDE/dashboard.py`
* `CSS-CLAUDE/broker_bootstrap.py`
* `backend/app/run_live_guarded.py`
* `run_live_manual.py`
* `run_live_manual_mt5.py`
* `run_live_manual_mt5_v2.py`
* `run_demo_end_to_end.py`
* `run_live_guarded.py`

## 3. Duplicate Production Startup Paths
We identified historical dashboard runners (`css_live_dashboard_v5.py`, `CSS-CLAUDE/dashboard.py`, `css-gemini/dashboard.py`) competing with the canonical dashboard. Furthermore, experimental agentic engine runners (`CSS-CLAUDE/main.py`) existed alongside `run_css.py`.

## 4. Remediation Actions Taken
1. Certified `run_css.py` as the canonical production trading engine path.
2. Certified `backend/run_api.py` as the canonical API path.
3. Certified `scripts/css_live_dashboard.py` as the canonical dashboard path.
4. Added strict `SystemExit` quarantine markers with documentation linking to the canonical path in the following retired launchers:
   - `css-gemini/gemini-dashboard.py`
   - `css-gemini/dashboard.py`
   - `CSS-CLAUDE/main.py`
   - `CSS-CLAUDE/dashboard.py`
   - `run_live_manual.py`

## 5. Certification
I certify that the entry point canonicalization is complete and respects all prior trading logic, broker behaviors, and risk gates. The pytest suite remains fully stable and green.
