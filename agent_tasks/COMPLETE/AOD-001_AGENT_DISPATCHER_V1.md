id: AOD-001
status: COMPLETE
priority: 110
risk: MEDIUM
owner: Codex
base_branch: css-v1.0.1-maintenance
starting_head: e79ab0837506dd5efd930af3fd1d95a48082a653
claimed_branch: css-agent-dispatcher-v1
claimed_starting_head: c706c0184c059342d5580448c0d524fc2b742e63
claimed_at_utc: 2026-08-12T04:34:42Z
review_ready_at_utc: 2026-08-12T04:41:49Z
r1_remediated_at_utc: 2026-08-12T05:09:51Z
r2_remediated_at_utc: 2026-08-12T05:31:10Z
r3_remediated_at_utc: 2026-08-12T11:56:12Z
r4_accepted_at_utc: 2026-08-12T12:09:51Z
closed_at_utc: 2026-08-12T12:31:58Z
commit_authority: NONE
push_authority: NONE
live_trading_authority: NONE

# AOD-001 — Agent Orchestration Dispatcher V1

## Objective

Implement a local, repository-native dispatcher that lets CSS process the highest-priority READY task with one short command while preserving the governance in `AGENTS.md` and `.codex-instructions.md`.

The dispatcher must discover approved local coding agents, choose an eligible implementation agent deterministically, launch it with the canonical queue instruction, and preserve an audit trail. It must not autonomously merge, push, enable trading, or bypass task authority.

## Approved agent candidates

Initial candidate order and roles:

1. Codex CLI — preferred implementation worker when available.
2. Claude Code — preferred independent review worker when the implementation agent was Codex.
3. Cursor CLI — fallback implementation/review host when usable non-interactively or via a documented launch path.
4. Google Antigravity — detect installed application availability, but do not assume a CLI exists. If no safe supported CLI/automation seam is discoverable, report it as GUI_ONLY/UNAVAILABLE_FOR_DISPATCH rather than fabricating invocation.

The implementation must be model/vendor agnostic enough to add future agents without redesigning the queue protocol.

## Required behavior

### 1. Repository gate

Before launching any agent, verify and record:

- repository root;
- current branch and HEAD;
- upstream and ahead/behind state;
- staged, modified, and untracked files;
- merge/rebase/cherry-pick state;
- queue/active-task state.

If the repository is dirty outside an explicitly claimed task scope, or branch state conflicts with the selected task, fail closed.

### 2. Task selection

Read `agent_tasks/QUEUE/*.md` and select only tasks with `status: READY`.

Selection order:

- highest numeric priority first;
- lexical task ID as tie-breaker.

Do not allow overlapping ACTIVE ownership.

### 3. Agent discovery

Discover at minimum:

- `codex`
- `claude`
- `cursor`
- Antigravity installed-app presence

Record executable/app availability and version where safely queryable.

Discovery must not install software or alter PATH automatically.

### 4. Deterministic implementation-agent selection

For V1 use this safe preference unless the task explicitly restricts an agent:

`codex -> claude -> cursor`

Antigravity may be selected only if a verified safe invocation seam exists.

If no eligible agent is available, report BLOCKED without changing task state.

### 5. Canonical launch instruction

The implementation agent must receive an instruction equivalent to:

`Read AGENTS.md and .codex-instructions.md. Inspect repository state. Process the highest-priority READY task in agent_tasks/QUEUE. Obey all safety, scope, validation, commit, and review gates. If anything conflicts, fail closed and report BLOCKED.`

The dispatcher must not silently grant commit/push/merge/live-trading authority beyond the task front matter.

### 6. Review-agent separation

Provide a review mode that selects a different agent family from the implementation worker where practical.

Default V1 rule:

- if implementation agent = Codex, reviewer preference begins with Claude;
- if implementation agent = Claude, reviewer preference begins with Codex;
- never treat the implementing agent's self-review as independent acceptance for MEDIUM/HIGH trading-sensitive tasks.

### 7. Modes

Support at minimum:

- `discover` — report available agents only;
- `status` — show repo/task/agent state without mutation;
- `dispatch` — choose and launch the highest-priority READY task;
- `review` — choose and launch an eligible independent reviewer for the highest-priority REVIEW task;
- `dry-run` — show exactly what would be selected/launched, with no task mutation or agent launch.

Prefer a PowerShell entrypoint because the certified desktop environment is Windows/PowerShell. A small Python helper is acceptable if already-supported dependencies suffice.

### 8. Auditability

Write deterministic local audit evidence under an appropriate repository-controlled or ignored runtime/log location, recording at minimum:

