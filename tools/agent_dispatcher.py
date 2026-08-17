"""Repository-native coding-agent dispatcher for CSS task queue governance."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence


CANONICAL_LAUNCH_INSTRUCTION = (
    "Read AGENTS.md and .codex-instructions.md. Inspect repository state. "
    "Process the highest-priority READY task in agent_tasks/QUEUE. Obey all "
    "safety, scope, validation, commit, push, merge, and independent-review "
    "gates. Do not enable live trading, access broker accounts, change "
    "credentials, alter execution governance, install dependencies, stage, "
    "commit, push, or merge unless the task explicitly grants that authority. "
    "If anything conflicts, fail closed and report BLOCKED."
)

SECRET_PATTERNS = (
    re.compile(r"(?i)(token|secret|credential|password|api[_-]?key)=\S+"),
    re.compile(r"(?i)bearer\s+[a-z0-9._\-]+"),
)

IMPLEMENTATION_PREFERENCE = ("codex", "claude", "cursor")
REVIEW_PREFERENCE_BY_IMPLEMENTER = {
    "codex": ("claude", "cursor"),
    "claude": ("codex", "cursor"),
}


class DispatcherBlocked(RuntimeError):
    """Raised for deterministic fail-closed dispatcher states."""

    def __init__(
        self,
        message: str,
        *,
        git_state: "GitState | None" = None,
        queue_state: "QueueState | None" = None,
        plan: "DispatchPlan | None" = None,
    ) -> None:
        super().__init__(message)
        self.git_state = git_state
        self.queue_state = queue_state
        self.plan = plan

    def with_context(
        self,
        *,
        git_state: "GitState | None" = None,
        queue_state: "QueueState | None" = None,
        plan: "DispatchPlan | None" = None,
    ) -> "DispatcherBlocked":
        return DispatcherBlocked(
            str(self),
            git_state=self.git_state or git_state,
            queue_state=self.queue_state or queue_state,
            plan=self.plan or plan,
        )


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class GitState:
    root: str
    branch: str
    head: str
    upstream: str
    ahead: int | None
    behind: int | None
    staged_files: tuple[str, ...]
    modified_files: tuple[str, ...]
    untracked_files: tuple[str, ...]
    merge_active: bool
    rebase_active: bool
    cherry_pick_active: bool

    @property
    def dirty(self) -> bool:
        return bool(self.staged_files or self.modified_files or self.untracked_files)


@dataclass(frozen=True)
class Task:
    id: str
    status: str
    priority: int
    path: str
    metadata: dict[str, str]


@dataclass(frozen=True)
class QueueState:
    ready_tasks: tuple[Task, ...]
    active_tasks: tuple[Task, ...]
    review_tasks: tuple[Task, ...]


@dataclass(frozen=True)
class AgentStatus:
    agent_id: str
    family: str
    status: str
    executable: str | None
    version: str | None
    launch_supported: bool
    notes: str


@dataclass(frozen=True)
class DispatchPlan:
    mode: str
    selected_task: Task | None
    selected_agent: AgentStatus | None
    launch_command: tuple[str, ...] | None
    outcome: str
    reason: str | None = None


def _run_command(args: Sequence[str], cwd: Path | None = None, timeout: int = 10) -> CommandResult:
    proc = subprocess.run(
        list(args),
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return CommandResult(proc.returncode, proc.stdout.strip(), proc.stderr.strip())


def _redact(value: str) -> str:
    redacted = value
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub(lambda match: match.group(0).split("=", 1)[0] + "=<REDACTED>" if "=" in match.group(0) else "<REDACTED>", redacted)
    return redacted


def redact_command(command: Sequence[str] | None) -> list[str] | None:
    if command is None:
        return None
    return [_redact(part) for part in command]


def _git(repo: Path, args: Sequence[str], allow_failure: bool = False) -> CommandResult:
    result = _run_command(("git", *args), cwd=repo)
    if result.returncode != 0 and not allow_failure:
        raise DispatcherBlocked(f"git {' '.join(args)} failed: {result.stderr or result.stdout}")
    return result


def inspect_git_state(repo: Path) -> GitState:
    root = _git(repo, ("rev-parse", "--show-toplevel")).stdout
    root_path = Path(root)
    branch = _git(root_path, ("branch", "--show-current")).stdout or "DETACHED"
    head = _git(root_path, ("rev-parse", "HEAD")).stdout
    upstream_result = _git(
        root_path,
        ("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"),
        allow_failure=True,
    )
    upstream = upstream_result.stdout if upstream_result.returncode == 0 else "NONE"
    ahead = behind = None
    if upstream != "NONE":
        counts = _git(root_path, ("rev-list", "--left-right", "--count", "HEAD...@{u}")).stdout.split()
        if len(counts) == 2:
            ahead, behind = int(counts[0]), int(counts[1])

    git_dir = Path(_git(root_path, ("rev-parse", "--git-dir")).stdout)
    if not git_dir.is_absolute():
        git_dir = root_path / git_dir

    return GitState(
        root=str(root_path),
        branch=branch,
        head=head,
        upstream=upstream,
        ahead=ahead,
        behind=behind,
        staged_files=tuple(_lines(_git(root_path, ("diff", "--cached", "--name-only")).stdout)),
        modified_files=tuple(_lines(_git(root_path, ("diff", "--name-only")).stdout)),
        untracked_files=tuple(_lines(_git(root_path, ("ls-files", "--others", "--exclude-standard")).stdout)),
        merge_active=(git_dir / "MERGE_HEAD").exists(),
        rebase_active=(git_dir / "rebase-merge").exists() or (git_dir / "rebase-apply").exists(),
        cherry_pick_active=(git_dir / "CHERRY_PICK_HEAD").exists(),
    )


def _lines(value: str) -> list[str]:
    return [line.strip().replace("\\", "/") for line in value.splitlines() if line.strip()]


def parse_task_file(path: Path) -> Task:
    metadata: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()
    missing = [key for key in ("id", "status", "priority") if key not in metadata]
    if missing:
        raise DispatcherBlocked(f"invalid task metadata in {path}: missing {', '.join(missing)}")
    try:
        priority = int(metadata["priority"])
    except ValueError as exc:
        raise DispatcherBlocked(f"invalid task priority in {path}: {metadata['priority']}") from exc
    return Task(
        id=metadata["id"],
        status=metadata["status"],
        priority=priority,
        path=str(path),
        metadata=metadata,
    )


def _tasks_in(directory: Path, status: str) -> tuple[Task, ...]:
    if not directory.exists():
        return ()
    tasks = []
    for path in sorted(directory.glob("*.md")):
        task = parse_task_file(path)
        if task.status == status:
            tasks.append(task)
    return tuple(tasks)


def inspect_queue_state(repo: Path) -> QueueState:
    task_root = repo / "agent_tasks"
    return QueueState(
        ready_tasks=_tasks_in(task_root / "QUEUE", "READY"),
        active_tasks=_tasks_in(task_root / "ACTIVE", "ACTIVE"),
        review_tasks=_tasks_in(task_root / "REVIEW", "REVIEW"),
    )


def select_task(tasks: Iterable[Task]) -> Task | None:
    ordered = sorted(tasks, key=lambda task: (-task.priority, task.id))
    return ordered[0] if ordered else None


def _version_for(executable: str, args: Sequence[str] = ("--version",)) -> str | None:
    result = _run_command((executable, *args), timeout=5)
    if result.returncode != 0:
        return None
    return (result.stdout or result.stderr).splitlines()[0][:160] if (result.stdout or result.stderr) else None


def _safe_version_for(executable: str) -> tuple[str | None, str | None]:
    try:
        return _version_for(executable), None
    except subprocess.TimeoutExpired:
        return None, "VERSION_TIMEOUT"
    except OSError as exc:
        return None, f"VERSION_ERROR: {exc.__class__.__name__}"


def _detect_antigravity_app() -> str | None:
    roots = [
        os.environ.get("LOCALAPPDATA"),
        os.environ.get("ProgramFiles"),
        os.environ.get("ProgramFiles(x86)"),
    ]
    candidates = (
        "Google\\Antigravity\\Antigravity.exe",
        "Antigravity\\Antigravity.exe",
    )
    for root in roots:
        if not root:
            continue
        for candidate in candidates:
            path = Path(root) / candidate
            if path.exists():
                return str(path)
    return None


def discover_agents() -> tuple[AgentStatus, ...]:
    agents: list[AgentStatus] = []
    for agent_id in ("codex", "claude", "cursor"):
        executable = shutil.which(agent_id)
        if not executable:
            agents.append(AgentStatus(agent_id, agent_id, "UNAVAILABLE", None, None, False, "not found on PATH"))
            continue
        version, version_error = _safe_version_for(executable)
        if version_error:
            agents.append(
                AgentStatus(
                    agent_id,
                    agent_id,
                    version_error.split(":", 1)[0],
                    executable,
                    None,
                    False,
                    f"found on PATH but {version_error.lower().replace('_', ' ')}; launch disabled fail-closed",
                )
            )
            continue
        if agent_id == "cursor":
            agents.append(
                AgentStatus(
                    agent_id,
                    agent_id,
                    "AVAILABLE_GUI_OR_CLI",
                    executable,
                    version,
                    False,
                    "non-interactive dispatch seam not assumed by V1",
                )
            )
            continue
        agents.append(
            AgentStatus(
                agent_id,
                agent_id,
                "AVAILABLE",
                executable,
                version,
                True,
                "safe non-interactive launch command supported by dispatcher V1",
            )
        )

    antigravity_path = _detect_antigravity_app()
    agents.append(
        AgentStatus(
            "antigravity",
            "antigravity",
            "GUI_ONLY" if antigravity_path else "UNAVAILABLE",
            antigravity_path,
            None,
            False,
            "installed application detected without verified CLI seam" if antigravity_path else "installed application not detected",
        )
    )
    return tuple(agents)


def _agent_by_id(agents: Sequence[AgentStatus], agent_id: str) -> AgentStatus | None:
    return next((agent for agent in agents if agent.agent_id == agent_id), None)


def select_implementation_agent(agents: Sequence[AgentStatus]) -> AgentStatus | None:
    for agent_id in IMPLEMENTATION_PREFERENCE:
        agent = _agent_by_id(agents, agent_id)
        if agent and agent.launch_supported:
            return agent
    return None


def select_review_agent(agents: Sequence[AgentStatus], implementation_family: str | None = None) -> AgentStatus | None:
    preference = REVIEW_PREFERENCE_BY_IMPLEMENTER.get(implementation_family or "codex", ("claude", "codex", "cursor"))
    for agent_id in preference:
        agent = _agent_by_id(agents, agent_id)
        if agent and agent.launch_supported:
            return agent
    return None


def build_launch_command(agent: AgentStatus, mode: str) -> tuple[str, ...]:
    if not agent.executable or not agent.launch_supported:
        raise DispatcherBlocked(f"selected agent {agent.agent_id} has no supported launch command")
    instruction = CANONICAL_LAUNCH_INSTRUCTION
    if mode == "review":
        instruction += " Review the highest-priority REVIEW task and do not mark it COMPLETE unless the task explicitly permits that disposition."
    if agent.agent_id == "codex":
        return (agent.executable, "exec", instruction)
    if agent.agent_id == "claude":
        return (agent.executable, "-p", instruction)
    raise DispatcherBlocked(f"unsupported launch mode for {agent.agent_id}")


def resolve_base_branch(repo: Path, base_branch: str) -> tuple[str, str] | None:
    declared = base_branch.strip()
    if not declared:
        return None
    if declared.startswith("refs/"):
        candidates = (declared,)
    elif declared.startswith("origin/"):
        candidates = (f"refs/remotes/{declared}",)
    else:
        candidates = (f"refs/heads/{declared}", f"refs/remotes/origin/{declared}")
    for candidate in candidates:
        result = _run_command(("git", "rev-parse", "--verify", "--quiet", f"{candidate}^{{commit}}"), cwd=repo)
        if result.returncode == 0 and result.stdout:
            return candidate, result.stdout
    return None


def enforce_repo_gate(git_state: GitState, queue_state: QueueState, selected_task: Task | None, mode: str) -> None:
    if git_state.merge_active or git_state.rebase_active or git_state.cherry_pick_active:
        raise DispatcherBlocked("repository has an active merge, rebase, or cherry-pick")
    if mode in {"dispatch", "dry-run", "review"} and git_state.dirty:
        raise DispatcherBlocked("repository is dirty; dispatcher refuses to launch agents from a conflicting workspace")
    if mode in {"dispatch", "dry-run"} and queue_state.active_tasks:
        active_ids = ", ".join(task.id for task in queue_state.active_tasks)
        raise DispatcherBlocked(f"overlapping ACTIVE task ownership present: {active_ids}")
    if selected_task is not None:
        base_branch = selected_task.metadata.get("base_branch")
        if base_branch:
            resolved = resolve_base_branch(Path(git_state.root), base_branch)
            if resolved is None:
                raise DispatcherBlocked(
                    f"BASE_BRANCH_UNRESOLVABLE: task base_branch {base_branch} did not resolve as a local branch or origin remote-tracking branch"
                )
            resolved_ref, resolved_commit = resolved
            ancestor = _run_command(("git", "merge-base", "--is-ancestor", resolved_commit, "HEAD"), cwd=Path(git_state.root))
            if ancestor.returncode != 0:
                raise DispatcherBlocked(
                    f"BASE_BRANCH_MISMATCH: current HEAD is not based on task base_branch {base_branch} ({resolved_ref})"
                )


def plan_dispatch(repo: Path, mode: str, implementation_family: str | None = None) -> tuple[GitState, QueueState, tuple[AgentStatus, ...], DispatchPlan]:
    repo = repo.resolve()
    agents = discover_agents()
    if mode == "discover":
        empty_git = GitState(str(repo), "", "", "", None, None, (), (), (), False, False, False)
        empty_queue = QueueState((), (), ())
        return empty_git, empty_queue, agents, DispatchPlan(mode, None, None, None, "OK")

    git_state = inspect_git_state(repo)
    selected_task: Task | None = None
    queue_state: QueueState | None = None
    try:
        queue_state = inspect_queue_state(Path(git_state.root))

        if mode == "status":
            return git_state, queue_state, agents, DispatchPlan(mode, None, None, None, "OK")

        task_pool = queue_state.review_tasks if mode == "review" else queue_state.ready_tasks
        selected_task = select_task(task_pool)
        if selected_task is None:
            expected = "REVIEW" if mode == "review" else "READY"
            raise DispatcherBlocked(f"no {expected} task available")

        enforce_repo_gate(git_state, queue_state, selected_task, mode)
        selected_agent = select_review_agent(agents, implementation_family) if mode == "review" else select_implementation_agent(agents)
        if selected_agent is None:
            raise DispatcherBlocked("no eligible launch-supported agent is available")
        launch_command = build_launch_command(selected_agent, "review" if mode == "review" else "dispatch")
        outcome = "DRY_RUN" if mode == "dry-run" else "PLANNED"
        return git_state, queue_state, agents, DispatchPlan(mode, selected_task, selected_agent, launch_command, outcome)
    except DispatcherBlocked as exc:
        plan = DispatchPlan(mode, selected_task, None, None, "BLOCKED", str(exc))
        raise exc.with_context(git_state=git_state, queue_state=queue_state, plan=plan) from exc


def serialize_queue_state(queue_state: QueueState) -> dict[str, list[dict[str, object]]]:
    return {
        "ready_tasks": [asdict(task) for task in queue_state.ready_tasks],
        "active_tasks": [asdict(task) for task in queue_state.active_tasks],
        "review_tasks": [asdict(task) for task in queue_state.review_tasks],
    }


def write_audit(
    audit_dir: Path,
    mode: str,
    git_state: GitState,
    queue_state: QueueState,
    plan: DispatchPlan,
    outcome: str,
    reason: str | None = None,
) -> Path:
    audit_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    safe_task = asdict(plan.selected_task) if plan.selected_task else None
    safe_agent = asdict(plan.selected_agent) if plan.selected_agent else None
    payload = {
        "timestamp_utc": timestamp,
        "mode": mode,
        "git": asdict(git_state),
        "queue": serialize_queue_state(queue_state),
        "branch": git_state.branch,
        "head": git_state.head,
        "selected_task": safe_task,
        "selected_agent": safe_agent,
        "launch_command": redact_command(plan.launch_command),
        "outcome": outcome,
        "reason": reason,
    }
    path = audit_dir / f"{timestamp.replace(':', '')}_{mode}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def execute_launch(plan: DispatchPlan) -> int:
    if not plan.launch_command:
        raise DispatcherBlocked("no launch command prepared")
    return subprocess.call(list(plan.launch_command))


def serialize_result(
    git_state: GitState,
    queue_state: QueueState,
    agents: Sequence[AgentStatus],
    plan: DispatchPlan,
    audit_path: Path | None,
) -> dict[str, object]:
    return {
        "git": asdict(git_state),
        "queue": {
            "ready_tasks": [asdict(task) for task in queue_state.ready_tasks],
            "active_tasks": [asdict(task) for task in queue_state.active_tasks],
            "review_tasks": [asdict(task) for task in queue_state.review_tasks],
        },
        "agents": [asdict(agent) for agent in agents],
        "plan": {
            **asdict(plan),
            "launch_command": redact_command(plan.launch_command),
        },
        "audit_path": str(audit_path) if audit_path else None,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CSS local coding-agent dispatcher")
    parser.add_argument("mode", choices=("discover", "status", "dispatch", "review", "dry-run"))
    parser.add_argument("--repo", default=".", help="repository root or child path")
    parser.add_argument("--audit-dir", default=None, help="audit output directory")
    parser.add_argument("--implementation-family", default=None, help="review mode implementer family to avoid")
    parser.add_argument("--no-launch", action="store_true", help="plan dispatch/review without starting an external agent")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    audit_dir = Path(args.audit_dir) if args.audit_dir else repo / "audit_logs" / "agent_dispatcher"
    audit_path: Path | None = None
    try:
        git_state, queue_state, agents, plan = plan_dispatch(repo, args.mode, args.implementation_family)
        outcome = plan.outcome
        if args.mode in {"dispatch", "review"} and not args.no_launch:
            launch_code = execute_launch(plan)
            outcome = "LAUNCHED" if launch_code == 0 else f"LAUNCH_EXIT_{launch_code}"
        audit_path = write_audit(audit_dir, args.mode, git_state, queue_state, plan, outcome)
        result = serialize_result(git_state, queue_state, agents, plan, audit_path)
        result["plan"]["outcome"] = outcome
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if outcome in {"OK", "DRY_RUN", "PLANNED", "LAUNCHED"} else 2
    except DispatcherBlocked as exc:
        git_state = exc.git_state or GitState(str(repo), "", "", "", None, None, (), (), (), False, False, False)
        queue_state = exc.queue_state or QueueState((), (), ())
        plan = exc.plan or DispatchPlan(args.mode, None, None, None, "BLOCKED", str(exc))
        try:
            audit_path = write_audit(audit_dir, args.mode, git_state, queue_state, plan, "BLOCKED", str(exc))
        except OSError:
            audit_path = None
        print(json.dumps({"outcome": "BLOCKED", "reason": str(exc), "audit_path": str(audit_path) if audit_path else None}, indent=2))
        return 2


if __name__ == "__main__":
    sys.exit(main())
