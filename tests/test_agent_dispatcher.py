from __future__ import annotations

from dataclasses import asdict
import json
import subprocess
from pathlib import Path

import pytest

from tools import agent_dispatcher as dispatcher


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "agent@example.invalid")
    _git(repo, "config", "user.name", "Agent Test")
    (repo / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")
    (repo / ".codex-instructions.md").write_text("# Instructions\n", encoding="utf-8")
    (repo / "agent_tasks" / "QUEUE").mkdir(parents=True)
    (repo / "agent_tasks" / "ACTIVE").mkdir()
    (repo / "agent_tasks" / "REVIEW").mkdir()
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")
    return repo


def _write_task(directory: Path, task_id: str, status: str, priority: int, extra: str = "") -> Path:
    path = directory / f"{task_id}.md"
    path.write_text(
        "\n".join(
            [
                f"id: {task_id}",
                f"status: {status}",
                f"priority: {priority}",
                "risk: MEDIUM",
                "owner: UNCLAIMED",
                "base_branch: master",
                "commit_authority: NONE",
                "push_authority: NONE",
                "live_trading_authority: NONE",
                extra,
                "",
                f"# {task_id}",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _head(repo: Path) -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def _branch(repo: Path) -> str:
    return subprocess.run(["git", "branch", "--show-current"], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def _latest_audit(audit_dir: Path) -> dict[str, object]:
    audits = sorted(audit_dir.glob("*.json"))
    assert audits
    return json.loads(audits[-1].read_text(encoding="utf-8"))


def _set_upstream_to_current_head(repo: Path) -> None:
    branch = _branch(repo)
    _git(repo, "config", "remote.origin.url", str(repo))
    _git(repo, "config", "remote.origin.fetch", "+refs/heads/*:refs/remotes/origin/*")
    _git(repo, "update-ref", f"refs/remotes/origin/{branch}", _head(repo))
    _git(repo, "config", f"branch.{branch}.remote", "origin")
    _git(repo, "config", f"branch.{branch}.merge", f"refs/heads/{branch}")


def _expected_git_payload(git_state: dispatcher.GitState) -> dict[str, object]:
    expected = asdict(git_state)
    for key in ("staged_files", "modified_files", "untracked_files"):
        expected[key] = list(expected[key])
    return expected


def _assert_complete_audit_git(payload: dict[str, object], expected_git_state: dispatcher.GitState) -> None:
    expected = _expected_git_payload(expected_git_state)
    assert payload["git"] == expected
    assert payload["branch"] == expected["branch"]
    assert payload["head"] == expected["head"]


def _assert_audit_queue_ids(payload: dict[str, object], *, ready: list[str], active: list[str], review: list[str]) -> None:
    queue = payload["queue"]
    assert [task["id"] for task in queue["ready_tasks"]] == ready
    assert [task["id"] for task in queue["active_tasks"]] == active
    assert [task["id"] for task in queue["review_tasks"]] == review


def _agents(codex: bool = True, claude: bool = True, cursor: bool = True):
    return (
        dispatcher.AgentStatus("codex", "codex", "AVAILABLE", "codex", "codex 1.0", codex, "test"),
        dispatcher.AgentStatus("claude", "claude", "AVAILABLE", "claude", "claude 1.0", claude, "test"),
        dispatcher.AgentStatus("cursor", "cursor", "AVAILABLE_GUI_OR_CLI", "cursor", "cursor 1.0", cursor, "test"),
        dispatcher.AgentStatus("antigravity", "antigravity", "GUI_ONLY", "Antigravity.exe", None, False, "test"),
    )


def test_discovery_identifies_codex_and_claude_when_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dispatcher.shutil, "which", lambda name: f"C:/tools/{name}.exe" if name in {"codex", "claude"} else None)
    monkeypatch.setattr(dispatcher, "_version_for", lambda executable: f"{Path(executable).stem} version")
    monkeypatch.setattr(dispatcher, "_detect_antigravity_app", lambda: None)

    agents = {agent.agent_id: agent for agent in dispatcher.discover_agents()}

    assert agents["codex"].status == "AVAILABLE"
    assert agents["codex"].launch_supported is True
    assert agents["claude"].status == "AVAILABLE"
    assert agents["claude"].launch_supported is True


def test_discovery_version_timeout_is_truthful_fail_closed_and_audited(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = _init_repo(tmp_path)
    audit_dir = tmp_path / "audit"

    def which(agent_id: str) -> str | None:
        return f"C:/tools/{agent_id}.exe" if agent_id in {"codex", "claude"} else None

    def version_for(executable: str) -> str:
        if Path(executable).stem.lower() == "claude":
            raise subprocess.TimeoutExpired([executable, "--version"], timeout=5)
        return f"{Path(executable).stem} version"

    monkeypatch.setattr(dispatcher.shutil, "which", which)
    monkeypatch.setattr(dispatcher, "_version_for", version_for)
    monkeypatch.setattr(dispatcher, "_detect_antigravity_app", lambda: None)

    result = dispatcher.main(["discover", "--repo", str(repo), "--audit-dir", str(audit_dir)])
    output = capsys.readouterr()
    payload = json.loads(output.out)
    agents = {agent["agent_id"]: agent for agent in payload["agents"]}
    audit_payload = _latest_audit(audit_dir)

    assert result == 0
    assert "Traceback" not in output.out
    assert "Traceback" not in output.err
    assert agents["codex"]["status"] == "AVAILABLE"
    assert agents["codex"]["launch_supported"] is True
    assert agents["claude"]["status"] == "VERSION_TIMEOUT"
    assert agents["claude"]["version"] is None
    assert agents["claude"]["launch_supported"] is False
    assert "launch disabled fail-closed" in agents["claude"]["notes"]
    assert audit_payload["outcome"] == "OK"
    assert audit_payload["mode"] == "discover"
    _assert_audit_queue_ids(audit_payload, ready=[], active=[], review=[])


def test_dry_run_selects_highest_priority_ready_without_task_mutation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _init_repo(tmp_path)
    task = _write_task(repo / "agent_tasks" / "QUEUE", "AOD-002", "READY", 200)
    _write_task(repo / "agent_tasks" / "QUEUE", "AOD-001", "READY", 100)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "queue")
    before = task.read_text(encoding="utf-8")
    monkeypatch.setattr(dispatcher, "discover_agents", lambda: _agents())

    _, _, _, plan = dispatcher.plan_dispatch(repo, "dry-run")

    assert plan.selected_task is not None
    assert plan.selected_task.id == "AOD-002"
    assert plan.selected_agent is not None
    assert plan.selected_agent.agent_id == "codex"
    assert task.read_text(encoding="utf-8") == before


def test_priority_tie_breaks_by_lexical_task_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _init_repo(tmp_path)
    _write_task(repo / "agent_tasks" / "QUEUE", "AOD-010", "READY", 110)
    _write_task(repo / "agent_tasks" / "QUEUE", "AOD-002", "READY", 110)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "queue")
    monkeypatch.setattr(dispatcher, "discover_agents", lambda: _agents())

    _, _, _, plan = dispatcher.plan_dispatch(repo, "dry-run")

    assert plan.selected_task is not None
    assert plan.selected_task.id == "AOD-002"


def test_dirty_workspace_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _init_repo(tmp_path)
    _write_task(repo / "agent_tasks" / "QUEUE", "AOD-001", "READY", 110)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "queue")
    (repo / "local_change.txt").write_text("dirty\n", encoding="utf-8")
    monkeypatch.setattr(dispatcher, "discover_agents", lambda: _agents())

    with pytest.raises(dispatcher.DispatcherBlocked, match="dirty"):
        dispatcher.plan_dispatch(repo, "dry-run")


def test_dirty_worktree_blocked_audit_persists_complete_git_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _init_repo(tmp_path)
    _write_task(repo / "agent_tasks" / "QUEUE", "AOD-001", "READY", 110)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "queue")
    (repo / "staged_change.txt").write_text("staged\n", encoding="utf-8")
    _git(repo, "add", "staged_change.txt")
    (repo / "AGENTS.md").write_text("# Agents\nmodified\n", encoding="utf-8")
    (repo / "local_change.txt").write_text("dirty\n", encoding="utf-8")
    expected_git_state = dispatcher.inspect_git_state(repo)
    audit_dir = tmp_path / "audit"
    monkeypatch.setattr(dispatcher, "discover_agents", lambda: _agents())

    result = dispatcher.main(["dry-run", "--repo", str(repo), "--audit-dir", str(audit_dir)])

    payload = _latest_audit(audit_dir)
    assert result == 2
    assert payload["outcome"] == "BLOCKED"
    assert payload["reason"].startswith("repository is dirty")
    _assert_complete_audit_git(payload, expected_git_state)
    assert payload["git"]["staged_files"] == ["staged_change.txt"]
    assert payload["git"]["modified_files"] == ["AGENTS.md"]
    assert payload["git"]["untracked_files"] == ["local_change.txt"]


def test_active_task_conflict_blocked_audit_persists_complete_git_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _init_repo(tmp_path)
    _write_task(repo / "agent_tasks" / "QUEUE", "AOD-001", "READY", 110)
    _write_task(repo / "agent_tasks" / "ACTIVE", "AOD-002", "ACTIVE", 100)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "active-conflict")
    _set_upstream_to_current_head(repo)
    expected_git_state = dispatcher.inspect_git_state(repo)
    audit_dir = tmp_path / "audit"
    monkeypatch.setattr(dispatcher, "discover_agents", lambda: _agents())

    result = dispatcher.main(["dry-run", "--repo", str(repo), "--audit-dir", str(audit_dir)])

    payload = _latest_audit(audit_dir)
    assert result == 2
    assert payload["outcome"] == "BLOCKED"
    assert payload["reason"].startswith("overlapping ACTIVE task ownership present")
    _assert_complete_audit_git(payload, expected_git_state)
    assert payload["git"]["upstream"] == f"origin/{expected_git_state.branch}"
    assert payload["git"]["ahead"] == 0
    assert payload["git"]["behind"] == 0
    _assert_audit_queue_ids(payload, ready=["AOD-001"], active=["AOD-002"], review=[])
    assert payload["queue"]["active_tasks"][0]["status"] == "ACTIVE"
    assert payload["queue"]["active_tasks"][0]["priority"] == 100


