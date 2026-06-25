from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from math import ceil
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.validation.marathon_readiness import MarathonReadiness
from backend.validation.marathon_runner import MarathonRunner


DEFAULT_CONFIG_PATH = REPOSITORY_ROOT / "config.json"
DEFAULT_ARTIFACT_ROOT = REPOSITORY_ROOT / "artifacts" / "marathon"


class MarathonExecutionPrepError(RuntimeError):
    """Fail-closed exception for V2C execution wrapper failures."""


@dataclass(frozen=True)
class ExecutionSettings:
    duration_minutes: float
    cycle_interval_seconds: float
    dry_run: bool
    config_path: Path
    artifact_root: Path


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp() -> str:
    return _utc_now().strftime("%Y%m%dT%H%M%SZ")


def _load_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise MarathonExecutionPrepError(f"config not found: {config_path}")
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise MarathonExecutionPrepError(f"config unreadable: {exc}") from exc
    if not isinstance(payload, dict):
        raise MarathonExecutionPrepError("config must be a JSON object")
    return payload


def _paper_practice_enabled(config_payload: dict[str, Any]) -> bool:
    system = config_payload.get("system", {})
    oanda = config_payload.get("oanda", {})
    mode = str(system.get("mode") or "").strip().lower()
    environment = str(oanda.get("environment") or "").strip().lower()

    if mode == "live":
        return False
    return environment in {"practice", "paper", "demo"}


def _enforce_paper_practice_mode(config_payload: dict[str, Any]) -> None:
    if not _paper_practice_enabled(config_payload):
        raise MarathonExecutionPrepError("live mode detected; refusing marathon execution")


def _resolve_settings(args: argparse.Namespace) -> ExecutionSettings:
    duration_minutes = float(args.duration_minutes) if args.duration_minutes is not None else float(args.duration_hours) * 60.0
    cycle_interval_seconds = float(args.cycle_interval_seconds)
    if duration_minutes < 0.0:
        raise MarathonExecutionPrepError("duration must be >= 0")
    if cycle_interval_seconds <= 0.0:
        raise MarathonExecutionPrepError("cycle interval must be > 0")

    return ExecutionSettings(
        duration_minutes=duration_minutes,
        cycle_interval_seconds=cycle_interval_seconds,
        dry_run=bool(args.dry_run),
        config_path=Path(args.config_path).resolve(),
        artifact_root=Path(args.artifact_root).resolve(),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="V2C wrapper for 48-hour paper marathon certification execution prep")
    parser.add_argument("--duration-hours", type=float, default=48.0, help="Target run duration in hours (default: 48)")
    parser.add_argument("--duration-minutes", type=float, default=None, help="Override duration in minutes for smoke tests")
    parser.add_argument("--cycle-interval-seconds", type=float, default=60.0, help="Seconds between validation cycles")
    parser.add_argument("--artifact-root", default=str(DEFAULT_ARTIFACT_ROOT), help="Artifact root directory")
    parser.add_argument("--config-path", default=str(DEFAULT_CONFIG_PATH), help="Path to config.json")
    parser.add_argument("--dry-run", action="store_true", help="Prepare evidence and readiness outputs without executing cycles")
    return parser


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _plan_cycles(duration_minutes: float, cycle_interval_seconds: float) -> int:
    if duration_minutes <= 0.0:
        return 1
    return max(1, int(ceil((duration_minutes * 60.0) / cycle_interval_seconds)))


def execute(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        settings = _resolve_settings(args)
        config_payload = _load_config(settings.config_path)
        _enforce_paper_practice_mode(config_payload)

        run_id = _timestamp()
        run_dir = settings.artifact_root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        print(f"STARTED 48-hour paper marathon wrapper run_id={run_id}")

        readiness = MarathonReadiness(
            repository_root=REPOSITORY_ROOT,
            config_path=settings.config_path,
        )
        readiness_report = readiness.certify()
        readiness_payload = readiness_report.to_dict() if hasattr(readiness_report, "to_dict") else asdict(readiness_report)
        _write_json(run_dir / "readiness_report.json", readiness_payload)

        execution_plan = {
            "run_id": run_id,
            "duration_minutes": settings.duration_minutes,
            "cycle_interval_seconds": settings.cycle_interval_seconds,
            "planned_cycles": _plan_cycles(settings.duration_minutes, settings.cycle_interval_seconds),
            "dry_run": settings.dry_run,
            "artifact_dir": str(run_dir),
            "config_path": str(settings.config_path),
            "paper_practice_enforced": True,
        }
        _write_json(run_dir / "execution_plan.json", execution_plan)

        if readiness_report.go_no_go != "GO":
            print("FAILED readiness status is not GO")
            return 2

        if settings.dry_run:
            dry_run_report = {
                "run_id": run_id,
                "certification_status": "DRY_RUN",
                "go_no_go": "GO",
                "stop_reason": "DRY_RUN",
                "readiness_status": readiness_report.go_no_go,
                "planned_cycles": execution_plan["planned_cycles"],
            }
            _write_json(run_dir / "final_certification_report.json", dry_run_report)
            print("STOPPED dry-run completed with no cycle execution")
            print("CERTIFIED DRY_RUN")
            return 0

        runner = MarathonRunner(
            readiness=readiness,
            checkpoint_path=run_dir / "marathon_checkpoint.json",
            cycle_interval_seconds=settings.cycle_interval_seconds,
            paper_mode_probe=lambda: _paper_practice_enabled(_load_config(settings.config_path)),
        )
        planned_cycles = execution_plan["planned_cycles"]
        result = runner.start(cycles=planned_cycles)

        result_payload = result.to_dict() if hasattr(result, "to_dict") else asdict(result)
        _write_json(run_dir / "marathon_run_result.json", result_payload)

        certification_payload = (
            result.certification_report.to_dict()
            if hasattr(result.certification_report, "to_dict")
            else asdict(result.certification_report)
        )
        _write_json(run_dir / "final_certification_report.json", certification_payload)

        print(f"STOPPED cycles_completed={len(result.snapshots)} stop_reason={result.stop_reason or 'COMPLETED'}")
        print(f"CERTIFIED {result.certification_report.go_no_go}")

        return 0 if result.certification_report.go_no_go in {"GO", "CONDITIONAL_GO"} else 3
    except Exception as exc:
        print(f"FAILED {exc}")
        return 1


def main() -> int:
    return execute()


if __name__ == "__main__":
    raise SystemExit(main())