- UTC timestamp;
- mode;
- branch/HEAD;
- selected task;
- selected agent and version;
- exact launch command minus secrets;
- final dispatcher outcome.

Do not log credentials, tokens, environment secrets, or private broker data.

### 9. Safety boundaries

The dispatcher itself must never:

- enable live trading;
- place or authorize orders;
- access or change broker credentials;
- modify RBAC, Unified Trade Gate, Margin Gate, Capital Governor, AntiBleedGuard, kill switches, emergency stops, or execution defaults;
- install dependencies automatically;
- rewrite Git history;
- force push;
- merge PRs;
- fabricate agent availability;
- auto-approve arbitrary tool calls from coding agents.

### 10. Robust failure behavior

Fail closed for:

- no READY/REVIEW task for requested mode;
- dirty conflicting workspace;
- invalid task metadata;
- overlapping ACTIVE scope;
- selected agent unavailable;
- unsupported invocation mode;
- malformed configuration.

Return a clear nonzero exit code for blocked/error states.

## Preferred files / scope

Prefer additive orchestration files such as:

- `tools/agent_dispatcher.ps1`
- optional `tools/agent_dispatcher.py`
- `tests/test_agent_dispatcher*`
- `docs/AGENT_DISPATCHER.md`
- task/status files required by queue protocol

Avoid application trading logic. Changes to existing intelligence/execution modules are out of scope.

## Acceptance tests

At minimum prove deterministically:

1. discovery identifies Codex and Claude when present;
2. dry-run selects the highest-priority READY task without mutation;
3. priority and lexical tie-break behavior is correct;
4. dirty/conflicting workspace fails closed;
5. no eligible agent fails closed;
6. dispatch does not grant commit/push/merge/live-trading authority;
7. review mode prefers a different agent family;
8. Antigravity installed-without-CLI is reported truthfully, not invoked through a guessed command;
9. audit output contains no obvious secrets/tokens;
10. no trading/execution modules are modified.

Tests must avoid actually launching external agents unless explicitly isolated/mocked.

## Validation

Run:

- focused dispatcher tests;
- syntax/compile checks for changed scripts/helpers;
- relevant governance/queue tests if present;
- `git diff --check`;
- final status/diff inspection.

Do not run live trading or broker integrations.

## Implementation Evidence

### Files changed

- `tools/agent_dispatcher.py`
- `tools/agent_dispatcher.ps1`
- `tests/test_agent_dispatcher.py`
- `docs/AGENT_DISPATCHER.md`
- `agent_tasks/STATUS.md`
- `agent_tasks/ACTIVE/AOD-001_AGENT_DISPATCHER_V1.md` moved to `agent_tasks/REVIEW/AOD-001_AGENT_DISPATCHER_V1.md`

### Validation results

- `.\.venv\Scripts\python.exe -m py_compile tools\agent_dispatcher.py tests\test_agent_dispatcher.py` - PASSED.
- `.\.venv\Scripts\python.exe -m pytest tests\test_agent_dispatcher.py -q` - PASSED, `10 passed in 11.78s`.
- `powershell -ExecutionPolicy Bypass -File tools\agent_dispatcher.ps1 discover -AuditDir C:\tmp\css_agent_dispatcher_audit_validation` - PASSED outside sandbox after the sandboxed run could not access the local Python launcher.
- `.\.venv\Scripts\python.exe -m tools.agent_dispatcher status --audit-dir C:\tmp\css_agent_dispatcher_audit_validation` - PASSED outside sandbox after the sandboxed run could not access the local Python launcher.
- `git diff --check` - PASSED; emitted only environment warnings for inaccessible user git ignore and CRLF normalization notice on `agent_tasks/STATUS.md`.

### Safety boundary

No live trading, broker account access, credential changes, execution-governance changes, dependency installation, staging, commit, push, merge, or deployment was performed. Changes remained inside the AOD-001 orchestration/documentation/test/task-status write scope and did not modify trading, broker, risk, or execution modules.

### Final implementation disposition

`AOD-001 IMPLEMENTED â€” READY FOR INDEPENDENT REVIEW`

## R1 Remediation Evidence

Independent Claude review failed AOD-001 on two reproducible defects. R1 applied the narrowest safe dispatcher remediation and kept AOD-001 in REVIEW pending independent re-review.

### R1 files changed

- `tools/agent_dispatcher.py`
- `tests/test_agent_dispatcher.py`
- `agent_tasks/REVIEW/AOD-001_AGENT_DISPATCHER_V1.md`
- `agent_tasks/STATUS.md`

### R1 fix summary

