from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import scripts.run_48h_paper_marathon as wrapper


@dataclass(frozen=True)
class FakeReadinessReport:
    go_no_go: str

    def to_dict(self):
        return {"go_no_go": self.go_no_go}


@dataclass(frozen=True)
class FakeCertificationReport:
    go_no_go: str = "GO"

    def to_dict(self):
        return {"go_no_go": self.go_no_go, "certification_status": self.go_no_go}


@dataclass(frozen=True)
class FakeRunnerResult:
    snapshots: tuple[dict, ...]
    stop_reason: str | None
    certification_report: FakeCertificationReport

    def to_dict(self):
        return {
            "snapshots": list(self.snapshots),
            "stop_reason": self.stop_reason,
            "certification_report": self.certification_report.to_dict(),
        }


class FakeReadiness:
    state = "GO"

    def __init__(self, *args, **kwargs):
        pass

    def certify(self):
        return FakeReadinessReport(self.state)


class FakeRunner:
    started_cycles: int | None = None

    def __init__(self, *args, **kwargs):
        pass

    def start(self, *, cycles: int):
        FakeRunner.started_cycles = cycles
        return FakeRunnerResult(
            snapshots=({"cycle": 1},),
            stop_reason=None,
            certification_report=FakeCertificationReport("GO"),
        )


def _write_config(path: Path, *, mode: str = "paper", environment: str = "practice"):
    path.write_text(
        json.dumps({"system": {"mode": mode}, "oanda": {"environment": environment}}, indent=2),
        encoding="utf-8",
    )


def test_smoke_duration_accepted(tmp_path, monkeypatch) -> None:
    config = tmp_path / "config.json"
    _write_config(config)

    FakeReadiness.state = "GO"
    FakeRunner.started_cycles = None
    monkeypatch.setattr(wrapper, "MarathonReadiness", FakeReadiness)
    monkeypatch.setattr(wrapper, "MarathonRunner", FakeRunner)

    code = wrapper.execute(
        [
            "--duration-minutes",
            "0",
            "--cycle-interval-seconds",
            "1",
            "--config-path",
            str(config),
            "--artifact-root",
            str(tmp_path / "artifacts"),
            "--dry-run",
        ]
    )

    assert code == 0


def test_readiness_no_go_prevents_start(tmp_path, monkeypatch) -> None:
    config = tmp_path / "config.json"
    _write_config(config)

    FakeReadiness.state = "NO_GO"
    FakeRunner.started_cycles = None
    monkeypatch.setattr(wrapper, "MarathonReadiness", FakeReadiness)
    monkeypatch.setattr(wrapper, "MarathonRunner", FakeRunner)

    code = wrapper.execute(
        [
            "--duration-minutes",
            "1",
            "--cycle-interval-seconds",
            "1",
            "--config-path",
            str(config),
            "--artifact-root",
            str(tmp_path / "artifacts"),
        ]
    )

    assert code == 2
    assert FakeRunner.started_cycles is None


def test_evidence_path_generated(tmp_path, monkeypatch) -> None:
    config = tmp_path / "config.json"
    _write_config(config)

    FakeReadiness.state = "GO"
    monkeypatch.setattr(wrapper, "MarathonReadiness", FakeReadiness)
    monkeypatch.setattr(wrapper, "MarathonRunner", FakeRunner)

    artifact_root = tmp_path / "artifacts"
    code = wrapper.execute(
        [
            "--duration-minutes",
            "0",
            "--cycle-interval-seconds",
            "1",
            "--config-path",
            str(config),
            "--artifact-root",
            str(artifact_root),
            "--dry-run",
        ]
    )

    assert code == 0
    run_dirs = [entry for entry in artifact_root.iterdir() if entry.is_dir()]
    assert run_dirs
    report = run_dirs[0] / "readiness_report.json"
    assert report.exists()


def test_paper_mode_enforced(tmp_path, monkeypatch) -> None:
    config = tmp_path / "config.json"
    _write_config(config, mode="live", environment="live")

    FakeReadiness.state = "GO"
    FakeRunner.started_cycles = None
    monkeypatch.setattr(wrapper, "MarathonReadiness", FakeReadiness)
    monkeypatch.setattr(wrapper, "MarathonRunner", FakeRunner)

    code = wrapper.execute(
        [
            "--duration-minutes",
            "1",
            "--cycle-interval-seconds",
            "1",
            "--config-path",
            str(config),
            "--artifact-root",
            str(tmp_path / "artifacts"),
        ]
    )

    assert code == 1
    assert FakeRunner.started_cycles is None


def test_final_report_generated(tmp_path, monkeypatch) -> None:
    config = tmp_path / "config.json"
    _write_config(config)

    FakeReadiness.state = "GO"
    FakeRunner.started_cycles = None
    monkeypatch.setattr(wrapper, "MarathonReadiness", FakeReadiness)
    monkeypatch.setattr(wrapper, "MarathonRunner", FakeRunner)

    artifact_root = tmp_path / "artifacts"
    code = wrapper.execute(
        [
            "--duration-minutes",
            "1",
            "--cycle-interval-seconds",
            "60",
            "--config-path",
            str(config),
            "--artifact-root",
            str(artifact_root),
        ]
    )

    assert code == 0
    run_dirs = sorted([entry for entry in artifact_root.iterdir() if entry.is_dir()])
    assert run_dirs
    final_report = run_dirs[-1] / "final_certification_report.json"
    assert final_report.exists()
    payload = json.loads(final_report.read_text(encoding="utf-8"))
    assert payload["go_no_go"] == "GO"
