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

## Procedure (operator on the real Windows host)
1. **Freeze the candidate.** Check out the exact candidate commit. `git status --porcelain` must be empty.
   Record the SHA.
2. **Start the runtime** with the standard launcher and supervisor, in advisory/paper mode only. Confirm
   that `/api/runtime-mode` and `/api/v1/live-execution-authority` respond on `CSS_OV002_HEALTH_BASE`
   (default `http://127.0.0.1:8765`).
3. **Run the preflight.** It must exit 0 (`certifying: true`). If any flag reports `not_observed`, stop:
   that is an evidence gap to fix, not something to waive.
   ```
   python scripts/css064_endurance_package.py preflight --package-dir <PKG> --expected-sha <SHA> --operator-id <ID>
   ```
4. **Initialise and run the monitor** in the same package directory, for at least 72 wall-clock hours.
   Do not restart, edit, pull or redeploy during the run.
   ```
   python scripts/css_ov002_72h_endurance.py --output-dir <PKG> --target-hours 72
   ```
   Resume after a monitor-only interruption with `--resume-dir <PKG>`. A runtime restart invalidates the
   attempt; do not resume it as certifying.
5. **Finalize.** It must exit 0, then archive `<PKG>` unchanged, together with the manifest digest.
   ```
   python scripts/css064_endurance_package.py finalize --package-dir <PKG>
   ```
6. **Independent review.** The reviewer re-hashes every file against `CSS064_FINAL_MANIFEST.json`,
   checks there are zero invalidation markers, checks `head_at_finalize == expected_sha`, and records the
   result in the Master Portfolio Register. Only then may CSS-064 move to DONE.

## Acceptance (engineering mirror; the authority's wording prevails)
- **Duration:** at least 72 h continuous wall-clock on the frozen SHA, with zero unexpected runtime
  restarts and zero critical heartbeat-loss events.
- **Safety:** all four flags observed safe at preflight, throughout (monitor safety assertions) and at
  finalize.
- **Custody:** a complete hashed manifest that an independent reviewer has reproduced.

## Known gaps to resolve before running
1. **`broker_execution_armed` exposure unverified.** The runtime endpoints are not yet confirmed to expose
   it. The preflight fails closed with `not_observed` until they do.
2. **Fail-open advisory default in the monitor.** `capture_safety_assertions` treats a missing
   `advisory_only` as `True`. The CSS-064 preflight and finalize do not inherit this default, but the
   monitor's per-snapshot assertion should be made strict (CSS-062 follow-up).
3. **Reboot detection is Windows-only.** `CanonicalEnduranceEvidence.get_host_boot_time` uses Windows
   `GetTickCount64`. On other hosts it returns 0.0 and silently disables reboot detection. That doesn't
   matter on the Windows host, but the package refuses non-Windows hosts for this reason.
