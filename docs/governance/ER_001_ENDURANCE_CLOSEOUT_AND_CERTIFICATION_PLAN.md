# ER-001 — Endurance Closeout and Certification Plan

**Programme:** CSS Endurance Programme
**Phase:** ER-001 (offline governance only)
**Branch:** `css-unified-consolidation-2026-07-13`
**HEAD (plan authoring):** `66e11d4f83600a7765b4e55afa33d19e301dd70e`
**Upstream parity at authoring:** `0 0`
**Status:** PLAN COMPLETE — **NO SHUTDOWN EXECUTED**
**Companion template:** `docs/governance/ER_001_ENDURANCE_CERTIFICATION_TEMPLATE.md`

**Related:** LDT-002 endurance-credit rule (observational ≠ OV-002 auto-credit); OV-002 plan/report precedents; prior controlled shutdown report pattern (`CSS_OV002_CONTROLLED_SHUTDOWN_REPORT.txt`).

---

## 1. Purpose and non-actions

Define the complete closeout, evidence, shutdown, verification, and certification framework for the **currently running untimed CSS endurance/desktop instance** (and reusable for future timed runs).

**ER-001 does not:**

- Stop, restart, or synchronize the running CSS runtime
- Modify runtime-loaded code
- Contact brokers or authenticate
- Commit, push, or merge
- Award OV-002 certification by default (see §3 and LDT-002)

---

## 2. Workspace verification (frozen at authoring)

| Field | Required | Observed |
| --- | --- | --- |
| Repository | `C:\rasib\source\capital-strata-systems` | Match |
| Branch | `css-unified-consolidation-2026-07-13` | Match |
| HEAD | `66e11d4f83600a7765b4e55afa33d19e301dd70e` | Match |
| Upstream parity | `0 0` | Match |

Re-verify immediately before any future closeout execution.

---

## 3. Certification classes and credit types

| Credit type | Meaning | When allowed |
| --- | --- | --- |
| **OBSERVATIONAL_STABILITY** | Narrative + hashed evidence of continuous operation | Allowed if closeout evidence complete and criteria §4 met for observation |
| **FORMAL_48H_STABILITY** | Sealed 48h contract with checkpoints/manifest | Only if a declared 48h monitor/manifest/checkpoint set exists for **this** supervisor generation |
| **OV-002_CERTIFICATION** | Release-gate 72h endurance credit | Only if OV-002 (or successor) monitor, `RUN_META`, checkpoints, and executive acceptance exist for **this** run — **not** automatic for the current untimed instance |

**Decision vocabulary for each criterion and overall:**

- `PASS` — objective evidence meets the criterion
- `FAIL` — objective evidence violates the criterion
- `BLOCKED` — criterion cannot be evaluated, evidence missing/corrupt, or credit type not applicable

**Overall rules:**

1. Any mandatory criterion `FAIL` ⇒ overall `FAIL` for that credit type.
2. Any mandatory criterion `BLOCKED` ⇒ overall `BLOCKED` (cannot certify).
3. OV-002 Attempt 2 historical package remains separately dispositioned (residuals / invalidated for certification credit per prior reports) and must not be conflated with the current supervisor generation.

---

## 4. Endurance closeout checklist

Execute **in order** during a future authorized closeout. Mark each row PASS/FAIL/BLOCKED with UTC timestamp and operator initials.

### 4.1 Pre-closeout repository lock

| # | Check | Method (future) | Classification keys |
| --- | --- | --- | --- |
| R1 | Branch matches freeze expectation | `git branch --show-current` | PASS/FAIL |
| R2 | HEAD recorded | `git rev-parse HEAD` | PASS/FAIL |
| R3 | Upstream parity recorded | `git rev-list --left-right --count HEAD...@{upstream}` | PASS/FAIL/BLOCKED |
| R4 | Tracked tree clean or deviations inventoried | `git status --short` | PASS/FAIL |
| R5 | Untracked runtime evidence listed (not deleted) | inventory only | PASS/BLOCKED |

