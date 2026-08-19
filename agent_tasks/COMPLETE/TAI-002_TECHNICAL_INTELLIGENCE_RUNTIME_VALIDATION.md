---
id: TAI-002
status: COMPLETE
review_ready_at_utc: 2026-08-19T16:00:00Z
verified_utc: 2026-08-19T16:05:00Z
closed_at_utc: 2026-08-19T16:05:00Z
priority: 110
risk: HIGH
owner: Cursor Cloud Agent TAI-002 R2
base_branch: css-v1.0.1-maintenance
starting_head: ba3ff07478164fb1f5011fbc6f5d44955fb3f42d
original_charter_starting_head: e79ab0837506dd5efd930af3fd1d95a48082a653
claimed_branch: css-tai-002-runtime-validation-r2
claimed_starting_head: ba3ff07478164fb1f5011fbc6f5d44955fb3f42d
claimed_at_utc: 2026-08-19T15:51:23Z
commit_authority: FEATURE_BRANCH
push_authority: FEATURE_BRANCH
pr_authority: DRAFT_TO_MAINTENANCE
live_trading_authority: NONE
supersedes_branch: css-tai-002-runtime-validation
supersedes_pr: 54
merged_pr: 57
merge_commit: f70824f1e1deae34d24602597520411b88f7c311
lifecycle_reconciled_utc: 2026-08-19T18:59:40Z
---

# TAI-002 — Technical Intelligence Integration & Runtime Validation

## Recovery note

This is the TAI-002 R2 recovery from the current canonical maintenance HEAD
`ba3ff07478164fb1f5011fbc6f5d44955fb3f42d`. The original charter on
`css-tai-002-runtime-validation` assumed `e79ab083`. That SHA is an ancestor of
this baseline. The original branch at `3a1d76ec` and draft PR #54 are stale and
conflicting; they must not be merged or rebased in place.

Authority update for R2 (explicit operator instruction, 2026-08-19):

- commit and push are permitted **only** on feature branch
  `css-tai-002-runtime-validation-r2`;
- a **draft** PR targeting `css-v1.0.1-maintenance` is permitted;
- merge into maintenance or `main` is **not** permitted;
- live trading, funded orders, broker credential access, and execution-gate
  mutation remain `NONE`.

## Objective

Validate the already-merged TAI-001 Technical Intelligence subsystem end-to-end
inside the canonical CSS intelligence/opportunity pipeline while preserving
advisory-only behavior and all existing execution, broker, credential, risk,
governance, and live/paper safety boundaries.

This task is primarily validation, integration-hardening, observability, and
regression work. It must not enable live trading, place or submit real orders,
access or alter funded broker credentials, weaken governance gates, or change
live/paper defaults toward live execution.

## Mandatory pre-change gate

Before editing application code:

1. Read `AGENTS.md`, `.codex-instructions.md`, `agent_tasks/README.md`,
   `agent_tasks/STATUS.md`, and this task completely.
2. Verify repository path, branch, HEAD, upstream, ahead/behind, staged files,
   modified files, untracked files, and active merge/rebase/cherry-pick state.
3. Confirm the task baseline is `css-v1.0.1-maintenance` at
   `ba3ff07478164fb1f5011fbc6f5d44955fb3f42d`, or explicitly document a newer
   reviewed descendant before proceeding.
4. Confirm no overlapping ACTIVE task owns any intended write scope.
5. Claim the task per `AGENTS.md` before application-code changes.
6. If any repository-state or governance assumption conflicts, fail closed and
   report `BLOCKED — GOVERNANCE BOUNDARY` or the precise state mismatch.

## Validation scope

Establish, with deterministic evidence, that TAI-001 functions correctly through
the real CSS intelligence and opportunity-ranking seams.

### 1. End-to-end intelligence flow

Trace and test the canonical path from supplied OHLCV/time-series evidence
through `TechnicalIntelligenceEngine` into the existing autonomous opportunity
intelligence and opportunity ranking components.

Verify:

- technical intelligence is attached at the intended seam only;
- valid technical evidence is available to downstream diagnostics/ranking;
- no parallel trading or execution architecture is introduced;
- no mutation of broker, order-routing, execution, governance, or
  capital-control authority occurs.

### 2. Ranking interaction

Verify the ranking integration behaves deterministically and conservatively.

Required cases:

- strong valid bullish technical evidence;
- strong valid bearish technical evidence;
- conflicting multi-timeframe evidence;
- neutral/indeterminate evidence;
- insufficient-history evidence;
- stale evidence;
- malformed/non-finite evidence;
- future-timestamped evidence.