- BLOCKED audit records now preserve the inspected real `GitState` when repository inspection succeeded before the block. The fallback empty/minimal `GitState` is used only when no inspected state is available.
- `base_branch` enforcement now fails closed when the declared base cannot be resolved. Resolution is limited to deterministic local branch refs and `origin/<base_branch>` remote-tracking refs; non-ancestor bases block with an explicit `BASE_BRANCH_MISMATCH` reason.

### R1 tests added

- Dirty-worktree BLOCKED audit preserves real branch and HEAD.
- ACTIVE-task-conflict BLOCKED audit preserves real branch and HEAD.
- Base-branch mismatch BLOCKED audit preserves real branch and HEAD.
- Merge/rebase/cherry-pick BLOCKED audit preserves real branch and HEAD when Git inspection succeeds.
- Nonexistent `base_branch` blocks with `BASE_BRANCH_UNRESOLVABLE`.
- Local valid `base_branch` passes when it is an ancestor.
- `origin/<base_branch>` satisfies the declared base when the local branch is absent and the remote-tracking ref exists.
- Non-ancestor base blocks with `BASE_BRANCH_MISMATCH`.

### R1 validation results

- `.\.venv\Scripts\python.exe -m py_compile tools\agent_dispatcher.py tests\test_agent_dispatcher.py` - PASSED.
- `.\.venv\Scripts\python.exe -m pytest tests\test_agent_dispatcher.py -q` - PASSED, `20 passed in 32.15s`.
- `powershell -ExecutionPolicy Bypass -File tools\agent_dispatcher.ps1 discover -AuditDir C:\tmp\css_agent_dispatcher_r1_discover` - PASSED.
- `powershell -ExecutionPolicy Bypass -File tools\agent_dispatcher.ps1 status -AuditDir C:\tmp\css_agent_dispatcher_r1_status` - PASSED.
- `.\.venv\Scripts\python.exe -m pytest tests\test_agent_dispatcher.py::test_dirty_worktree_blocked_audit_preserves_real_branch_and_head tests\test_agent_dispatcher.py::test_active_task_conflict_blocked_audit_preserves_real_branch_and_head tests\test_agent_dispatcher.py::test_base_branch_mismatch_blocked_audit_preserves_real_branch_and_head tests\test_agent_dispatcher.py::test_in_progress_git_operation_blocked_audit_preserves_real_branch_and_head -q` - PASSED, `6 passed in 13.76s`.

### R1 safety boundary

No live trading, broker account access, credential changes, execution-governance changes, dependency installation, staging, commit, push, merge, or deployment was performed. R1 changes remained inside the AOD-001 orchestration/test/task-record scope and did not touch trading, broker, risk, or execution modules.

### R1 disposition

`AOD-001 R1 REMEDIATED - READY FOR INDEPENDENT RE-REVIEW`

## R2 Remediation Evidence

Independent Claude R1 re-review identified one remaining MEDIUM auditability defect: BLOCKED audit JSON preserved only top-level `branch` and `head`, dropping other inspected `GitState` fields needed to explain fail-closed decisions.

### R2 files changed

- `tools/agent_dispatcher.py`
- `tests/test_agent_dispatcher.py`
- `agent_tasks/REVIEW/AOD-001_AGENT_DISPATCHER_V1.md`
- `agent_tasks/STATUS.md`

### R2 fix summary

- `write_audit()` now persists a structured `git` object containing the complete inspected `GitState`: `root`, `branch`, `head`, `upstream`, `ahead`, `behind`, `staged_files`, `modified_files`, `untracked_files`, `merge_active`, `rebase_active`, and `cherry_pick_active`.
- Existing top-level `branch` and `head` audit fields remain in place for backward compatibility.
- No task selection, agent discovery, launch command, dry-run, reviewer selection, or governance behavior was changed.

### R2 tests added or strengthened

- Dirty-worktree BLOCKED audit persists complete GitState including staged, modified, and untracked evidence.
- ACTIVE-task-conflict BLOCKED audit persists complete GitState including real upstream, ahead, and behind values.
- Merge, rebase, and cherry-pick BLOCKED audits persist complete GitState and the corresponding active-operation flag.
- `BASE_BRANCH_MISMATCH` BLOCKED audit persists complete GitState and explicit reason.
- `BASE_BRANCH_UNRESOLVABLE` BLOCKED audit persists complete GitState and explicit reason.
- Successful dry-run audit records continue to serialize correctly with complete GitState and backward-compatible top-level `branch`/`head`.

### R2 validation results

