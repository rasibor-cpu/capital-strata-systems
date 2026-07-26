# CSS OV-002 Attempt 2 — Pre-Run Readiness

**Programme:** Release Gate 3 — Operational Validation OV-002
**Attempt identifier:** `OV-002 ATTEMPT 2`
**Decision:** `READY FOR ENDURANCE`
**Recorded (UTC):** 2026-07-23T06:22:00Z
**Elapsed carry-forward from Attempt 1:** **None** (starts at zero)

---

## Result

# READY FOR ENDURANCE

---

## Identity and synchronization

| Field | Value |
| --- | --- |
| Branch | `css-unified-consolidation-2026-07-13` |
| Commit SHA (freeze) | `0ff97cba114c051b640eeabe2edacdecc5c02053` |
| Remote HEAD | `0ff97cba114c051b640eeabe2edacdecc5c02053` |
| Ahead/behind | `0 0` |
| Tracked working-tree modifications | **None** (untracked local diagnostics / Attempt 2 docs only) |
| Machine | `FINANCE` |
| Windows boot time | `2026-07-15T02:32:17.5000000-04:00` |
| Python | `3.12.9` (`.venv`) |
| Disk free (C:) | ~342.12 GB |

---

## CSS controlled restart

| Field | Value |
| --- | --- |
| Prior CSS tree | Identified and stopped (cmd `22760` / runtime launcher tree on `:8765`) |
| Launcher | `launch_css.bat` |
| CSS startup (UTC) | `2026-07-23T06:18:14Z` (supervisor `started_at`) |
| Health first OK (UTC) | `2026-07-23T06:18:16.582403Z` |
| Backend `/health` | **200** `healthy` / `css_mobile_launcher` |
| Mobile Dashboard `/mobile` | **200** |
| Mission Control `/mission-control` | **200** |
| Supervisor | **RUNNING** (`runtime/supervisor/css_runtime_supervisor_state.json`) |
| Heartbeat | Present and advancing (`last_heartbeat_at` updating) |
| Initial display/session cycle | **635** (`/api/runtime-telemetry`) |
| Runtime mode reason | `incomplete_startup_information` / fail-closed empty context (advisory) |

### Active processes (post-restart)

| PID | Role |
| --- | --- |
| 27400 | `cmd.exe` / `launch_css.bat` |
| 24776 | `.venv` `launcher.css_runtime_launcher` |
| 15744 | nested `css_runtime_launcher` |
| 24144 / 19312 | `css_live_dashboard` |
| 22168 / 26152 | `css_mobile_launcher` (`:8765`) |

---

## Safety assertions

| Assertion | Result |
| --- | --- |
| `execution_allowed=false` | **PASS** |
| `can_live_execute=false` | **PASS** |
| `live_trading_blocked=true` | **PASS** |
| Broker execution armed | **false** |
| Advisory / read-only posture | **PASS** (`runtime_mode=DISABLED`, `advisory_only=true`, `fail_closed=true`) |
| Order submission | **BLOCKED** |
| Live trading enabled | **false** |
| Phase 181 | **`NOT_CERTIFIED`** |
| Monitor `capture_safety_assertions().ok` | **true** |

Live authority: `BLOCKED` — reason `Credentials Invalid`.

---

## Broker truthfulness

| Broker | Observed |
| --- | --- |
| Coinbase | Credentials missing / Auth Status FAIL / Operational DEGRADED / Validation **FAIL_CLOSED**; account authentication **not** claimed |
| OANDA | Validation **FAIL_CLOSED**; Authentication **False**; read-only / pending-account labels present; **not** presented as LIVE-certified |
| Broker health GREEN while fail-closed | **Not observed** for Coinbase/OANDA (GREEN badges elsewhere are non-broker portfolio widgets) |

OV-001 residuals remain: Coinbase account auth not claimed; OANDA practice/read-only non-LIVE.

---

## Attempt 1 preservation

| Check | Status |
| --- | --- |
| Evidence dir `ov002_72h_20260722T043023Z/` | **Preserved** (not reused) |
| Incident report committed | Present |
| Disposition | `ENDURANCE INVALIDATED` |
| AR-014 | PARTIALLY CLOSED |
| RB-012 | PARTIALLY CLOSED |
| Phase 181 | NOT_CERTIFIED |

---

## Evidence directory (Attempt 2)

Authoritative package (created at monitor start):

`runtime_reports/operational_validation/ov002_attempt2_20260723T062224Z/`

Run ID: `OV002-20260723T062225Z`

(Pending placeholder `ov002_attempt2_pending_20260723T055046Z/` is **not** authoritative.)

---

## Known residuals

- Coinbase account authentication residual (OV-001)
- OANDA not LIVE-certified (practice/read-only residual)
- `operator_requested_live=true` in authority payload while execution remains blocked
- Selected broker mode may display `live` while execution authority remains BLOCKED
- Untracked local pytest/diagnostic text files (excluded from freeze)

---

## Invalidating conditions (monitor fail-closed)

- Active commit change
- Tracked code/config change
- Host reboot
- Unexpected CSS restart
- Evidence capture gap
- Live execution enabled / broker write attempted
- Safety assertion regression
- Secrets in evidence
- Runtime unavailable without permitted recovery

---

## Final readiness decision

# READY FOR ENDURANCE

---

*End of CSS_OV002_ATTEMPT2_PRE_RUN_READINESS.md*