def test_base_branch_mismatch_blocked_audit_persists_complete_git_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _init_repo(tmp_path)
    _git(repo, "checkout", "-b", "otherbase")
    (repo / "base_only.txt").write_text("base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base-only")
    _git(repo, "checkout", "master")
    _write_task(repo / "agent_tasks" / "QUEUE", "AOD-001", "READY", 110, "base_branch: otherbase")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "queue")
    expected_git_state = dispatcher.inspect_git_state(repo)
    audit_dir = tmp_path / "audit"
    monkeypatch.setattr(dispatcher, "discover_agents", lambda: _agents())

    result = dispatcher.main(["dry-run", "--repo", str(repo), "--audit-dir", str(audit_dir)])

    payload = _latest_audit(audit_dir)
    assert result == 2
    assert payload["outcome"] == "BLOCKED"
    assert payload["reason"].startswith("BASE_BRANCH_MISMATCH")
    _assert_complete_audit_git(payload, expected_git_state)


def test_base_branch_unresolvable_blocked_audit_persists_complete_git_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _init_repo(tmp_path)
    _write_task(repo / "agent_tasks" / "QUEUE", "AOD-001", "READY", 110, "base_branch: missing-base")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "queue")
    expected_git_state = dispatcher.inspect_git_state(repo)
    audit_dir = tmp_path / "audit"
    monkeypatch.setattr(dispatcher, "discover_agents", lambda: _agents())

    result = dispatcher.main(["dry-run", "--repo", str(repo), "--audit-dir", str(audit_dir)])

    payload = _latest_audit(audit_dir)
    assert result == 2
    assert payload["outcome"] == "BLOCKED"
    assert payload["reason"].startswith("BASE_BRANCH_UNRESOLVABLE")
    _assert_complete_audit_git(payload, expected_git_state)