- `.\.venv\Scripts\python.exe -m py_compile tools\agent_dispatcher.py tests\test_agent_dispatcher.py` - PASSED.
- `.\.venv\Scripts\python.exe -m pytest tests\test_agent_dispatcher.py -q` - PASSED, `22 passed in 54.63s`.
- `.\.venv\Scripts\python.exe -m pytest tests\test_agent_dispatcher.py::test_dirty_worktree_blocked_audit_persists_complete_git_state tests\test_agent_dispatcher.py::test_active_task_conflict_blocked_audit_persists_complete_git_state tests\test_agent_dispatcher.py::test_base_branch_mismatch_blocked_audit_persists_complete_git_state tests\test_agent_dispatcher.py::test_base_branch_unresolvable_blocked_audit_persists_complete_git_state tests\test_agent_dispatcher.py::test_in_progress_git_operation_blocked_audit_persists_complete_git_state -q` - PASSED, `7 passed in 29.47s`.
- `powershell -ExecutionPolicy Bypass -File tools\agent_dispatcher.ps1 discover -AuditDir C:\tmp\css_agent_dispatcher_r2_discover` - PASSED.
- `powershell -ExecutionPolicy Bypass -File tools\agent_dispatcher.ps1 status -AuditDir C:\tmp\css_agent_dispatcher_r2_status` - PASSED.

### R2 safety boundary

No live trading, broker account access, credential changes, execution-governance changes, dependency installation, staging, commit, push, merge, or deployment was performed. R2 changes remained inside the AOD-001 orchestration/test/task-record scope and did not touch trading, broker, risk, or execution modules.

### R2 disposition

`AOD-001 R2 REMEDIATED - READY FOR INDEPENDENT RE-REVIEW`

## R3 Remediation Evidence

Independent R3 acceptance review identified two remaining defects: version discovery could crash when an installed agent's `--version` probe timed out, and durable audit JSON did not persist the inspected queue state required to explain repository-gate decisions.

### R3 files changed

- `tools/agent_dispatcher.py`
- `tests/test_agent_dispatcher.py`
- `agent_tasks/REVIEW/AOD-001_AGENT_DISPATCHER_V1.md`
- `agent_tasks/STATUS.md`

### R3 fix summary

- Agent version probing is now non-throwing for timeout and OS execution errors. A timed-out discovered executable is classified as `VERSION_TIMEOUT`, records no version, and has launch support disabled fail-closed instead of crashing discovery.
- Audit records now include a structured `queue` object containing inspected `ready_tasks`, `active_tasks`, and `review_tasks` for successful and BLOCKED outcomes.
- BLOCKED ACTIVE-overlap audit evidence now preserves the active task objects/state in durable audit JSON, not only the selected task and textual reason.

### R3 tests added or strengthened

- Version-probe timeout regression proves discovery returns structured output without an unhandled traceback, classifies the timed-out agent truthfully as fail-closed, and still writes audit evidence.
- Successful `status` audit records persist inspected READY, ACTIVE, and REVIEW queue task state.
- BLOCKED ACTIVE-overlap audit records persist inspected active task objects/state.
- Successful dry-run and redaction audit tests now assert queue state is present in durable audit JSON.

### R3 validation results

- `.\.venv\Scripts\python.exe -c "from pathlib import Path; compile(Path('tools/agent_dispatcher.py').read_text(encoding='utf-8'), 'tools/agent_dispatcher.py', 'exec'); compile(Path('tests/test_agent_dispatcher.py').read_text(encoding='utf-8'), 'tests/test_agent_dispatcher.py', 'exec'); print('syntax ok')"` - PASSED, `syntax ok`.
- `$env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests\test_agent_dispatcher.py` - PASSED, `24 passed in 44.59s`. Pytest emitted a post-run Windows temp cleanup `PermissionError` for `pytest-current`; tests had already completed successfully.
- `powershell -ExecutionPolicy Bypass -File tools\agent_dispatcher.ps1 discover -AuditDir C:\tmp\css_agent_dispatcher_r3_remediation_discover_final` - PASSED and produced structured dispatcher JSON plus audit evidence at `C:\tmp\css_agent_dispatcher_r3_remediation_discover_final\2026-08-12T115820Z_discover.json`.

### R3 safety boundary

No live trading, broker account access, credential changes, execution-governance changes, dependency installation, staging, commit, push, merge, stash, reset, clean, branch switching, or deployment was performed. R3 changes remained inside the AOD-001 orchestration/test/task-record scope and did not touch trading, broker, risk, execution, intelligence, or credential modules.

### R3 disposition

`AOD-001 R3 REMEDIATED - READY FOR INDEPENDENT R4 REVIEW`

## R4 Acceptance Evidence

Independent R4 acceptance review verified the complete AOD-001 implementation and R3 remediation.

### R4 findings