### 4.2 Final live capture (read-only; before stop)

| # | Item | Source (canonical) | Notes |
| --- | --- | --- | --- |
| C1 | Final uptime | Supervisor `started_at` → now; process CreationDate | Record hours + HMS local/UTC |
| C2 | Heartbeat verification | `runtime/supervisor/css_runtime_supervisor_state.json` `last_heartbeat_at`; HTTP `/health` | Age threshold: recommend ≤ 30s FRESH |
| C3 | Restart count | Supervisor `restart_count` / `restart_attempt_count` | Unexpected vs documented |
| C4 | Failure count | Supervisor `failure_count`; failure history JSONL | This supervisor_id only |
| C5 | Supervisor status | `status`, `shutdown_requested`, `supervisor_id` | Expect RUNNING pre-stop |
| C6 | Runtime health | `GET /api/runtime-health` (and `/health`) | Record AMBER/RED reasons without “fixing” mid-closeout |
| C7 | Mission Control status | `GET /mission-control/api/runtime` (or MC health) | Record schema + runtime_status |
| C8 | Broker status | MC broker block / readiness projection | Paper/fail-closed expected; no auth |
| C9 | Portfolio state | `/api/runtime-portfolio-state` or lifecycle | Equity, cash, exposure |
| C10 | Open positions | Same + options-income positions | Must be recorded (often 0 for paper idle) |
| C11 | Realized PnL | Portfolio / trade-summary | Record value + currency context |
| C12 | Alerts | MC `alerts`, options-income alerts, audit WARN/CRITICAL since start | List critical separately |
| C13 | Runtime artifacts | `runtime/supervisor/*`, `runtime_supervisor.json`, audit logs | Copy or hash in place |
| C14 | Logs | Launcher/dashboard/mobile logs if present; audit JSONL tails | Redact secrets |
| C15 | Evidence hashing | SHA-256 of every archived file | Deterministic manifest |
| C16 | Process/port inventory | PIDs, PPID, cmdline, ports 8765/8000/8090 as applicable | Match prior OV shutdown pattern |

### 4.3 Final shutdown sequence

See §6. Checklist items:

| # | Item |
| --- | --- |
| S1 | Founder/owner authorization recorded |
| S2 | Pre-shutdown snapshot set sealed (hashes) |
| S3 | Graceful supervisor stop executed |
| S4 | Children exited |
| S5 | Ports released |
| S6 | No orphan CSS python processes |
| S7 | Post-shutdown supervisor state consistent (`STOPPED` / stopped_at set if applicable) |
| S8 | Final evidence + `MANIFEST.json` written |
| S9 | Corruption checks PASS |
| S10 | Post-shutdown verification §7 PASS |

---

## 5. Objective PASS/FAIL/BLOCKED criteria

### 5.1 Mandatory for OBSERVATIONAL_STABILITY

| ID | Criterion | PASS | FAIL | BLOCKED |
| --- | --- | --- | --- | --- |
| OS-01 | Unexpected restarts (this supervisor_id) | `restart_count == 0` **or** all restarts pre-documented in closeout notes | Undocumented restart > 0 | Supervisor state missing/unreadable |
| OS-02 | Crash / unexpected failure | `failure_count == 0` for this generation **or** failures documented as non-crash recoveries with evidence | Undocumented crash / restart_limit_exhausted without incident package | Failure history unreadable |
| OS-03 | Heartbeat healthy at final capture | Age ≤ agreed threshold; `/health` healthy | Stale heartbeat or unhealthy | Endpoints unreachable without documented reason |
| OS-04 | No orphan CSS processes post-shutdown | Zero matching launcher/dashboard/mobile python after stop | Orphans remain | Process inventory incomplete |
| OS-05 | Ports released | 8765 (and declared CSS ports) not LISTENING by CSS PIDs | Still held | Port scan failed |
| OS-06 | Evidence integrity | All mandatory artifacts present; SHA-256 match manifest; no secret markers | Missing/corrupt/hash mismatch | Manifest incomplete |
| OS-07 | Deterministic reports | Closeout report + template fields filled; timestamps UTC | Contradictory stats | Template not produced |
| OS-08 | Live authority remained blocked | `live_authority_state=BLOCKED` / execution not armed | Live execution occurred | Authority snapshot missing |
| OS-09 | Repository freeze recorded | Branch/HEAD/parity captured pre/post | Undocumented HEAD drift during closeout | Git unavailable |