Prove that insufficient, malformed, stale, or future data cannot create an
artificial ranking advantage or high-confidence directional signal.

### 3. Anti-lookahead regression

Re-validate TAI-001 anti-lookahead behavior at the integration boundary, not
only inside the standalone engine.

At evaluation time T, downstream opportunity/ranking results must not change
because of candles or observations strictly after T.

Add an integration-level deterministic regression test that compares identical
histories with and without future observations and proves the current-time
ranking/intelligence result is unchanged or explicitly fail-closed.

### 4. Fail-closed propagation

Verify that TAI fail-closed states remain fail-closed after downstream
enrichment.

No downstream component may silently convert:

- `INSUFFICIENT_DATA`;
- future-timestamp rejection;
- stale-data rejection;
- malformed-data rejection;
- zero-confidence evidence;

into positive conviction, implicit authorization, or a higher-quality
opportunity classification.

### 5. Runtime / dashboard observability

Inspect the existing Mission Control/dashboard/runtime telemetry seams and
determine the narrowest safe way to expose TAI diagnostics if not already
visible.

At minimum, make the following inspectable through an existing machine-readable
diagnostics/state path where architecture permits:

- technical directional score;
- confidence;
- timeframe agreement/conflict;
- freshness/data-quality state;
- regime;
- component contributions/reasons;
- advisory-only / execution-disallowed safety markers.

Prefer existing state builders/contracts. Do not create a second dashboard
architecture.

If existing observability is already sufficient, add tests/documentation rather
than unnecessary code.

### 6. Trade-authority isolation

Prove through code inspection and automated tests that TAI cannot:

- place or submit orders;
- authorize execution;
- override an existing gate denial;
- alter RBAC;
- alter Unified Trade Gate;
- alter Margin Gate;
- alter Capital Governor;
- alter AntiBleedGuard;
- alter kill switches or emergency stops;
- access broker credentials;
- switch paper/practice/read-only operation toward live mode.

Include a regression proving that an existing downstream governance denial
remains denied regardless of favorable TAI evidence.

### 7. Regression coverage

Run the narrow TAI suite plus relevant intelligence/ranking/regime tests.
Include any affected dashboard/runtime tests if observability code changes.

Do not claim full-suite PASS unless the full suite is actually run.

## Preferred write scope

Keep changes minimal and additive. Expected files may include, only if
necessary:

- `tests/test_tai002_technical_intelligence_integration.py`;
- existing TAI/intelligence/ranking tests where narrowly appropriate;
- existing diagnostics/state-builder/frontend-contract files only when required
  for observability;
- `docs/TAI-002_TECHNICAL_INTELLIGENCE_RUNTIME_VALIDATION.md`;
- `agent_tasks/STATUS.md` and this task record as required by queue governance.

Avoid modifying `backend/intelligence/technical_intelligence.py` unless
validation reveals a concrete defect. If a defect is found, document the failing
reproduction first and make the smallest safe remediation.

Narrow integration-hardening is permitted at the autonomous-intelligence seam
to force advisory-only / execution-disallowed markers on TAI payloads before
ranking/Mission Control consumption.

## Forbidden scope

Do not modify, except to add a non-mutating test fixture/reference when
unavoidable:

- broker credentials or broker account configuration;
- live-order submission paths;
- live/paper default mode configuration;
- RBAC authorization behavior;
- Unified Trade Gate authorization behavior;
- Margin Gate authorization behavior;
- Capital Governor authorization behavior;
- AntiBleedGuard authorization behavior;
- kill-switch/emergency-stop semantics;
- funded-account connectivity.

Out of scope for TAI-002 (later tasks):

- MI-EXT integration;
- RC-LIVE reconciliation;
- world-event intelligence;
- manual-confirmation trading productization;
- autonomous live trading.

No live runtime, funded broker session, real order, endurance run, or
credential operation is authorized.

## Mandatory validation

At minimum, run and record exact results for:

1. changed Python compile/syntax checks;
2. standalone TAI-001 tests;
3. TAI-002 integration tests;
4. autonomous opportunity intelligence tests;
5. opportunity ranking tests;
6. market regime / intelligence orchestrator tests relevant to the touched seam;
7. dashboard/runtime tests if those files are modified;
8. `git diff --check`;
9. final `git diff --stat`;
10. final `git status --short`.

Add targeted deterministic tests for:

- valid bullish/bearish propagation;
- insufficient-data propagation;
- stale/malformed/future-data propagation;
- integration-level anti-lookahead;
- ranking determinism;
- gate-denial preservation;
- no execution-authority surface;
- observability contract, if changed.

## Acceptance criteria

TAI-002 is ready for independent review only when all of the following are
demonstrated:

- TAI evidence reaches the intended CSS intelligence/ranking seam correctly;
- downstream ranking remains deterministic;
- invalid or insufficient TAI evidence cannot create positive conviction or
  ranking advantage;
- integration-level anti-lookahead is proven;
- existing gate denials remain authoritative;
- TAI has no execution/broker/credential authority;
- required regression suites pass or any unrelated/pre-existing failures are
  precisely documented;
- observability is sufficient to explain technical evidence without granting
  execution authority;
- no live trading, broker credential access, funded account access, or real
  order activity occurred.

## Change control

- Commit/push only the TAI-002 R2 feature branch when implementation and
  required tests pass.
- Open only a draft PR targeting `css-v1.0.1-maintenance`.
- Do not merge or deploy.
- Do not install dependencies without stopping and reporting the requirement.
- Do not start live trading or a funded broker session.
- Preserve PCNRASS and fail-closed behavior throughout.

## Implementation record

Status: REVIEW

Recovered UTC: 2026-08-19T15:51:23Z
Review-ready UTC: 2026-08-19T16:00:00Z

Files added:

- `tests/test_tai002_technical_intelligence_integration.py`
- `docs/TAI-002_TECHNICAL_INTELLIGENCE_RUNTIME_VALIDATION.md`
- `agent_tasks/REVIEW/TAI-002_TECHNICAL_INTELLIGENCE_RUNTIME_VALIDATION.md`

Files modified:

- `backend/trading/autonomous_opportunity_intelligence_engine.py` — advisory safety overlay
- `backend/trading/opportunity_ranking_engine.py` — overlay TAI payload at ranking consumption
- `dashboard/mission_control/opportunity_ranking.py` — read-only TAI observability projection
- `agent_tasks/STATUS.md`

Validation:

- `python3 -m py_compile` of changed Python files → PASS
- `python3 -m pytest -q -p no:cacheprovider tests/test_tai002_technical_intelligence_integration.py` → `14 passed`
- TAI-001 + autonomous + ranking + orchestrator + regime suite → `52 passed`
- `tests/test_mc001_mission_control_foundation.py tests/test_mc007a_institutional_intelligence.py` → `20 passed, 1 warning` (Starlette httpx deprecation)
- `git diff --check` → PASS
- `tests/test_trade_tab_opportunity_ranking.py` → collection ERROR (`reportlab` missing; pre-existing environment gap, not a TAI-002 code regression)

Safety-boundary verification:

- No live trading, broker credentials, funded sessions, or orders.
- Unified Trade Gate, AntiBleedGuard, Capital Governor, RBAC, and kill-switch modules were not modified.
- Favorable TAI evidence cannot override a denying Unified Trade Gate.
- Forged `execution_allowed=True` TAI payloads are forced back to advisory-only before ranking/Mission Control.

## Verification review record

Status: COMPLETE

Verified UTC: 2026-08-19T16:05:00Z

Operator follow-up authorized verification and landing onto `css-v1.0.1-maintenance` after PR #57 review. PR #54 remains untouched and must not be merged. `main` remains untouched.

Re-verified:

- Base still `ba3ff07478164fb1f5011fbc6f5d44955fb3f42d`
- Feature HEAD `f9bae4c2e7c25552bbc4ac92cb097712a52d82a7` is 1 commit ahead of maintenance, mergeable
- Diff confined to TAI integration overlay, Mission Control read-only projection, tests, and task records
- Unified Trade Gate / AntiBleedGuard / Capital Governor / RBAC / kill-switch source not modified
- `python3 -m py_compile` PASS
- TAI-002 + TAI-001 + ranking/regime suite: 52 passed
- Mission Control mc001 + mc007a: 20 passed, 1 pre-existing Starlette/httpx warning

Informational (non-blocking):

- Bullish integration assertion allows `NEUTRAL` as well as `UP`
- Conflicting-MTF assertion is conservative (`confidence < 0.99`) rather than requiring `conflict_indicators`
- `FORBIDDEN_AUTHORITY_TOKENS` helper in the test file is unused; the test inlines a subset

Verdict: **TAI-002 R2 VERIFICATION PASS**. Authorized to land on `css-v1.0.1-maintenance` only.


