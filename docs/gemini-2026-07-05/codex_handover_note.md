# CSS Institutional Architecture - Codex Handover Note

**Date:** May 8, 2026
**Project:** Capital Strata Systems (CSS)
**Governance Protocol:** PCNRASS (Please Confirm No Regression And Stable State)

---

## Hello Codex
You are taking over the ongoing institutional hardening of the Capital Strata Systems (CSS) codebase. The foundation has been significantly fortified to support institutional-grade operations, strict payload freezing, and regression-free sprints. 

This document outlines the current architectural state, boundaries you must respect, and the tooling available to you.

## 1. Current Codebase State
Google Gemini (Antigravity) has just completed **Phase 1-6** and **UI-INFRA-2** of the CSS institutional audit.

**Recently Completed Features:**
*   **Web Broker Control Center:** A read-only dashboard surface displaying API health, reconnect state, supported assets, and account readiness. It safely handles missing credentials using boolean flags (`broker.missing_credentials`) without exposing actual secrets.
*   **Frontend Payload Contract Freezing (`css.frontend.contract.v1`):** 
    *   The canonical `DashboardState.to_dict()` has been locked down and versioned.
    *   Websocket communications (`ws_bridge.py`) now yield explicit, typed events (`pnl_update`, `risk_update`, etc.) rather than a monolithic `dashboard_delta`.
*   **Engine Refactoring:** Consolidated utilities into `_utils.py` and successfully wired `ExecutionCostEngine` into the `PnLEngine`.

## 2. Hard Architectural Boundaries (Do Not Break)
When continuing assignments, you must strictly adhere to these rules:
*   **Canonical Authority:** `DashboardState` is the single source of truth for the frontend.
*   **No Direct Broker Calls:** The frontend/UI must *never* make direct broker calls. It only consumes the `DashboardState` payload.
*   **Credential Redaction:** The serialization layer intercepts sensitive keys (e.g., `api_key`, `secret`) and replaces them with `"REDACTED"`. Never expose credentials in logs or payloads.
*   **Paper-First Safety:** The `resolved_mode()` logic mandates that live trading is only possible if both the session and the broker explicitly agree on `"live"`. Otherwise, it falls back to `"paper"`.
*   **Decimal Safety:** All `Decimal` objects from the backend ledger must be converted to `float` or strings before leaving the runtime.

## 3. Available Validation Tooling
You have access to institutional-grade validation tools to prevent schema drift:
*   **`dashboard/runtime/payload_validator.py`**: Use `FrontendPayloadValidator.validate()` to ensure any payload modifications conform to the strict v1 schema.
*   **`dashboard/runtime/payload_diff_tool.py`**: Use `PayloadDiffTool.compare_payloads(prev, current)` to detect missing keys or unexpected type changes.

## 4. Required PCNRASS Workflow
Before making any atomic `git commit`, you must guarantee zero regressions by running the following validations from the `.venv`:
1.  **Unit Tests:** `python -m pytest tests/engine/ tests/dashboard/`
2.  **Runtime Smoke Test:** `python dashboard/runtime/runtime_smoke_test.py`
3.  **Web Smoke Test:** `python dashboard/web/web_smoke_test.py`
4.  **Sprint Protections:** `python dashboard/auth/css_sign_on_smoke_test.py` and `python dashboard/mobile/mobile_smoke_test.py`

*Current status: All tests are passing cleanly on the `main` branch.*

**Good luck with the rest of the assignments! Maintain the institutional standard.**
