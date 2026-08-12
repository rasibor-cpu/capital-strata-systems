# CSS Agent Dispatcher

`tools/agent_dispatcher.ps1` is the Windows entrypoint for the repository-native agent dispatcher. It delegates deterministic logic to `tools.agent_dispatcher` so selection and fail-closed gates can be tested without starting external tools.

## Modes

- `discover` reports local agent availability for Codex, Claude, Cursor, and Google Antigravity installed-app presence.
- `status` reports repository, task queue, and agent state without launching an agent.
- `dry-run` selects the highest-priority READY task and implementation agent without mutating task state or launching.
- `dispatch` selects the highest-priority READY task and launches the selected implementation agent unless `-NoLaunch` is supplied.
- `review` selects the highest-priority REVIEW task and prefers a reviewer from a different agent family.

The dispatcher never grants commit, push, merge, live-trading, broker, credential, or execution-governance authority. The launched agent receives the canonical queue instruction and must obey task front matter and repository governance.

## Audit Evidence

Each run writes redacted JSON evidence under `audit_logs/agent_dispatcher/` by default. The directory is ignored as runtime audit output. Use `-AuditDir` or `--audit-dir` for isolated validation runs.

## Examples

```powershell
.\tools\agent_dispatcher.ps1 discover
.\tools\agent_dispatcher.ps1 status
.\tools\agent_dispatcher.ps1 dry-run
.\tools\agent_dispatcher.ps1 dispatch -NoLaunch
.\tools\agent_dispatcher.ps1 review -ImplementationFamily codex -NoLaunch
```
