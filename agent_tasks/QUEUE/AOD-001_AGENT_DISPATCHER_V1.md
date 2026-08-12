id: AOD-001
status: READY
priority: 110
risk: MEDIUM
owner: UNCLAIMED
base_branch: css-v1.0.1-maintenance
starting_head: e79ab0837506dd5efd930af3fd1d95a48082a653
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

## Completion gate

Implementation agent moves this task to REVIEW and records exact evidence. Independent review by a different agent family is required before COMPLETE.

Final implementation disposition must be exactly one of:

`AOD-001 IMPLEMENTED — READY FOR INDEPENDENT REVIEW`

or

`AOD-001 BLOCKED — <reason>`