@pytest.mark.parametrize(
    ("marker_path", "is_dir", "expected_flag"),
    [
        ("MERGE_HEAD", False, "merge_active"),
        ("rebase-merge", True, "rebase_active"),
        ("CHERRY_PICK_HEAD", False, "cherry_pick_active"),
    ],
)
def test_in_progress_git_operation_blocked_audit_persists_complete_git_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    marker_path: str,
    is_dir: bool,
    expected_flag: str,
) -> None:
    repo = _init_repo(tmp_path)
    _write_task(repo / "agent_tasks" / "QUEUE", "AOD-001", "READY", 110)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "queue")
    head = _head(repo)
    marker = repo / ".git" / marker_path
    if is_dir:
        marker.mkdir()
    else:
        marker.write_text(head + "\n", encoding="utf-8")
    expected_git_state = dispatcher.inspect_git_state(repo)
    audit_dir = tmp_path / "audit"
    monkeypatch.setattr(dispatcher, "discover_agents", lambda: _agents())

    result = dispatcher.main(["dry-run", "--repo", str(repo), "--audit-dir", str(audit_dir)])

    payload = _latest_audit(audit_dir)
    assert result == 2
    assert payload["outcome"] == "BLOCKED"
    assert payload["reason"] == "repository has an active merge, rebase, or cherry-pick"
    _assert_complete_audit_git(payload, expected_git_state)
    assert payload["git"][expected_flag] is True