### 5.2 Additional for FORMAL_48H_STABILITY

| ID | Criterion | PASS | FAIL | BLOCKED |
| --- | --- | --- | --- | --- |
| H48-01 | Declared 48h contract exists for this run | `target_hours>=48` + monitor/manifest | Contract absent but credit claimed | N/A if not claiming 48h |
| H48-02 | Wall-clock elapsed ≥ 48.0h | Proven from sealed start→end | < 48h | Clocks inconsistent |
| H48-03 | Checkpoint set complete | Required T+ checkpoints present | Gaps beyond tolerance | Checkpoints missing |

### 5.3 Additional for OV-002_CERTIFICATION

| ID | Criterion | PASS | FAIL | BLOCKED |
| --- | --- | --- | --- | --- |
| OV-01 | OV-002 monitor ran for this generation | Process + `RUN_META` match supervisor window | No monitor / wrong run_id | Evidence ambiguous |
| OV-02 | `RUN_STATUS` eligible | `COMPLETE` without invalidating residuals per executive rule | `INVALIDATED` or residuals rejected | Status missing |
| OV-03 | Snapshot/checkpoint completeness | Per OV-002 plan | Monitoring gaps | Package incomplete |
| OV-04 | Phase 181 / executive acceptance | Explicit accept | Reject / residuals | Not assessed |

**Default for current untimed instance:** claim at most **OBSERVATIONAL_STABILITY**; classify OV-002 and formal 48h as **BLOCKED** unless a sealed contract is proven.

---

## 6. Evidence package specification

**Custody root (future closeout):**

`runtime_reports/operational_validation/er001_<UTC_START>_closeout/`

**Run ID:** `ER001-<YYYYMMDDTHHMMSSZ>-<supervisor_id_short>`

**Hash:** SHA-256 per file; sorted `MANIFEST.json`
**Redaction:** credentials, PEM, tokens forbidden in archive
**Git:** local custody by default; do not commit secrets

### Categories and required artifacts

| Category | Artifacts |
| --- | --- |
| **Supervisor** | `css_runtime_supervisor_state.json` copy; failure history JSONL excerpt (this `supervisor_id`); process tree pre/post |
| **Mission Control** | `/mission-control/api/runtime` JSON; MC health JSON if available |
| **Portfolio** | runtime-portfolio-state; lifecycle; trade-summary; open positions export |
| **Runtime** | `/health`; `/api/runtime-health`; `/api/runtime-mode`; `runtime_supervisor.json` |
| **Alerts** | Active alerts dump; audit WARN/CRITICAL since `started_at` |
| **Logs** | Tails of relevant logs (redacted); note absent logs as BLOCKED item |
| **Trade DNA** | Present only if DIP-003+ deployed on this SHA — else mark `NOT_APPLICABLE` |
| **Decision Intelligence** | Present only if DIP packages on freeze — else `NOT_APPLICABLE` |
| **Broker diagnostics** | Redacted readiness/authority snapshots; no live auth |
| **Runtime reports** | Any OV/ER packages for this generation; do not overwrite OV-002 historical dirs |
| **Validation summaries** | long-duration-validation excerpt; paper-validation-summary if used |
| **Recovery snapshots** | Optional; if taken, hash and list |
| **Hashes** | Per-file SHA-256 list |
| **Manifest** | `MANIFEST.json` with run_id, commit, branch, credit_type_claimed, disposition |

### Manifest minimum fields