- CRITICAL: None.
- HIGH: None.
- MEDIUM: None.
- LOW: None.
- INFORMATIONAL: Pytest emitted a Windows temporary-directory cleanup `PermissionError` after all tests completed successfully; this was treated separately from test pass/fail.
- INFORMATIONAL: Git commands emitted environment warnings for inaccessible user global git ignore and CRLF normalization on `agent_tasks/STATUS.md`; these did not affect validation.

### R4 validation results

- Repository gate: workspace `C:\rasib\source\capital-strata-systems`; branch `css-agent-dispatcher-v1`; HEAD `c706c0184c059342d5580448c0d524fc2b742e63`; upstream `origin/css-agent-dispatcher-v1`; divergence `0/0`; no staged files; no active merge, rebase, cherry-pick, or revert; dirty scope limited to accepted AOD-001 review work.
- Python syntax validation for `tools/agent_dispatcher.py` and `tests/test_agent_dispatcher.py` - PASSED, `syntax ok`.
- `$env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests\test_agent_dispatcher.py` - PASSED, `24 passed in 44.40s`. Post-run warning: Windows temp cleanup `PermissionError` after tests completed.
- `powershell -ExecutionPolicy Bypass -File tools\agent_dispatcher.ps1 discover -AuditDir C:\tmp\css_agent_dispatcher_r4_discover_20260812_001` - PASSED; structured JSON and audit evidence produced at `C:\tmp\css_agent_dispatcher_r4_discover_20260812_001\2026-08-12T120347Z_discover.json`.
- R4 timeout PowerShell smoke with temporary fake agent executables under `C:\tmp\css_agent_dispatcher_r4_fake_bin` - PASSED; fake Claude timed out during version discovery and was reported as `VERSION_TIMEOUT`, `version: null`, `launch_supported: false`; other agents continued discovery; audit evidence produced at `C:\tmp\css_agent_dispatcher_r4_timeout_smoke_20260812_001\2026-08-12T120951Z_discover.json`.
- PowerShell parser validation for `tools\agent_dispatcher.ps1` - PASSED, `powershell syntax ok`.
- `git diff --check` - PASSED with only environment warnings.
- `git diff --stat` - inspected; untracked AOD-001 files were not included because staging was not authorized during review.
- `git status --short` - inspected; dirty scope remained limited to accepted AOD-001 review work.

### R4 verification summary

- `subprocess.TimeoutExpired` from agent `--version` probes is caught and cannot escape as an unhandled traceback.
- Timed-out version probes are represented truthfully and fail-closed.
- One timed-out agent does not block discovery of other agents.
- PowerShell discover produces structured output and audit evidence under timeout conditions.
- Audit JSON persists inspected READY, ACTIVE, and REVIEW queue state for successful and BLOCKED outcomes.
- BLOCKED ACTIVE-overlap audit evidence preserves actual active task objects/state.
- BLOCKED audit records continue to preserve complete inspected `GitState`.
- Audit evidence remains secret-safe for tested token/secret/password/api-key/bearer launch-command values.
- READY selection remains deterministic by highest numeric priority and lexical task-ID tie-break.
- ACTIVE overlap protection remains fail-closed.
- Implementation-agent and independent-reviewer family separation remains enforced.
- Codex, Claude, Cursor, and Antigravity discovery semantics remain truthful.
- `discover`, `status`, `dispatch`, `review`, and `dry-run` behavior remains correct under the AOD-001 design.
- No dispatcher path grants commit, push, merge, deployment, live-trading, broker, credential, or execution-gate authority.
- Tests do not launch real external implementation or review agents.

### R4 acceptance verdict

`AOD-001 R4 ACCEPTANCE REVIEW  PASS`

## Closure Evidence

AOD-001 was moved from `REVIEW` to `COMPLETE` after independent R4 acceptance. Closure was limited to task-state governance records and did not modify dispatcher behavior, tests, documentation, trading, broker, execution, intelligence, risk, credential, or runtime code.

Publication commit/push was not performed because AOD-001 front matter explicitly declares `commit_authority: NONE` and `push_authority: NONE`. Under `AGENTS.md` commit/push policy, this blocks staging, committing, and pushing despite successful task closure.

### Closure disposition

`AOD-001 COMPLETE - R4 ACCEPTED; PUBLICATION COMMIT/PUSH BLOCKED BY TASK AUTHORITY`

## Completion gate

Implementation agent moves this task to REVIEW and records exact evidence. Independent review by a different agent family is required before COMPLETE.

Final implementation disposition must be exactly one of:

`AOD-001 IMPLEMENTED — READY FOR INDEPENDENT REVIEW`

or

`AOD-001 BLOCKED — <reason>`
