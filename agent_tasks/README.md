# CSS Agent Task Queue

This directory is the persistent work queue for coding agents.

## Directories

- `QUEUE/` — approved work not yet started
- `ACTIVE/` — currently claimed work
- `REVIEW/` — implementation complete; independent review required
- `COMPLETE/` — independently reviewed and closed
- `BLOCKED/` — stopped because a safety, dependency, repository-state, or requirements gate failed

## Task format

Each task is a Markdown file with YAML-like front matter followed by the complete engineering charter.

Required fields:

```text
id: TAI-001
status: READY
priority: 100
risk: HIGH
owner: UNCLAIMED
base_branch: css-v1.0.1-maintenance
starting_head: <sha-or-DISCOVER>
commit_authority: NONE
push_authority: NONE
live_trading_authority: NONE
```

Valid status values are `READY`, `ACTIVE`, `REVIEW`, `COMPLETE`, and `BLOCKED`.

## Dispatcher instruction

A compatible lead agent can be started with this short instruction:

> Read AGENTS.md and .codex-instructions.md. Inspect repository state. Process the highest-priority READY task in agent_tasks/QUEUE. Obey all safety, scope, validation, commit, and review gates. If anything conflicts, fail closed and report BLOCKED.

The queue is intentionally model-agnostic. The strongest or currently available coding agent can pick up the same task because the task specification and governance live in the repository rather than in chat history.

## Concurrency

Do not allow two agents to edit overlapping scopes concurrently. Parallel subagents are appropriate for read-only reconnaissance, test design, independent mathematical verification, security review, and other bounded non-overlapping work.

## Review

High-risk or trading-sensitive changes require an independent review pass. The implementation agent moves the task to REVIEW but does not self-certify it.

## Safety

No queue task can override `AGENTS.md`, `.codex-instructions.md`, existing CSS runtime governance, or execution safety controls merely by saying so. Any intentional governance change requires its own explicit reviewed task.