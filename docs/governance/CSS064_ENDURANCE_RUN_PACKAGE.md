# CSS-064 Governed Endurance Run Package (real Windows host)

**Status:** PACKAGE PREPARED. The run has NOT been executed. CSS-064 remains **BLOCKED** until this run is
executed on the real host and independently reviewed.
**Authority:** the Master Portfolio Register. This document is engineering procedure only.
**Safety boundary (unchanged):** `execution_allowed=false`, `live_trading_blocked=true`,
`broker_execution_armed=false`, `advisory_only=true`. Nothing here authorizes funded or live execution.

## Why a new governed run is needed
- **Not certification:** the ~19.7-hour stable runtime is an observation. It had no frozen SHA, no
  preflight gate and no final manifest.
- **OV-002 Attempt 2 is invalidated** (`docs/release/CSS_OV002_ATTEMPT2_INVALIDATION_REPORT.md`) and must
  not be reused.
- **CI can't produce this evidence:** the 23 OV-002 regression tests depend on Windows process identity
  (creation time, executable path and hash) and Windows runtime discovery. They can only pass on the real
  host (see the CSS-061 failure ledger in `CSS_PROGRAM_REGISTER.md`).

## Tooling
| Step | Tool | Captures |
|---|---|---|
| Pre-run gate | `scripts/css064_endurance_package.py preflight` | Exact expected SHA = HEAD; clean worktree; Windows host; operator ID; interpreter path and SHA-256; four safety flags, each explicitly observed (missing = FAIL); target hours >= 72 |
| Run | `scripts/css_ov002_72h_endurance.py` (existing OV-002 monitor) | Run metadata, git freeze, machine identity, supervisor process identity (`SUPERVISOR_PREFLIGHT.json`), `PROCESS_IDENTITY.json`, health snapshots, checkpoints, critical events, heartbeat and restart reconciliation, irreversible invalidation markers |
| Finalize | `scripts/css064_endurance_package.py finalize` | SHA-256 of every evidence file, start and end timestamps, monitor status and counters, invalidation markers, final flag capture, HEAD unchanged, manifest digest, disposition |

The disposition is at best `CERTIFICATION_CANDIDATE_INDEPENDENT_REVIEW_REQUIRED`. It is never "CERTIFIED".
If the preflight file is absent, the disposition is `OBSERVATION_ONLY`.

## Procedure: exact Windows command sequence (operator on the real host, PowerShell)

Placeholders: `<FROZEN_SHA>` is the frozen candidate commit (given in the release note for this run) and
`<OPERATOR_ID>` is the operator's identifier. Evidence is written **outside** the repository, so the
worktree stays clean.

```powershell
# 0. Variables
$Repo = "C:\rasib\source\capital-strata-systems"
$Sha  = "<FROZEN_SHA>"
New-Item -ItemType Directory -Force -Path "C:\CSS_Evidence" | Out-Null
$Pkg  = "C:\CSS_Evidence\CSS064_" + (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$env:CSS_OV002_HEALTH_BASE = "http://127.0.0.1:8765"

# 1. Freeze the candidate (must print the SHA and an EMPTY status)
Set-Location $Repo
git fetch origin feature/governed-configurable-pilot-limit
git checkout --detach $Sha
git rev-parse HEAD
git status --porcelain

# 2. Environment + real-host regression slice (CSS-061 evidence; all must pass on Windows)
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pytest -q tests/test_ov002_endurance_monitor.py tests/test_ov002_r1_continuity_remediation.py tests/test_ov002_r1_r1_blocker_repairs.py tests/test_phase163_endurance_validation.py tests/test_safety_flag_observation.py tests/test_css064_endurance_package.py *> "$Pkg-host-regression.txt"
.venv\Scripts\python.exe -m pytest -q *> "$Pkg-full-regression.txt"

# 3. Start the runtime (advisory/paper only) in a SEPARATE window and leave it running
#    (equivalent to double-clicking launch_css.bat)
Start-Process -FilePath "$Repo\launch_css.bat" -WorkingDirectory $Repo

# 4. Confirm the authoritative safety surface (expect verdict=SAFE, execution_allowed=false,
#    live_trading_blocked=true, broker_execution_armed=false, advisory_only=true, not_observed=[])
Invoke-RestMethod "$env:CSS_OV002_HEALTH_BASE/api/v1/safety-flags" | ConvertTo-Json -Depth 4

# 5. Pre-run gate (must exit 0 with certifying=true; any not_observed => STOP and report)
.venv\Scripts\python.exe scripts\css064_endurance_package.py preflight --package-dir $Pkg --expected-sha $Sha --operator-id <OPERATOR_ID>
if ($LASTEXITCODE -ne 0) { throw "CSS-064 preflight not certifying - do not start the run" }

# 6. 72-hour monitor (same package dir). Do not restart, edit, pull or redeploy during the run.
.venv\Scripts\python.exe scripts\css_ov002_72h_endurance.py --output-dir $Pkg --target-hours 72
#    Only if the MONITOR process itself was interrupted (runtime untouched):
#    .venv\Scripts\python.exe scripts\css_ov002_72h_endurance.py --resume-dir $Pkg --target-hours 72

# 7. Finalize (writes CSS064_FINAL_MANIFEST.json; never overwrites)
.venv\Scripts\python.exe scripts\css064_endurance_package.py finalize --package-dir $Pkg
Get-FileHash "$Pkg\CSS064_FINAL_MANIFEST.json" -Algorithm SHA256

# 8. Archive the package directory and the two regression logs unchanged; send for independent review.
```

