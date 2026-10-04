# Phase 181 Certification Matrix: Release-Candidate Line (2026-10-04)

**Phase 181 status: `NOT_CERTIFIED`.** This matrix separates what remains into three categories that are never mixed:
- **Code / engineering:** closable in the repository.
- **Runtime evidence:** needs observed operation on the governed host.
- **External governance:** needs a party or environment outside engineering.

Passing tests, or a clean soak, closes nothing in the other two categories. Live trading authorization is not a row in any category that engineering can close.

Release line: PR #101 (`css-operator-auth-2026-09-28`) stacked on PR #100. Safety posture throughout: `execution_allowed=false`, `live_trading_blocked=true`, `advisory_only=true`, broker execution unarmed, Questrade read-only, Binance live execution disabled.

The Phase 181 framework document (`docs/governance/PHASE_181_PRODUCTION_READINESS_CERTIFICATION.md`) lives on `css-rclive-w1-autonomous-supervisor`, not on this line. This matrix applies its boundary to this line without porting the evaluator.

## A. Code / engineering

| ID | Item | Status | Evidence |
|---|---|---|---|
| ENG-01 | Route-level auth for every servable route; anonymous engine run closed; production API docs off | **CLOSED** (pending CI on the new head) | COM-016, `tests/test_route_auth_inventory.py` (163) |
| ENG-02 | Supervisor restart limit cumulative, persistent and terminal (Attempt 2 defect) | **CLOSED** (pending CI) | `dashboard/runtime/runtime_supervisor.py`, `tests/test_endurance_supervision.py` |
| ENG-03 | Exit code / signal / PID transition / child output retained | **CLOSED** (pending CI) | as ENG-02 |
| ENG-04 | Heartbeat classification and loss diagnostics (thread vs event loop vs PID vs monitor vs clock) | **CLOSED** (pending CI) | `dashboard/runtime/heartbeat_diagnostics.py`, `runtime_heartbeat.py` |
| ENG-05 | Endurance monitor on this line: auto-invalidation, hash-chained evidence, recorder-restart handling | **CLOSED** (pending CI) | `dashboard/runtime/endurance_monitor.py`, `scripts/css_ov002_endurance.py`, `tests/test_endurance_monitor.py` |
| ENG-06 | Mobile smoke test stale since 2026-06-16; never run in CI | **CLOSED** | Smoke updated to the governed contract; added to two workflows and to the suite (`tests/test_mobile_smoke.py`) |
| ENG-07 | **Unattended, fail-closed paper-engine mode.** `scripts/css_live_dashboard.py` still needs interactive sign-on, mode/broker/arming prompts and a per-cycle ENTER, so the trading engine loop cannot be soaked unattended | **OPEN** | Root-cause analysis §"Consequence"; deliberately not improvised (touches engine startup and arming) |
| ENG-08 | Operator sessions are in-memory (restart-safe sessions) | **OPEN** (known; fail-safe) | `docs/CSS_COMMERCIAL_CLOSURE_EVIDENCE.md` item 23 |
| ENG-09 | `python-jose` → `ecdsa` 0.19.2 (PYSEC-2026-1325, no fixed version); `jose` is not imported by `backend/`, `dashboard/` or `engine/` | **OPEN** (low) | `pip-audit -r requirements.txt` on 2026-10-04. Proposed fix: drop the unused dependency after confirming no other consumer |
| ENG-10 | Engine-API `/health` echoes import-error text | **OPEN** (low) | COM-016 audit |
| ENG-11 | PR #100 / #101 not merged to `css-v1-completion-2026-09-13` | **OPEN** (owner merge decision) | PR state |

## B. Runtime evidence

| ID | Item | Status |
|---|---|---|
| RUN-01 | OV-002 Attempt 1 | **INVALIDATED** (commit drift at ~25.19 h); no credit |
| RUN-02 | OV-002 Attempt 2 | **INVALIDATED** (8 unexpected restarts, 2 critical heartbeat losses); no credit; root cause in `CSS_OV002_ATTEMPT2_ROOT_CAUSE_ANALYSIS_2026-10-04.md` |
| RUN-03 | OV-002 Attempt 3: governed 72 h endurance of this release candidate's supervised service, on the governed host, with zero carry-forward | **NOT STARTED.** Approved by the owner on 2026-10-04; tooling and SHA prepared; must be started on the governed host (see the Attempt 3 readiness record) |
| RUN-04 | ~23 h interim checkpoint | Recorded automatically by the monitor as non-certifying `INTERIM_CHECKPOINT`; does not alter the 72 h requirement |
| RUN-05 | Engine-loop (paper) endurance | **BLOCKED on ENG-07** |
| RUN-06 | Host-side records that would settle Attempt 2 items 6–10 (console transcript, audit `login_failed`, CRITICAL `Runtime Exception` alerts, `cycles_completed`) | **OPEN** (owner to retrieve if retained) |
| RUN-07 | Runtime certification register rows (`certification/runtime/RUNTIME_CERTIFICATION_EVIDENCE_REGISTER.md`) | **NOT_STARTED** (unchanged) |

## C. External governance

| ID | Item | Status |
|---|---|---|
| EXT-01 | Independent security / operations review (secrets storage, TLS, monitoring and alerting, dependency review) | **BLOCKED (external)** |
| EXT-02 | Real-environment encrypted off-site backup and restore / rollback drill | **BLOCKED (external)** |
| EXT-03 | Signed incident tabletop | **BLOCKED (external)** |
| EXT-04 | Production-like UAT in a deployed environment | **BLOCKED (external)** |
| EXT-05 | Legal / jurisdiction review of the exact agreement and version | **BLOCKED (external)** |
| EXT-06 | Production environment | **BLOCKED (external)**: none exists |
| EXT-07 | Appropriate broker credentials and a `REAL_BROKER`, CURRENT, armed provenance | **BLOCKED (external)** |
| EXT-08 | Owner sign-off after reviewing all of the above | **BLOCKED** (requires the above first) |

## Decision (unchanged)

```
PHASE_181=NOT_CERTIFIED
PRODUCTION_RELEASE_AUTHORIZED=NO
LIVE_FUNDED_TRADING_AUTHORIZED=NO
BROKER_EXECUTION_AUTHORIZED=NO
```
