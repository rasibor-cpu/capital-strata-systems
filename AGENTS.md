# Capital Strata Systems — Agent Governance

This file is the canonical entrypoint for coding agents working in this repository.

## Mission

Agents may inspect, implement, test, document, and review approved CSS engineering tasks. They must preserve CSS safety, governance, auditability, and broker-agnostic design.

## Mandatory startup sequence

Before editing anything:

1. Read this file completely.
2. Read `.codex-instructions.md` completely.
3. Inspect repository path, branch, HEAD, upstream, ahead/behind, staged files, modified files, untracked files, and active merge/rebase/cherry-pick state.
4. Read `agent_tasks/README.md` and `agent_tasks/STATUS.md`.
5. Select only a task whose front matter says `status: READY`.
6. Verify the task's safety boundary and permitted write scope before changing files.
7. If repository state conflicts with the task assumptions, stop fail-closed and report the mismatch.

## Authority boundaries

No agent may, unless a task explicitly authorizes it and the repository's existing governance permits it:

- enable live trading;
- place or submit real orders;
- access or alter funded broker credentials;
- weaken, bypass, disable, or silently modify Unified Trade Gate, Margin Gate, RBAC, Capital Governor, AntiBleedGuard, kill switches, emergency stops, audit controls, or equivalent execution protections;
- change live/paper mode defaults toward live execution;
- remove fail-closed behavior;
- delete working features merely to make tests pass;
- rewrite repository history;
- force-push;
- commit directly to a protected/certified baseline branch;
- install new dependencies without explicit task authorization and rationale.

If any requested work would require one of these actions, stop and report `BLOCKED — GOVERNANCE BOUNDARY`.

## Task queue protocol

Task states are represented by directories:

- `agent_tasks/QUEUE/` — approved tasks waiting to start.
- `agent_tasks/ACTIVE/` — task currently being worked.
- `agent_tasks/REVIEW/` — implementation complete and awaiting independent review.
- `agent_tasks/COMPLETE/` — independently reviewed and closed.
- `agent_tasks/BLOCKED/` — cannot proceed safely or deterministically.

A task is eligible only when its front matter contains `status: READY` and no conflicting ACTIVE task owns the same write scope.

Agents should prefer the highest numeric `priority` value. Ties are broken by lexical task ID.

## Claiming a task

Before implementation, an agent must:

1. Re-check git state.
2. Confirm no overlapping ACTIVE task exists.
3. Change the task status from `READY` to `ACTIVE` and record:
   - agent/session identifier if available;
   - branch;
   - starting HEAD;
   - UTC start timestamp.
4. Move the task file from `QUEUE` to `ACTIVE` when the execution environment supports file moves safely. If not, update `agent_tasks/STATUS.md` and leave a clear claim marker in the task file before code changes.

Only one implementation agent may own a task's write scope at a time.

## Delegation / subagents

A lead agent may use subagents for bounded work such as repository reconnaissance, test design, mathematical verification, security review, architecture review, or documentation.

Subagents:

- inherit this file and the active task's restrictions;
- must not independently broaden scope;
- must not commit, push, merge, deploy, enable live trading, or change credentials unless the active task explicitly grants that authority;
- return evidence to the lead agent, which remains responsible for integration.

Parallel subagents must not write the same files concurrently.

## Engineering discipline

All work must remain PCNRASS compliant: Please Confirm No Regression And Stable State.

Prefer:

- additive, modular changes;
- existing abstractions and dependencies;
- deterministic behavior;
- typed/stable contracts;
- structured logging and audit evidence;
- explicit insufficient-data states;
- fail-closed behavior;
- tests that prove safety boundaries as well as functional correctness.

Never fabricate market data, broker state, credentials, runtime evidence, test results, or certification evidence.

## Validation requirements

At minimum, every implementation task must:

1. compile or syntax-check changed source files where applicable;
2. run the narrowest relevant tests;
3. run the task-required regression suite;
4. record exact commands and results;
5. inspect `git diff --check` where available;
6. inspect final `git diff --stat` and `git status --short`;
7. verify that no out-of-scope files changed.

If full regression cannot run, report exactly why. Do not convert an untested state into PASS.

## Completion / review gate

Implementation agents do not self-certify high-risk trading changes.

When implementation is complete:

- set task status to `REVIEW`;
- record files changed, tests, results, limitations, and final git state;
- move the task to `agent_tasks/REVIEW/` where practical;
- do not mark `COMPLETE` unless the task explicitly permits self-review.

An independent review agent should verify mathematical correctness, regression risk, data leakage/look-ahead risk where applicable, safety-boundary isolation, and test adequacy before closing the task.

## Commit / push policy

Default: **do not commit, push, merge, or deploy** unless the active task explicitly authorizes those actions.

Repository-governance/bootstrap tasks may be committed on an isolated feature branch when explicitly created for that purpose. Certified or maintenance baselines remain untouched until reviewed.

## Standard final report

Every task report must include:

1. TASK ID
2. WORKSPACE / BRANCH / HEAD
3. PRE-CHANGE STATE
4. FILES CHANGED
5. PURPOSE
6. ARCHITECTURE / INTEGRATION SEAM
7. TESTS AND EXACT RESULTS
8. REGRESSION RISKS
9. SAFETY-BOUNDARY VERIFICATION
10. FINAL GIT STATUS / DIFF STAT
11. KNOWN LIMITATIONS
12. NEXT RECOMMENDED ACTION
13. FINAL DISPOSITION: `READY FOR REVIEW`, `BLOCKED`, or `COMPLETE` as permitted

When uncertain, preserve the existing system and fail closed.