def test_no_eligible_agent_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _init_repo(tmp_path)
    _write_task(repo / "agent_tasks" / "QUEUE", "AOD-001", "READY", 110)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "queue")
    monkeypatch.setattr(dispatcher, "discover_agents", lambda: _agents(codex=False, claude=False, cursor=False))

    with pytest.raises(dispatcher.DispatcherBlocked, match="no eligible"):
        dispatcher.plan_dispatch(repo, "dry-run")


def test_nonexistent_base_branch_blocks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _init_repo(tmp_path)
    _write_task(repo / "agent_tasks" / "QUEUE", "AOD-001", "READY", 110, "base_branch: missing-base")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "queue")
    monkeypatch.setattr(dispatcher, "discover_agents", lambda: _agents())

    with pytest.raises(dispatcher.DispatcherBlocked, match="BASE_BRANCH_UNRESOLVABLE"):
        dispatcher.plan_dispatch(repo, "dry-run")


def test_local_valid_base_branch_passes_when_ancestor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _init_repo(tmp_path)
    _write_task(repo / "agent_tasks" / "QUEUE", "AOD-001", "READY", 110, "base_branch: master")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "queue")
    monkeypatch.setattr(dispatcher, "discover_agents", lambda: _agents())

    _, _, _, plan = dispatcher.plan_dispatch(repo, "dry-run")

    assert plan.outcome == "DRY_RUN"
    assert plan.selected_task is not None
    assert plan.selected_task.id == "AOD-001"


def test_origin_base_branch_satisfies_declared_base_when_local_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _init_repo(tmp_path)
    _git(repo, "update-ref", "refs/remotes/origin/release-base", _head(repo))
    _write_task(repo / "agent_tasks" / "QUEUE", "AOD-001", "READY", 110, "base_branch: release-base")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "queue")
    monkeypatch.setattr(dispatcher, "discover_agents", lambda: _agents())

    _, _, _, plan = dispatcher.plan_dispatch(repo, "dry-run")

    assert plan.outcome == "DRY_RUN"
    assert plan.selected_task is not None
    assert plan.selected_task.id == "AOD-001"


def test_non_ancestor_base_branch_blocks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _init_repo(tmp_path)
    _git(repo, "checkout", "-b", "otherbase")
    (repo / "base_only.txt").write_text("base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base-only")
    _git(repo, "checkout", "master")
    _write_task(repo / "agent_tasks" / "QUEUE", "AOD-001", "READY", 110, "base_branch: otherbase")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "queue")
    monkeypatch.setattr(dispatcher, "discover_agents", lambda: _agents())

    with pytest.raises(dispatcher.DispatcherBlocked, match="BASE_BRANCH_MISMATCH"):
        dispatcher.plan_dispatch(repo, "dry-run")


def test_dispatch_instruction_does_not_grant_restricted_authority(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _init_repo(tmp_path)
    _write_task(repo / "agent_tasks" / "QUEUE", "AOD-001", "READY", 110)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "queue")
    monkeypatch.setattr(dispatcher, "discover_agents", lambda: _agents())

    _, _, _, plan = dispatcher.plan_dispatch(repo, "dry-run")
    command = " ".join(plan.launch_command or ())

    assert "commit, push, merge, and independent-review gates" in command
    assert "Do not enable live trading" in command
    assert "unless the task explicitly grants that authority" in command


