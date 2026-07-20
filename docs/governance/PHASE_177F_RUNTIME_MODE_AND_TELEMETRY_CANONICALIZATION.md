# PHASE 177F — Runtime Mode & Telemetry Canonicalization

**Status:** Activated on `:8090` and `:8765` (Phase 177G). Source commit authorized.
**Date:** 2026-07-20
**Baseline:** `5ff64f0356505e2cb8f12088f741abed892fb57f`
**Branch:** `css-unified-consolidation-2026-07-13`

---

## Prior inconsistencies

| Symptom | Root cause |
|---------|------------|
| Mobile `system_mode=LIVE_READ_ONLY` vs resolver `DISABLED` | `load_mobile_controls()` mapped `MOBILE_READ_ONLY` → platform-looking `LIVE_READ_ONLY` and `/api/status` published it as `system_mode` |
| Mobile/MC cycle `0` vs supervisor `~18254` | UI bound session/snapshot `cycle_number` with silent default `0`; engine loop counter lives in `runtime_supervisor.json` as `cycles_completed` and was not wired |
| Restart `~1657` labelled ambiguously | `CSSRuntimeSupervisor.restart_count` = managed child auto-restarts within the supervisor process — not host reboots |

---

## Canonical concepts

| Concept | Authority | Examples |
|---------|-----------|----------|
| Runtime mode | Runtime Mode Resolver | PAPER, LIVE_READ_ONLY, LIVE_MICRO_PILOT, LIVE, DISABLED |
| Engine mode | Session / mobile controls | SAFE, CONSERVATIVE, BALANCED, AGGRESSIVE, EXPANSION |
| Broker mode | Broker registry / startup | NONE, PRACTICE, SANDBOX, LIVE |
| Mobile access mode | Mobile controls only | READ_ONLY, OPERATOR |
| Execution state | Derived from resolver | BLOCKED (current), SIMULATED, ADVISORY_ONLY, ENABLED (future) |

`MOBILE_READ_ONLY` remains a control-plane value only. It is never published as canonical runtime mode.

---

## Authority hierarchy (telemetry)

1. `runtime_supervisor.json` — engine loop cycles, uptime, disconnects, errors, recoveries
2. `runtime/supervisor/css_runtime_supervisor_state.json` — managed_service_restart_count, failure_count, heartbeat
3. Session artifacts — `session_cycle`
4. Runtime Mode Resolver — runtime_mode / execution projection
5. Accounting stores — financial metrics (untouched this phase)

Missing counters → `UNKNOWN` / `NOT_REPORTED` / `UNAVAILABLE` — **never** silent numeric zero.

Primary displayed cycle field: `display_cycle` (= `session_cycle` when present, else UNKNOWN).

---

## Modules

| Module | Role |
|--------|------|
| `backend/runtime/platform_status.py` | Multi-concept status builder |
| `backend/runtime/runtime_telemetry.py` | Canonical telemetry service |
| `dashboard/runtime/api/runtime_telemetry.py` | Read-only APIs |
| `backend/options/options_income_surface_link.py` | OI detail URL helper |

API routes: `GET /api/runtime-telemetry`, `/status`, `/provenance` (mounted on launcher and mobile_app).

---

## Compatibility aliases

| Alias | Canonical | Notes |
|-------|-----------|-------|
| `system_mode` | `runtime_mode` | Deprecated; must equal resolver mode |
| `cycle` | `display_cycle` | Deprecated; may be UNKNOWN |
| `restart_count` | `managed_service_restart_count` | Deprecated; definition clarified |
| `cycles_completed` | `supervisor_cycles_completed` | Deprecated |

---

## Options Income linkage

`:8090` does not remount full OI APIs. It exposes a summary card + deep link via `options_income_detail_link()` (`CSS_MISSION_CONTROL_BASE_URL` / `CSS_LAUNCHER_PUBLIC_URL` optional). `same_origin_api_expected=false`.

---

## Safety

- Resolver unchanged (fail-closed DISABLED)
- Broker registry unchanged (no IBKR)
- Execution remains blocked
- Accounting calculations untouched

---

## Activation

Phase 177G performed controlled restarts of `:8090` and `:8765` only. Runtime launcher and live dashboard were not restarted.