### Stop conditions
- **Wrong checkout:** step 1 prints a different SHA or a non-empty status. Stop.
- **Real-host tests fail:** step 2 fails any test in the real-host slice. Record the output; that is
  CSS-061 evidence, not something to fix during the run.
- **Flags not exposed or unsafe:** step 4 returns 404, a `verdict` other than `SAFE`, any `NOT_OBSERVED`
  flag or any unsafe value.
- **Preflight not certifying:** step 5 exits non-zero.
- **Run invalidated:** an `INVALIDATION*.json` appears in `$Pkg`. The attempt is invalidated; do not
  resume it as certifying.

### Independent review
The reviewer re-hashes every file against `CSS064_FINAL_MANIFEST.json`, checks there are zero
invalidation markers, checks `head_at_finalize == expected_sha`, and records the result in the Master
Portfolio Register. Only then may CSS-064 move to DONE.

## Acceptance (engineering mirror; the authority's wording prevails)
- **Duration:** at least 72 h continuous wall-clock on the frozen SHA, with zero unexpected runtime
  restarts and zero critical heartbeat-loss events.
- **Safety:** all four flags observed safe at preflight, throughout (monitor safety assertions) and at
  finalize.
- **Custody:** a complete hashed manifest that an independent reviewer has reproduced.

## Pre-run gaps (status as of this commit)
0. **Authoritative surface: `GET /api/v1/safety-flags`** (schema `css.safety_flags.v1`).
   - Returns all four flags at top level, each an exact boolean or `"NOT_OBSERVED"`, plus
     `verdict` (`SAFE` / `UNSAFE` / `NOT_OBSERVED`), `fail_closed`, `not_observed` and `unsafe`.
   - It is GET-only (other methods return 405).
   - The CSS-064 preflight/finalize and the OV-002 monitor accept flags **only** from this surface.
     Flags found elsewhere can make a check fail but can never satisfy it.
   - **Requires restarting the server onto the frozen SHA.** A server running an earlier build returns
     404 here, and the preflight then fails closed. On 2026-10-07 the running Windows server exposed
     none of the four flags on `/health`, `/status`, `/mission-control` or `/mobile`.
1. **`broker_execution_armed` exposure: RESOLVED in code.**
   - `/api/v1/live-execution-authority` on the :8765 launcher now publishes `safety_flags`, derived by
     `backend/runtime/safety_flag_observation.py` from runtime-mode resolution, the broker authority
     feed, the mobile trading-mode control and the legacy arming global.
   - An unreadable source yields `null` (not observed).
   - Before this change, only `execution_allowed` and `advisory_only` were exposed, and as literals.
   - Verified in-process with FastAPI TestClient (`tests/test_safety_flag_observation.py`). It must
     still be confirmed on the real host at step 4.
2. **Fail-open `advisory_only` default in the OV-002 monitor: FIXED.**
   - `capture_safety_assertions` now reports a missing or non-boolean `advisory_only`, any missing
     observed flag, or a missing `fail_closed` as `not_observed` / failed.
3. **Reboot detection remains Windows-only** (`GetTickCount64`). The package refuses non-Windows
   hosts.