```json
{
  "schema_version": "css.er001.closeout_manifest.v1",
  "run_id": "ER001-...",
  "credit_type_claimed": "OBSERVATIONAL_STABILITY",
  "commit_sha": "...",
  "branch": "css-unified-consolidation-2026-07-13",
  "supervisor_id": "...",
  "started_at_utc": "...",
  "capture_at_utc": "...",
  "shutdown_at_utc": "...",
  "overall_disposition": "PASS|FAIL|BLOCKED",
  "artifacts": [{"id": "...", "path": "...", "sha256": "...", "bytes": 0}],
  "secrets_present": false
}
```

---

## 7. Controlled shutdown procedure

**Authorization required** before any step.
**ER-001 does not execute these commands.** Future operators only.

All actionable lines are placeholders:

`FUTURE_EXECUTION_COMMAND — DO NOT RUN`

### Phase A — Seal evidence (runtime still up)

1. Re-verify workspace (§2).
2. Capture C1–C16 into the custody directory.
3. Compute SHA-256 for every file; write draft manifest.
4. Record founder authorization string and UTC time.

### Phase B — Graceful stop

5. `FUTURE_EXECUTION_COMMAND — DO NOT RUN` — Request graceful shutdown via the **approved** CSS supervisor/launcher stop path (same family as historical controlled shutdown: stop launcher tree rooted at `launch_css.bat` / `css_runtime_launcher`, not random python kills).
6. Wait bounded time for children to exit (dashboard, mobile).
7. `FUTURE_EXECUTION_COMMAND — DO NOT RUN` — If graceful path incomplete after timeout, use **documented PID tree stop** (PPID-ordered) excluding unrelated processes (e.g. Notepad).
8. Confirm supervisor state shows stop / no longer RUNNING.

### Phase C — Confirm teardown

9. Verify no CSS `python.exe` with cmdlines matching `css_runtime_launcher`, `css_mobile_launcher`, `css_live_dashboard`.
10. Verify ports **8765** (and any declared 8000/8090 CSS listeners) released.
11. Confirm no orphan venv wrappers left for those roles.

### Phase D — Persist final evidence

12. Write `SHUTDOWN_OBSERVATION.json` (start/end UTC, PIDs stopped, ports, result).
13. Finalize `MANIFEST.json` hashes including shutdown observation.
14. Corruption check: re-hash all files; compare to manifest.
15. Fill `ER_001_ENDURANCE_CERTIFICATION_TEMPLATE.md` instance under custody (or dated copy).

### Hard rules

- Do **not** delete historical OV-002 evidence directories.
- Do **not** authenticate to brokers during closeout.
- Do **not** clear kill switch or arm live.
- Do **not** commit secrets.

---

## 8. Post-shutdown verification

| # | Check | PASS condition |
| --- | --- | --- |
| P1 | Repository unchanged vs pre-closeout plan | Same branch; HEAD unchanged **or** drift explicitly documented; no surprise tracked edits from shutdown |
| P2 | Runtime evidence present | Custody dir exists; mandatory artifacts listed |
| P3 | Shutdown successful | Authorization + SHUTDOWN_OBSERVATION result SUCCESS |
| P4 | No orphan CSS process | Inventory empty for CSS roles |
| P5 | Ports released | No CSS listener on declared ports |
| P6 | Evidence manifest complete | All required IDs present; hashes verify; `secrets_present=false` |
| P7 | Credit claim consistent | Claimed credit type matches §3 eligibility |
| P8 | Live still not authorized | No live orders; authority blocked in last sealed snapshot |

Any FAIL ⇒ overall certification `FAIL`. Any mandatory BLOCKED ⇒ overall `BLOCKED`.

---

## 9. Relationship to merge / live programmes

- ER closeout should complete **before** MR-001 merges are applied on the endurance host.
- ER observational PASS does **not** clear LDT AntiBleed/CAD20, FX, TTL, or OANDA LIVE blockers.
- After closeout, RC-LIVE-001 candidate work proceeds on a clean host/worktree per MR-001.

---

## 10. Explicit statement

**ER-001 does not stop the running runtime and does not certify OV-002 by publication of this plan.**