def test_review_mode_prefers_different_agent_family(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _init_repo(tmp_path)
    _write_task(repo / "agent_tasks" / "REVIEW", "AOD-001", "REVIEW", 110)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "review")
    monkeypatch.setattr(dispatcher, "discover_agents", lambda: _agents())

    _, _, _, plan = dispatcher.plan_dispatch(repo, "review", implementation_family="codex")

    assert plan.selected_agent is not None
    assert plan.selected_agent.agent_id == "claude"


def test_antigravity_gui_only_is_not_launch_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dispatcher.shutil, "which", lambda name: None)
    monkeypatch.setattr(dispatcher, "_detect_antigravity_app", lambda: "C:/Program Files/Google/Antigravity/Antigravity.exe")

    agents = {agent.agent_id: agent for agent in dispatcher.discover_agents()}

    assert agents["antigravity"].status == "GUI_ONLY"
    assert agents["antigravity"].launch_supported is False


def test_audit_output_redacts_obvious_secrets(tmp_path: Path) -> None:
    git_state = dispatcher.GitState(str(tmp_path), "main", "abc", "origin/main", 0, 0, (), (), (), False, False, False)
    queue_state = dispatcher.QueueState((), (), ())
    task = dispatcher.Task("AOD-001", "READY", 110, "task.md", {"id": "AOD-001", "status": "READY", "priority": "110"})
    agent = dispatcher.AgentStatus("codex", "codex", "AVAILABLE", "codex", "1", True, "test")
    plan = dispatcher.DispatchPlan("dry-run", task, agent, ("codex", "exec", "API_TOKEN=should_not_leak"), "DRY_RUN")

    path = dispatcher.write_audit(tmp_path / "audit", "dry-run", git_state, queue_state, plan, "DRY_RUN")
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert "should_not_leak" not in json.dumps(payload)
    assert payload["launch_command"][-1] == "API_TOKEN=<REDACTED>"
    _assert_complete_audit_git(payload, git_state)
    _assert_audit_queue_ids(payload, ready=[], active=[], review=[])


def test_status_audit_persists_ready_active_and_review_queue_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _init_repo(tmp_path)
    _write_task(repo / "agent_tasks" / "QUEUE", "AOD-001", "READY", 110)
    _write_task(repo / "agent_tasks" / "ACTIVE", "AOD-002", "ACTIVE", 100)
    _write_task(repo / "agent_tasks" / "REVIEW", "AOD-003", "REVIEW", 90)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "queue-state")
    audit_dir = tmp_path / "audit"
    monkeypatch.setattr(dispatcher, "discover_agents", lambda: _agents())

    result = dispatcher.main(["status", "--repo", str(repo), "--audit-dir", str(audit_dir)])

    payload = _latest_audit(audit_dir)
    assert result == 0
    assert payload["outcome"] == "OK"
    _assert_audit_queue_ids(payload, ready=["AOD-001"], active=["AOD-002"], review=["AOD-003"])
    assert payload["queue"]["ready_tasks"][0]["status"] == "READY"
    assert payload["queue"]["active_tasks"][0]["status"] == "ACTIVE"
    assert payload["queue"]["review_tasks"][0]["status"] == "REVIEW"


def test_successful_dry_run_audit_persists_complete_git_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _init_repo(tmp_path)
    _write_task(repo / "agent_tasks" / "QUEUE", "AOD-001", "READY", 110)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "queue")
    _set_upstream_to_current_head(repo)
    expected_git_state = dispatcher.inspect_git_state(repo)
    audit_dir = tmp_path / "audit"
    monkeypatch.setattr(dispatcher, "discover_agents", lambda: _agents())

    result = dispatcher.main(["dry-run", "--repo", str(repo), "--audit-dir", str(audit_dir)])

    payload = _latest_audit(audit_dir)
    assert result == 0
    assert payload["outcome"] == "DRY_RUN"
    _assert_complete_audit_git(payload, expected_git_state)
    _assert_audit_queue_ids(payload, ready=["AOD-001"], active=[], review=[])


def test_dispatcher_scope_does_not_touch_trading_execution_modules() -> None:
    scoped_files = {
        "tools/agent_dispatcher.py",
        "tools/agent_dispatcher.ps1",
        "docs/AGENT_DISPATCHER.md",
        "tests/test_agent_dispatcher.py",
    }

    assert not any(path.startswith(("backend/app/risk/", "backend/governance/", "engine/risk/")) for path in scoped_files)
