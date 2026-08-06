"""OV002-R1-R1 continuity controls: attempt state, process identity, critical ledger, final certification.

Builds on ov002_persistence atomic writes and single-writer locks. Does not enable live trading.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from backend.certification.ov002_persistence import (
    PersistenceError,
    WriterLockError,
    atomic_append_jsonl,
    locked_atomic_write_json,
    read_json_object,
    strict_json_loads,
)

# Monotonic attempt states. INVALIDATED is terminal for the attempt.
STATE_INITIALIZING = "INITIALIZING"
STATE_RUNNING = "RUNNING"
STATE_INVALIDATED = "INVALIDATED"
STATE_COMPLETED_ELIGIBLE = "COMPLETED_ELIGIBLE"
STATE_CERTIFIED = "CERTIFIED"
STATE_NOT_CERTIFIED = "NOT_CERTIFIED"

KNOWN_ATTEMPT_STATES = frozenset(
    {
        STATE_INITIALIZING,
        STATE_RUNNING,
        STATE_INVALIDATED,
        STATE_COMPLETED_ELIGIBLE,
        STATE_CERTIFIED,
        STATE_NOT_CERTIFIED,
    }
)

TERMINAL_STATES = frozenset({STATE_INVALIDATED, STATE_CERTIFIED, STATE_NOT_CERTIFIED})

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    STATE_INITIALIZING: frozenset({STATE_RUNNING, STATE_INVALIDATED, STATE_NOT_CERTIFIED}),
    STATE_RUNNING: frozenset({STATE_INVALIDATED, STATE_COMPLETED_ELIGIBLE}),
    STATE_COMPLETED_ELIGIBLE: frozenset({STATE_NOT_CERTIFIED, STATE_CERTIFIED}),
    STATE_INVALIDATED: frozenset(),
    STATE_CERTIFIED: frozenset(),
    STATE_NOT_CERTIFIED: frozenset(),
}

PROCESS_IDENTITY_SCHEMA = "css.ov002.process_identity.v2"
ATTEMPT_STATE_SCHEMA = "css.ov002.attempt_state.v2"
CRITICAL_LEDGER_SCHEMA = "css.ov002.critical_events.v1"
PROCESS_IDENTITY_RECONCILIATION_SCHEMA = "css.ov002.process_identity_reconciliation.v1"
MAX_CANONICAL_PROCESS_PID = (2**32) - 1

PROCESS_IDENTITY_EVIDENCE_FILENAME = "PROCESS_IDENTITY.json"

# Live OS facts that must be observed directly when strong identity is required.
REQUIRED_LIVE_IDENTITY_FIELDS = (
    "pid",
    "parent_pid",
    "creation_time",
    "executable_path",
    "executable_sha256",
    "command_line",
)

IDENTITY_RECORD_FIELDS = frozenset(
    {
        "schema_version",
        "pid",
        "parent_pid",
        "creation_time",
        "executable_path",
        "executable_identity",
        "executable_sha256",
        "command_identity",
        "command_sha256",
        "repo_root",
        "service_role",
        "attempt_id",
        "baseline_commit",
    }
)

IDENTITY_DOCUMENT_OPTIONAL_FIELDS = frozenset(
    {
        "supervisor_id",
        "started_at",
        "process_generation",
        "launcher_pid",
        "supervisor_pid",
        "failure_history_path",
        "frozen_at_utc",
        "note",
    }
)

ALERT_SCAN_MAX_FILES = 100_000
ALERT_SCAN_MAX_BYTES = 256 * 1024 * 1024

IdentityProbe = Callable[[int], dict[str, Any] | None]

_SECRET_PATTERNS = (
    re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*\S+"),
    re.compile(r"(?i)(token|secret|api_key|apikey|authorization)\s*[:=]\s*\S+"),
    re.compile(r"(?i)(Bearer\s+)\S+"),
)

_PATHISH_PATTERN = re.compile(
    r"(?i)([a-z]:\\[^\s\"']+|/[^\s\"']+)",
)


class ContinuityError(ValueError):
    def __init__(self, code: str, detail: Optional[str] = None) -> None:
        self.code = code
        self.detail = detail
        super().__init__(code if detail is None else f"{code}:{detail}")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256_normcase(text: str) -> str:
    normalized = os.path.normcase(str(text or "").strip())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _sha256_file(path: str | Path | None) -> str | None:
    if not path:
        return None
    try:
        hasher = hashlib.sha256()
        with open(path, "rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(block)
        return hasher.hexdigest()
    except OSError:
        return None


def _is_sha256_hex(value: Any) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-fA-F]{64}", value.strip()))


def _is_lower_sha256_hex(value: Any) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{64}", value))


def _strict_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def canonical_process_pid_error(value: Any) -> str | None:
    if type(value) is not int:
        return "malformed"
    if value <= 0 or value > MAX_CANONICAL_PROCESS_PID:
        return "out_of_range"
    return None


def canonical_process_pid(value: Any) -> int | None:
    return int(value) if canonical_process_pid_error(value) is None else None


def _require_canonical_process_pid(value: Any, *, field: str) -> int:
    error = canonical_process_pid_error(value)
    if error:
        raise ContinuityError(f"{field}_{error}", str(value))
    return int(value)


def _canonical_parent_process_pid(value: Any, *, field: str = "parent_pid") -> int | None:
    if value is None:
        return None
    error = canonical_process_pid_error(value)
    if error:
        raise ContinuityError(f"{field}_{error}", str(value))
    return int(value)


def _strict_nonempty_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _canonical_payload_digest(value: Mapping[str, Any] | None) -> str:
    return hashlib.sha256(
        json.dumps(value or {}, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _executable_identity_value(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if _is_sha256_hex(text):
        return text.lower()
    return _sha256_normcase(text)


def _same_int(left: Any, right: Any) -> bool:
    try:
        return _require_int(left, field="left") == _require_int(right, field="right")
    except ContinuityError:
        return False


def _same_creation(left: Any, right: Any) -> bool:
    try:
        return _parse_creation_time(left) == _parse_creation_time(right)
    except ContinuityError:
        return False


def _same_executable_identity(left: Any, right: Any) -> bool:
    if left in (None, "") or right in (None, ""):
        return False
    return _executable_identity_value(left) == _executable_identity_value(right)


def _same_command_identity(left: Any, right: Any) -> bool:
    return safe_command_identity(str(left or "")) == safe_command_identity(str(right or ""))


def _validate_required_live_probe(live: Mapping[str, Any], *, expected_pid: int) -> None:
    pid_error = canonical_process_pid_error(live.get("pid"))
    if pid_error:
        raise ContinuityError("identity_probe_field_malformed", f"pid:{pid_error}")
    pid = canonical_process_pid(live.get("pid"))
    if pid != expected_pid:
        raise ContinuityError("identity_probe_pid_mismatch", str(expected_pid))
    parent_error = canonical_process_pid_error(live.get("parent_pid"))
    if parent_error:
        raise ContinuityError("identity_probe_field_malformed", f"parent_pid:{parent_error}")
    creation = _strict_nonempty_string(live.get("creation_time"))
    if creation is None:
        raise ContinuityError("identity_probe_field_malformed", "creation_time")
    _parse_creation_time(creation)
    if _strict_nonempty_string(live.get("executable_path")) is None:
        raise ContinuityError("identity_probe_field_malformed", "executable_path")
    exe_hash = live.get("executable_sha256")
    if not _is_lower_sha256_hex(exe_hash):
        raise ContinuityError("identity_probe_field_malformed", "executable_sha256")
    if _strict_nonempty_string(live.get("command_line")) is None:
        raise ContinuityError("identity_probe_field_malformed", "command_line")
    for optional_hash in ("command_sha256", "command_hash"):
        if optional_hash in live and live.get(optional_hash) not in (None, ""):
            if not _is_lower_sha256_hex(live.get(optional_hash)):
                raise ContinuityError("identity_probe_field_malformed", optional_hash)


def transition_attempt_state(current: str, target: str) -> str:
    """Enforce monotonic attempt transitions. INVALIDATED cannot return to RUNNING."""
    cur = str(current or "").upper()
    nxt = str(target or "").upper()
    if cur == nxt:
        return cur
    if cur == STATE_INVALIDATED:
        raise ContinuityError("invalidated_terminal", f"cannot leave {cur}")
    if cur in TERMINAL_STATES:
        raise ContinuityError("terminal_state_immutable", f"{cur}->{nxt}")
    allowed = ALLOWED_TRANSITIONS.get(cur)
    if allowed is None:
        raise ContinuityError("unknown_attempt_state", cur)
    if nxt not in allowed:
        raise ContinuityError("illegal_attempt_transition", f"{cur}->{nxt}")
    return nxt


def _require_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool):
        raise ContinuityError("malformed_integer", field)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value != int(value):
            raise ContinuityError("malformed_integer", field)
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ContinuityError("malformed_integer", field)
        try:
            return int(text, 10)
        except ValueError as exc:
            raise ContinuityError("malformed_integer", field) from exc
    raise ContinuityError("malformed_integer", field)


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return _require_int(value, field="optional")
    except ContinuityError:
        return None


def _parse_creation_time(value: Any) -> str | None:
    """Parse ISO-8601 or CIM Win32 CreationDate (e.g. 20260804120000.000000-240)."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.replace(microsecond=0).isoformat()
    text = str(value).strip()
    if not text:
        return None

    dotnet_json_match = re.fullmatch(r"/Date\((-?\d+)(?:[+-]\d{4})?\)/", text)
    if dotnet_json_match:
        millis = int(dotnet_json_match.group(1))
        return datetime.fromtimestamp(millis / 1000, tz=timezone.utc).replace(microsecond=0).isoformat()

    cim_match = re.fullmatch(
        r"(\d{14})(?:\.(\d+))?([+-]\d+)?",
        text.replace(" ", ""),
    )
    if cim_match:
        base, frac, offset = cim_match.groups()
        try:
            dt = datetime.strptime(base, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        except ValueError as exc:
            raise ContinuityError("identity_creation_time_malformed", text) from exc
        if frac:
            micro = frac[:6].ljust(6, "0")
            dt = dt.replace(microsecond=int(micro))
        if offset:
            try:
                minutes = int(offset)
                dt = dt - timedelta(minutes=minutes)
            except ValueError as exc:
                raise ContinuityError("identity_creation_time_malformed", text) from exc
        return dt.replace(microsecond=dt.microsecond).isoformat()

    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContinuityError("identity_creation_time_malformed", text) from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def canonical_process_creation_time(value: Any) -> str | None:
    if not isinstance(value, (str, datetime)):
        return None
    try:
        return _parse_creation_time(value)
    except ContinuityError:
        return None


def safe_command_identity(command: str | None) -> str:
    """Redact secrets; hash path-like segments with sha256(normcase). Never store raw secrets."""
    text = str(command or "")

    def _redact_secret(match: re.Match[str]) -> str:
        fragment = match.group(0)
        if fragment.lower().startswith("bearer "):
            return "Bearer [REDACTED]"
        if "=" in fragment or ":" in fragment:
            key = re.split(r"[:=]", fragment, maxsplit=1)[0]
            return f"{key}=[REDACTED]"
        return "[REDACTED]"

    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(_redact_secret, text)

    def _hash_path(match: re.Match[str]) -> str:
        return f"path_sha256:{_sha256_normcase(match.group(1))}"

    text = _PATHISH_PATTERN.sub(_hash_path, text)
    return text.strip()


def command_identity_hash(command_identity: str) -> str:
    return hashlib.sha256(str(command_identity or "").encode("utf-8")).hexdigest()


def default_identity_probe(pid: int) -> dict[str, Any] | None:
    """Best-effort live process probe. Returns None on failure (fail closed upstream)."""
    try:
        pid_i = _require_int(pid, field="pid")
    except ContinuityError:
        return None

    if os.name == "nt":
        script = (
            f"$p1 = Get-CimInstance Win32_Process -Filter \"ProcessId={pid_i}\" -ErrorAction SilentlyContinue; "
            "if ($null -eq $p1) { exit 2 }; "
            "$creation1 = $p1.CreationDate; "
            "$p2 = Get-CimInstance Win32_Process -Filter \"ProcessId=$($p1.ProcessId)\" -ErrorAction SilentlyContinue; "
            "if ($null -eq $p2) { exit 3 }; "
            "$obj = [pscustomobject]@{"
            "ProcessId=$p2.ProcessId;"
            "ParentProcessId=$p2.ParentProcessId;"
            "CreationDate=$creation1;"
            "RecheckCreationDate=$p2.CreationDate;"
            "ExecutablePath=$p2.ExecutablePath;"
            "CommandLine=$p2.CommandLine"
            "}; "
            "$obj | "
            "ConvertTo-Json -Compress"
        )
        try:
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                capture_output=True,
                text=True,
                check=False,
                timeout=20,
            )
        except Exception:
            return None
        if completed.returncode != 0:
            return None
        raw = (completed.stdout or "").strip()
        if not raw:
            return None
        try:
            row = strict_json_loads(raw, source="process_identity_probe")
        except PersistenceError:
            return None
        if not isinstance(row, dict):
            return None
        creation = _parse_creation_time(row.get("CreationDate"))
        recheck_creation = _parse_creation_time(row.get("RecheckCreationDate"))
        if _optional_int(row.get("ProcessId")) != pid_i or creation != recheck_creation:
            return None
        executable = row.get("ExecutablePath")
        return {
            "pid": _optional_int(row.get("ProcessId")),
            "parent_pid": _optional_int(row.get("ParentProcessId")),
            "creation_time": creation,
            "executable_path": executable,
            "executable_sha256": _sha256_file(executable),
            "command_line": row.get("CommandLine"),
        }

    try:
        completed = subprocess.run(
            ["ps", "-p", str(pid_i), "-o", "pid=,ppid=,lstart=,command="],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except Exception:
        return None
    if completed.returncode != 0:
        return None
    line = (completed.stdout or "").strip()
    if not line:
        return None
    parts = line.split(None, 3)
    if len(parts) < 4:
        return None
    # POSIX path remains best-effort; authoritative tests exercise Windows path on this host.
    creation = None
    return {
        "pid": _optional_int(parts[0]),
        "parent_pid": _optional_int(parts[1]),
        "creation_time": creation,
        "executable_path": None,
        "command_line": parts[3] if len(parts) > 3 else "",
    }


def build_process_identity_record(
    *,
    pid: int,
    role: str,
    attempt_id: str,
    baseline_commit: str,
    repo_root: str | Path,
    parent_pid: int | None = None,
    creation_time: str | None = None,
    executable_path: str | None = None,
    executable_sha256: str | None = None,
    command_line: str | None = None,
    probe: IdentityProbe | None = None,
    require_live_fields: bool = False,
) -> dict[str, Any]:
    """Build one strong process identity record. Fail closed when live fields required but missing."""
    pid_i = _require_canonical_process_pid(pid, field="pid")
    parent_role = str(role or "process").replace(" ", "_")
    if parent_pid is not None:
        _canonical_parent_process_pid(parent_pid, field=f"{parent_role}_parent_pid")
    active_probe = probe
    if require_live_fields and active_probe is None:
        active_probe = default_identity_probe
    live = active_probe(pid_i) if active_probe is not None else None
    if require_live_fields:
        if not isinstance(live, Mapping):
            raise ContinuityError("identity_probe_unavailable", str(pid_i))
        if not live:
            raise ContinuityError("identity_probe_empty", str(pid_i))
        incomplete = [
            field for field in REQUIRED_LIVE_IDENTITY_FIELDS if live.get(field) in (None, "")
        ]
        if incomplete:
            raise ContinuityError("identity_probe_incomplete", ",".join(incomplete))
        _validate_required_live_probe(live, expected_pid=pid_i)
    if isinstance(live, Mapping) and live:
        supplied_checks = (
            ("parent_pid", parent_pid, live.get("parent_pid"), _same_int),
            ("creation_time", creation_time, live.get("creation_time"), _same_creation),
            ("executable_path", executable_path, live.get("executable_path"), _same_executable_identity),
            ("executable_sha256", executable_sha256, live.get("executable_sha256"), lambda a, b: str(a) == str(b)),
            ("command_line", command_line, live.get("command_line"), _same_command_identity),
        )
        for field, supplied, observed, comparator in supplied_checks:
            if supplied not in (None, "") and not comparator(supplied, observed):
                raise ContinuityError("identity_supplied_field_mismatch", field)
        parent_pid = live.get("parent_pid")
        creation_time = live.get("creation_time")
        executable_path = live.get("executable_path")
        executable_sha256 = live.get("executable_sha256")
        command_line = live.get("command_line")

    parsed_creation = _parse_creation_time(creation_time)
    parent = _canonical_parent_process_pid(parent_pid, field=f"{parent_role}_parent_pid")
    exe_identity = _executable_identity_value(executable_path)
    exe_sha = str(executable_sha256 or _sha256_file(executable_path) or "")
    command_identity = safe_command_identity(command_line)
    command_sha = command_identity_hash(command_identity) if command_identity else ""

    missing: list[str] = []
    if parent is None:
        missing.append("parent_pid")
    if not parsed_creation:
        missing.append("creation_time")
    if not exe_identity:
        missing.append("executable_identity")
    if not exe_sha:
        missing.append("executable_sha256")
    if not command_identity and command_line is None:
        missing.append("command_identity")
    if not command_sha:
        missing.append("command_sha256")
    if require_live_fields and missing:
        raise ContinuityError("process_identity_live_fields_missing", ",".join(missing))

    return {
        "schema_version": PROCESS_IDENTITY_SCHEMA,
        "pid": pid_i,
        "parent_pid": parent,
        "creation_time": parsed_creation,
        "executable_path": exe_identity,
        "executable_identity": exe_identity,
        "executable_sha256": exe_sha or None,
        "command_identity": command_identity,
        "command_sha256": command_sha or None,
        "repo_root": str(repo_root or ""),
        "service_role": str(role or ""),
        "attempt_id": str(attempt_id or ""),
        "baseline_commit": str(baseline_commit or ""),
    }


def _service_record_from_observed(
    *,
    pid: int | None,
    role: str,
    attempt_id: str,
    baseline_commit: str,
    repo_root: str | Path,
    probe: IdentityProbe | None,
    require_live_fields: bool,
) -> dict[str, Any]:
    if pid is None:
        raise ContinuityError("process_identity_pid_missing", role)
    return build_process_identity_record(
        pid=pid,
        role=role,
        attempt_id=attempt_id,
        baseline_commit=baseline_commit,
        repo_root=repo_root,
        probe=probe,
        require_live_fields=require_live_fields,
    )


def freeze_process_identity(
    supervisor_state: Mapping[str, Any],
    *,
    attempt_id: str = "",
    baseline_commit: str = "",
    repo_root: str | Path = "",
    probe: IdentityProbe | None = None,
    require_live_fields: bool = False,
) -> dict[str, Any]:
    """Capture expected process-tree identity from supervisor state (not from HTTP)."""
    identity = supervisor_state.get("process_identity")
    if not isinstance(identity, Mapping):
        raise ContinuityError("process_identity_missing")

    launcher_pid = canonical_process_pid(identity.get("launcher_pid"))
    supervisor_pid = canonical_process_pid(identity.get("supervisor_pid"))
    if launcher_pid is None or supervisor_pid is None:
        raise ContinuityError("process_identity_pid_missing")

    # Never auto-probe unless required or an explicit probe is supplied (keeps tests offline).
    active_probe: IdentityProbe | None = probe
    if require_live_fields and active_probe is None:
        active_probe = default_identity_probe
    managed_raw = identity.get("managed_services")
    managed_services: dict[str, Any] = {}
    if isinstance(managed_raw, Mapping):
        for name, info in managed_raw.items():
            if not isinstance(info, Mapping):
                raise ContinuityError("process_identity_service_malformed", str(name))
            svc_pid = canonical_process_pid(info.get("pid"))
            if svc_pid is None:
                if "pid" in info:
                    error = canonical_process_pid_error(info.get("pid")) or "malformed"
                    raise ContinuityError(f"process_identity_service_pid_{error}", str(name))
                if require_live_fields:
                    raise ContinuityError("process_identity_service_pid_missing", str(name))
                continue
            managed_services[str(name)] = build_process_identity_record(
                pid=svc_pid,
                role=str(info.get("service_role") or info.get("role") or name),
                attempt_id=attempt_id,
                baseline_commit=baseline_commit,
                repo_root=repo_root,
                parent_pid=info.get("parent_pid") if "parent_pid" in info else None,
                creation_time=info.get("creation_time") or info.get("create_time"),
                executable_path=info.get("executable_path") or info.get("exe"),
                executable_sha256=info.get("executable_sha256"),
                command_line=info.get("command_line") or info.get("cmdline"),
                probe=active_probe,
                require_live_fields=require_live_fields,
            )

    launcher = build_process_identity_record(
        pid=launcher_pid,
        role="launcher",
        attempt_id=attempt_id,
        baseline_commit=baseline_commit,
        repo_root=repo_root,
        parent_pid=identity.get("launcher_parent_pid") if "launcher_parent_pid" in identity else None,
        creation_time=identity.get("launcher_creation_time"),
        executable_path=identity.get("launcher_executable_path"),
        executable_sha256=identity.get("launcher_executable_sha256"),
        command_line=identity.get("launcher_command_line"),
        probe=active_probe,
        require_live_fields=require_live_fields,
    )
    supervisor = build_process_identity_record(
        pid=supervisor_pid,
        role="supervisor",
        attempt_id=attempt_id,
        baseline_commit=baseline_commit,
        repo_root=repo_root,
        parent_pid=identity.get("supervisor_parent_pid") if "supervisor_parent_pid" in identity else None,
        creation_time=identity.get("supervisor_creation_time"),
        executable_path=identity.get("supervisor_executable_path"),
        executable_sha256=identity.get("supervisor_executable_sha256"),
        command_line=identity.get("supervisor_command_line"),
        probe=active_probe,
        require_live_fields=require_live_fields,
    )

    return {
        "schema_version": PROCESS_IDENTITY_SCHEMA,
        "attempt_id": str(attempt_id or ""),
        "baseline_commit": str(baseline_commit or ""),
        "repo_root": str(repo_root or ""),
        "supervisor_id": supervisor_state.get("supervisor_id"),
        "started_at": supervisor_state.get("started_at"),
        "process_generation": supervisor_state.get("process_generation"),
        "launcher": launcher,
        "supervisor": supervisor,
        "managed_services": managed_services,
        "launcher_pid": launcher_pid,
        "supervisor_pid": supervisor_pid,
        "failure_history_path": supervisor_state.get("failure_history_path"),
        "frozen_at_utc": _utc_now_iso(),
        "note": "HTTP /health on port 8765 is insufficient continuity evidence",
    }


def _compare_identity_record(
    label: str,
    expected: Mapping[str, Any],
    observed_pid: int | None,
    observed_detail: Mapping[str, Any] | None = None,
) -> list[str]:
    reasons: list[str] = []
    exp_pid = _optional_int(expected.get("pid"))
    if exp_pid is None:
        reasons.append(f"process_identity_{label}_pid_unavailable")
        return reasons
    if observed_pid is None:
        reasons.append(f"process_identity_{label}_unavailable")
        return reasons
    if exp_pid != observed_pid:
        if label.startswith("service:"):
            reasons.append(f"process_identity_service_pid_mismatch:{label.split(':', 1)[1]}")
        else:
            reasons.append(f"process_identity_{label}_mismatch")
        return reasons

    expected_role = str(expected.get("service_role") or label)
    expected_repo = str(expected.get("repo_root") or "")
    if isinstance(observed_detail, Mapping) and observed_detail.get("schema_version") != PROCESS_IDENTITY_SCHEMA:
        try:
            observed_detail = build_process_identity_record(
                pid=observed_pid,
                role=str(observed_detail.get("service_role") or observed_detail.get("role") or expected_role),
                attempt_id="",
                baseline_commit="",
                repo_root=observed_detail.get("repo_root") or expected_repo,
                parent_pid=observed_detail.get("parent_pid"),
                creation_time=observed_detail.get("creation_time") or observed_detail.get("create_time"),
                executable_path=observed_detail.get("executable_path") or observed_detail.get("exe"),
                executable_sha256=observed_detail.get("executable_sha256"),
                command_line=observed_detail.get("command_line") or observed_detail.get("cmdline"),
            )
        except Exception:
            pass

    if not isinstance(observed_detail, Mapping):
        # Expected strong freeze but observed lacks nested detail — only fail on live fields.
        for field in (
            "parent_pid",
            "creation_time",
            "executable_identity",
            "executable_sha256",
            "command_identity",
            "command_sha256",
        ):
            if expected.get(field) not in (None, ""):
                reasons.append(f"process_identity_{label}_{field}_unavailable")
        return reasons

    observed_strong = observed_detail.get("schema_version") == PROCESS_IDENTITY_SCHEMA
    compare_fields = (
        "parent_pid",
        "creation_time",
        "executable_path",
        "executable_identity",
        "executable_sha256",
        "command_identity",
        "command_sha256",
    )
    if observed_strong:
        compare_fields = compare_fields + (
            "repo_root",
            "service_role",
        )

    exp_creation = expected.get("creation_time")
    if exp_creation not in (None, ""):
        try:
            obs_creation = _parse_creation_time(observed_detail.get("creation_time"))
        except ContinuityError:
            reasons.append(f"process_identity_{label}_creation_time_malformed")
            return reasons
        if obs_creation is None:
            reasons.append(f"process_identity_{label}_creation_time_unavailable")
        elif exp_creation != obs_creation:
            reasons.append(f"process_identity_{label}_creation_time_mismatch")

    for field in compare_fields:
        if field == "creation_time":
            continue
        exp_val = expected.get(field)
        if exp_val in (None, ""):
            continue
        obs_val = observed_detail.get(field)
        if obs_val in (None, ""):
            reasons.append(f"process_identity_{label}_{field}_unavailable")
            continue
        if field == "parent_pid":
            try:
                if int(exp_val) != int(obs_val):
                    reasons.append(f"process_identity_{label}_{field}_mismatch")
            except (TypeError, ValueError):
                reasons.append(f"process_identity_{label}_{field}_malformed")
            continue
        if field == "repo_root":
            exp_root = os.path.normcase(os.path.abspath(str(exp_val)))
            obs_root = os.path.normcase(os.path.abspath(str(obs_val)))
            if exp_root != obs_root:
                reasons.append(f"process_identity_{label}_{field}_mismatch")
            continue
        if str(exp_val) != str(obs_val):
            reasons.append(f"process_identity_{label}_{field}_mismatch")

    return reasons


def validate_process_identity(
    *,
    frozen: Mapping[str, Any],
    observed_supervisor_state: Mapping[str, Any],
) -> list[str]:
    """Fail-closed process-tree checks. Port reachability is not used."""
    reasons: list[str] = []
    try:
        observed = observed_supervisor_state.get("process_identity")
        if not isinstance(observed, Mapping):
            reasons.append("process_identity_missing")
            return list(dict.fromkeys(reasons))
        if observed.get("process_identity_error"):
            reasons.append(f"process_identity_error:{observed.get('process_identity_error')}")

        duplicate_discovery = observed_supervisor_state.get("duplicate_discovery")
        if isinstance(duplicate_discovery, Mapping):
            if duplicate_discovery.get("ok") is False:
                reasons.append("duplicate_discovery_failed")
            owners = duplicate_discovery.get("owners")
            if isinstance(owners, Sequence) and owners:
                reasons.append("duplicate_canonical_runtime_owner")

        if observed_supervisor_state.get("duplicate_canonical_owners"):
            reasons.append("duplicate_canonical_runtime_owner")

        frozen_launcher = frozen.get("launcher") if isinstance(frozen.get("launcher"), Mapping) else None
        frozen_supervisor = frozen.get("supervisor") if isinstance(frozen.get("supervisor"), Mapping) else None
        obs_launcher_pid = _optional_int(observed.get("launcher_pid"))
        obs_supervisor_pid = _optional_int(observed.get("supervisor_pid"))

        if frozen_launcher:
            launcher_detail = observed.get("launcher")
            if not isinstance(launcher_detail, Mapping):
                launcher_detail = {
                    "parent_pid": observed.get("launcher_parent_pid"),
                    "creation_time": observed.get("launcher_creation_time"),
                    "executable_path": observed.get("launcher_executable_path"),
                    "executable_sha256": observed.get("launcher_executable_sha256"),
                    "command_line": observed.get("launcher_command_line"),
                    "service_role": "launcher",
                    "repo_root": observed.get("launcher_repo_root") or observed.get("repo_root"),
                }
            reasons.extend(
                _compare_identity_record("launcher", frozen_launcher, obs_launcher_pid, launcher_detail)
            )
        else:
            exp_launcher = _optional_int(frozen.get("launcher_pid"))
            if exp_launcher is None or obs_launcher_pid is None:
                reasons.append("process_identity_launcher_pid_unavailable")
            elif exp_launcher != obs_launcher_pid:
                reasons.append("process_identity_launcher_pid_mismatch")

        if frozen_supervisor:
            supervisor_detail = observed.get("supervisor")
            if not isinstance(supervisor_detail, Mapping):
                supervisor_detail = {
                    "parent_pid": observed.get("supervisor_parent_pid"),
                    "creation_time": observed.get("supervisor_creation_time"),
                    "executable_path": observed.get("supervisor_executable_path"),
                    "executable_sha256": observed.get("supervisor_executable_sha256"),
                    "command_line": observed.get("supervisor_command_line"),
                    "service_role": "supervisor",
                    "repo_root": observed.get("supervisor_repo_root") or observed.get("repo_root"),
                }
            reasons.extend(
                _compare_identity_record(
                    "supervisor",
                    frozen_supervisor,
                    obs_supervisor_pid,
                    supervisor_detail,
                )
            )
        else:
            exp_supervisor = _optional_int(frozen.get("supervisor_pid"))
            if exp_supervisor is None or obs_supervisor_pid is None:
                reasons.append("process_identity_supervisor_pid_unavailable")
            elif exp_supervisor != obs_supervisor_pid:
                reasons.append("process_identity_supervisor_pid_mismatch")

        expected_services = (
            frozen.get("managed_services") if isinstance(frozen.get("managed_services"), Mapping) else {}
        )
        actual_services = observed.get("managed_services") if isinstance(observed.get("managed_services"), Mapping) else {}
        for name, expected_info in expected_services.items():
            actual_info = actual_services.get(name)
            if isinstance(expected_info, Mapping) and expected_info.get("schema_version") == PROCESS_IDENTITY_SCHEMA:
                act_pid = _optional_int(actual_info.get("pid")) if isinstance(actual_info, Mapping) else None
                reasons.extend(
                    _compare_identity_record(
                        f"service:{name}",
                        expected_info,
                        act_pid,
                        actual_info if isinstance(actual_info, Mapping) else None,
                    )
                )
                continue
            if not isinstance(expected_info, Mapping) or not isinstance(actual_info, Mapping):
                reasons.append(f"process_identity_service_unavailable:{name}")
                continue
            exp_pid = _optional_int(expected_info.get("pid"))
            act_pid = _optional_int(actual_info.get("pid"))
            if exp_pid is None or act_pid is None:
                reasons.append(f"process_identity_service_pid_unavailable:{name}")
            elif exp_pid != act_pid:
                reasons.append(f"process_identity_service_pid_mismatch:{name}")

        for bound_field in ("attempt_id", "baseline_commit", "repo_root"):
            frozen_val = frozen.get(bound_field)
            if not frozen_val:
                continue
            obs_top = str(observed_supervisor_state.get(bound_field) or "")
            obs_identity = str(observed.get(bound_field) or "")
            if obs_top and str(frozen_val) != obs_top:
                reasons.append(f"process_identity_{bound_field}_mismatch")
            elif obs_identity and str(frozen_val) != obs_identity:
                reasons.append(f"process_identity_{bound_field}_mismatch")

    except Exception as exc:
        reasons.append(f"process_identity_validation_error:{type(exc).__name__}")

    return list(dict.fromkeys(reasons))


def _observed_identity_detail(
    observed: Mapping[str, Any],
    *,
    key: str,
    prefix: str,
    role: str,
) -> Mapping[str, Any]:
    detail = observed.get(key)
    if isinstance(detail, Mapping):
        return detail
    return {
        "parent_pid": observed.get(f"{prefix}_parent_pid"),
        "creation_time": observed.get(f"{prefix}_creation_time"),
        "executable_path": observed.get(f"{prefix}_executable_path"),
        "executable_sha256": observed.get(f"{prefix}_executable_sha256"),
        "command_line": observed.get(f"{prefix}_command_line"),
        "service_role": role,
        "repo_root": observed.get(f"{prefix}_repo_root") or observed.get("repo_root"),
    }


def _context_mismatch_reasons(
    label: str,
    record: Mapping[str, Any],
    *,
    attempt_id: str,
    baseline_commit: str,
    repo_root: str | Path,
    require_present: bool,
) -> list[str]:
    reasons: list[str] = []
    expected = {
        "attempt_id": str(attempt_id or ""),
        "baseline_commit": str(baseline_commit or ""),
        "repo_root": os.path.normcase(os.path.abspath(str(repo_root or ""))),
    }
    for field, expected_value in expected.items():
        value = record.get(field)
        if value in (None, ""):
            if require_present:
                reasons.append(f"process_identity_{label}_{field}_unavailable")
            continue
        observed_value = str(value)
        if field == "repo_root":
            observed_value = os.path.normcase(os.path.abspath(observed_value))
        if expected_value and observed_value != expected_value:
            reasons.append(f"process_identity_{label}_{field}_mismatch")
    return reasons


def _live_reconcile_one(
    *,
    label: str,
    frozen_record: Mapping[str, Any],
    observed_pid: int | None,
    observed_detail: Mapping[str, Any],
    attempt_id: str,
    baseline_commit: str,
    repo_root: str | Path,
    probe: IdentityProbe,
) -> list[str]:
    reasons: list[str] = []
    expected_pid = canonical_process_pid(frozen_record.get("pid"))
    if expected_pid is None:
        return [f"process_identity_{label}_pid_unavailable"]
    if observed_pid is None:
        reasons.append(f"process_identity_{label}_observed_pid_unavailable")
    elif observed_pid != expected_pid:
        reasons.append(f"process_identity_{label}_observed_pid_mismatch")

    role = str(frozen_record.get("service_role") or label)
    reasons.extend(
        _context_mismatch_reasons(
            label,
            frozen_record,
            attempt_id=attempt_id,
            baseline_commit=baseline_commit,
            repo_root=repo_root,
            require_present=True,
        )
    )
    if observed_detail:
        reasons.extend(
            _context_mismatch_reasons(
                f"{label}_observed",
                observed_detail,
                attempt_id=attempt_id,
                baseline_commit=baseline_commit,
                repo_root=repo_root,
                require_present=False,
            )
        )

    try:
        live_record = build_process_identity_record(
            pid=expected_pid,
            role=role,
            attempt_id=attempt_id,
            baseline_commit=baseline_commit,
            repo_root=repo_root,
            parent_pid=observed_detail.get("parent_pid"),
            creation_time=observed_detail.get("creation_time") or observed_detail.get("create_time"),
            executable_path=observed_detail.get("executable_path") or observed_detail.get("exe"),
            executable_sha256=observed_detail.get("executable_sha256"),
            command_line=observed_detail.get("command_line") or observed_detail.get("cmdline"),
            probe=probe,
            require_live_fields=True,
        )
    except ContinuityError as exc:
        reasons.append(f"process_identity_{label}_live_probe_failed:{exc.code}")
        return list(dict.fromkeys(reasons))
    except Exception as exc:
        reasons.append(f"process_identity_{label}_live_probe_exception:{type(exc).__name__}")
        return list(dict.fromkeys(reasons))

    for reason in _compare_identity_record(
        f"{label}_frozen_live",
        frozen_record,
        expected_pid,
        live_record,
    ):
        reasons.append(reason)
    for reason in _compare_identity_record(
        f"{label}_observed_live",
        live_record,
        observed_pid,
        observed_detail,
    ):
        reasons.append(reason)
    return list(dict.fromkeys(reasons))


def _managed_service_mapping(
    source: Mapping[str, Any],
    *,
    label: str,
) -> tuple[dict[str, Any], list[str]]:
    value = source.get("managed_services")
    if not isinstance(value, Mapping):
        return {}, [f"process_identity_managed_services_malformed:{label}"]

    services: dict[str, Any] = {}
    reasons: list[str] = []
    for raw_name, raw_info in value.items():
        if not isinstance(raw_name, str):
            reasons.append(f"process_identity_managed_service_name_malformed:{label}:{raw_name}")
            continue
        name = raw_name
        if not name.strip():
            reasons.append(f"process_identity_managed_service_name_malformed:{label}:blank")
            continue
        services[name] = raw_info
        if not isinstance(raw_info, Mapping):
            reasons.append(f"process_identity_managed_service_malformed:{label}:{name}")
    return services, reasons


def reconcile_process_identity_live(
    *,
    frozen: Mapping[str, Any],
    observed_supervisor_state: Mapping[str, Any],
    attempt_id: str,
    baseline_commit: str,
    repo_root: str | Path,
    probe: IdentityProbe | None = None,
) -> list[str]:
    """Authoritative final process reconciliation.

    This keeps validate_process_identity as a pure JSON comparison, then
    requires a fresh stable OS probe for every frozen launcher/supervisor/service
    process. Matching JSON alone is never sufficient for final eligibility.
    """
    reasons = list(validate_process_identity(frozen=frozen, observed_supervisor_state=observed_supervisor_state))
    active_probe = probe or default_identity_probe
    observed = observed_supervisor_state.get("process_identity")
    if not isinstance(observed, Mapping):
        reasons.append("process_identity_missing")
        return list(dict.fromkeys(reasons))

    frozen_launcher = frozen.get("launcher") if isinstance(frozen.get("launcher"), Mapping) else None
    frozen_supervisor = frozen.get("supervisor") if isinstance(frozen.get("supervisor"), Mapping) else None

    if frozen_launcher:
        reasons.extend(
            _live_reconcile_one(
                label="launcher",
                frozen_record=frozen_launcher,
                observed_pid=canonical_process_pid(observed.get("launcher_pid")),
                observed_detail=_observed_identity_detail(
                    observed,
                    key="launcher",
                    prefix="launcher",
                    role="launcher",
                ),
                attempt_id=attempt_id,
                baseline_commit=baseline_commit,
                repo_root=repo_root,
                probe=active_probe,
            )
        )
    else:
        reasons.append("process_identity_launcher_live_required")

    if frozen_supervisor:
        reasons.extend(
            _live_reconcile_one(
                label="supervisor",
                frozen_record=frozen_supervisor,
                observed_pid=canonical_process_pid(observed.get("supervisor_pid")),
                observed_detail=_observed_identity_detail(
                    observed,
                    key="supervisor",
                    prefix="supervisor",
                    role="supervisor",
                ),
                attempt_id=attempt_id,
                baseline_commit=baseline_commit,
                repo_root=repo_root,
                probe=active_probe,
            )
        )
    else:
        reasons.append("process_identity_supervisor_live_required")

    expected_services, expected_service_reasons = _managed_service_mapping(frozen, label="frozen")
    actual_services, actual_service_reasons = _managed_service_mapping(observed, label="observed")
    reasons.extend(expected_service_reasons)
    reasons.extend(actual_service_reasons)

    expected_names = set(expected_services)
    actual_names = set(actual_services)
    for name in sorted(expected_names - actual_names):
        reasons.append(f"process_identity_missing_service:{name}")
    for name in sorted(actual_names - expected_names):
        reasons.append(f"process_identity_unexpected_service:{name}")

    for name in sorted(expected_names & actual_names):
        expected_info = expected_services[name]
        if not isinstance(expected_info, Mapping):
            reasons.append(f"process_identity_service_live_malformed:{name}")
            continue
        actual_info = actual_services.get(name)
        actual_detail = actual_info if isinstance(actual_info, Mapping) else {}
        reasons.extend(
            _live_reconcile_one(
                label=f"service:{name}",
                frozen_record=expected_info,
                observed_pid=canonical_process_pid(actual_detail.get("pid")),
                observed_detail=actual_detail,
                attempt_id=attempt_id,
                baseline_commit=baseline_commit,
                repo_root=repo_root,
                probe=active_probe,
            )
        )

    return list(dict.fromkeys(reasons))


def _validate_identity_record_structure(
    record: Any,
    *,
    label: str,
    expected_role: str,
    service_key: str | None = None,
    expected_attempt_id: str | None = None,
    expected_commit: str | None = None,
) -> list[str]:
    if record is None:
        return [f"process_identity_{label}_missing"]
    if not isinstance(record, Mapping):
        return [f"process_identity_{label}_malformed"]
    if not record:
        return [f"process_identity_{label}_empty"]

    reasons: list[str] = []
    fields = set(record)
    for field in sorted(fields - IDENTITY_RECORD_FIELDS):
        reasons.append(f"process_identity_{label}_unknown_field:{field}")
    for field in sorted(IDENTITY_RECORD_FIELDS - fields):
        reasons.append(f"process_identity_{label}_{field}_missing")

    if record.get("schema_version") != PROCESS_IDENTITY_SCHEMA:
        reasons.append(f"process_identity_{label}_schema_version_mismatch")

    pid_error = canonical_process_pid_error(record.get("pid"))
    if pid_error:
        reasons.append(f"process_identity_{label}_pid_{pid_error}")
    parent_error = canonical_process_pid_error(record.get("parent_pid"))
    if parent_error:
        reasons.append(f"process_identity_{label}_parent_pid_{parent_error}")

    creation = _strict_nonempty_string(record.get("creation_time"))
    if creation is None:
        reasons.append(f"process_identity_{label}_creation_time_malformed")
    else:
        try:
            _parse_creation_time(creation)
        except ContinuityError:
            reasons.append(f"process_identity_{label}_creation_time_malformed")

    for field in ("executable_path", "executable_identity", "executable_sha256", "command_sha256"):
        value = record.get(field)
        if not _is_lower_sha256_hex(value):
            reasons.append(f"process_identity_{label}_{field}_malformed")
    command_identity = _strict_nonempty_string(record.get("command_identity"))
    if command_identity is None:
        reasons.append(f"process_identity_{label}_command_identity_malformed")

    repo_root = _strict_nonempty_string(record.get("repo_root"))
    if repo_root is None:
        reasons.append(f"process_identity_{label}_repo_root_malformed")
    role = _strict_nonempty_string(record.get("service_role"))
    if role is None:
        reasons.append(f"process_identity_{label}_service_role_malformed")
    elif role != expected_role:
        reasons.append(f"process_identity_{label}_service_role_mismatch")
    if service_key is not None and role is not None and role != service_key:
        reasons.append(f"process_identity_{label}_service_key_role_mismatch")

    attempt_id = _strict_nonempty_string(record.get("attempt_id"))
    if attempt_id is None:
        reasons.append(f"process_identity_{label}_attempt_id_malformed")
    elif expected_attempt_id not in (None, "") and attempt_id != str(expected_attempt_id):
        reasons.append(f"process_identity_{label}_attempt_id_mismatch")
    commit = _strict_nonempty_string(record.get("baseline_commit"))
    if commit is None:
        reasons.append(f"process_identity_{label}_baseline_commit_malformed")
    elif expected_commit not in (None, "") and commit != str(expected_commit):
        reasons.append(f"process_identity_{label}_baseline_commit_mismatch")

    return list(dict.fromkeys(reasons))


def _validate_identity_document_structure(
    value: Any,
    *,
    label: str,
    expected_attempt_id: str | None = None,
    expected_commit: str | None = None,
) -> list[str]:
    """Structural fail-closed check shared by the freeze, observed tree, and persisted evidence."""
    if value is None:
        return [f"process_identity_{label}_missing"]
    if not isinstance(value, Mapping):
        return [f"process_identity_{label}_malformed"]
    if not value:
        return [f"process_identity_{label}_empty"]

    reasons: list[str] = []
    allowed_document_fields = frozenset(
        {
            "schema_version",
            "attempt_id",
            "baseline_commit",
            "repo_root",
            "launcher",
            "supervisor",
            "managed_services",
        }
    ) | IDENTITY_DOCUMENT_OPTIONAL_FIELDS
    for field in sorted(set(value) - allowed_document_fields):
        reasons.append(f"process_identity_{label}_unknown_field:{field}")
    if value.get("schema_version") != PROCESS_IDENTITY_SCHEMA:
        reasons.append(f"process_identity_{label}_schema_version_mismatch")
    doc_attempt = _strict_nonempty_string(value.get("attempt_id"))
    if doc_attempt is None:
        reasons.append(f"process_identity_{label}_attempt_id_malformed")
    elif expected_attempt_id not in (None, "") and doc_attempt != str(expected_attempt_id):
        reasons.append(f"process_identity_{label}_attempt_id_mismatch")
    doc_commit = _strict_nonempty_string(value.get("baseline_commit"))
    if doc_commit is None:
        reasons.append(f"process_identity_{label}_baseline_commit_malformed")
    elif expected_commit not in (None, "") and doc_commit != str(expected_commit):
        reasons.append(f"process_identity_{label}_baseline_commit_mismatch")
    if _strict_nonempty_string(value.get("repo_root")) is None:
        reasons.append(f"process_identity_{label}_repo_root_malformed")

    launcher = value.get("launcher")
    supervisor = value.get("supervisor")
    reasons.extend(
        _validate_identity_record_structure(
            launcher,
            label=f"{label}_launcher",
            expected_role="launcher",
            expected_attempt_id=doc_attempt,
            expected_commit=doc_commit,
        )
    )
    reasons.extend(
        _validate_identity_record_structure(
            supervisor,
            label=f"{label}_supervisor",
            expected_role="supervisor",
            expected_attempt_id=doc_attempt,
            expected_commit=doc_commit,
        )
    )
    if isinstance(launcher, Mapping):
        launcher_pid_error = canonical_process_pid_error(value.get("launcher_pid"))
        launcher_pid = canonical_process_pid(value.get("launcher_pid"))
        if "launcher_pid" in value and launcher_pid_error:
            reasons.append(f"process_identity_{label}_launcher_pid_{launcher_pid_error}")
        elif launcher_pid is not None and launcher_pid != canonical_process_pid(launcher.get("pid")):
            reasons.append(f"process_identity_{label}_launcher_pid_mismatch")
    if isinstance(supervisor, Mapping):
        supervisor_pid_error = canonical_process_pid_error(value.get("supervisor_pid"))
        supervisor_pid = canonical_process_pid(value.get("supervisor_pid"))
        if "supervisor_pid" in value and supervisor_pid_error:
            reasons.append(f"process_identity_{label}_supervisor_pid_{supervisor_pid_error}")
        elif supervisor_pid is not None and supervisor_pid != canonical_process_pid(supervisor.get("pid")):
            reasons.append(f"process_identity_{label}_supervisor_pid_mismatch")

    managed = value.get("managed_services")
    if not isinstance(managed, Mapping):
        reasons.append(f"process_identity_{label}_managed_services_malformed")
    else:
        for raw_name, record in managed.items():
            if not isinstance(raw_name, str) or not raw_name.strip():
                reasons.append(f"process_identity_{label}_managed_service_name_malformed")
                continue
            reasons.extend(
                _validate_identity_record_structure(
                    record,
                    label=f"{label}_service:{raw_name}",
                    expected_role=raw_name,
                    service_key=raw_name,
                    expected_attempt_id=doc_attempt,
                    expected_commit=doc_commit,
                )
            )
    return list(dict.fromkeys(reasons))


def load_process_identity_evidence(
    package_root: Path | str,
    *,
    filename: str = PROCESS_IDENTITY_EVIDENCE_FILENAME,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Strict reader for persisted PROCESS_IDENTITY.json. Missing/malformed fails closed."""
    path = Path(package_root) / filename
    if not path.exists():
        return None, ["process_identity_evidence_missing"]
    try:
        payload = read_json_object(path)
    except PersistenceError as exc:
        return None, [f"process_identity_evidence_invalid:{exc.code}"]
    return payload, []


def validate_process_identity_evidence(
    evidence: Any,
    *,
    freeze: Mapping[str, Any] | None = None,
    expected_attempt_id: str | None = None,
    expected_commit: str | None = None,
) -> list[str]:
    """Fail-closed validation of persisted process-identity evidence and its bindings."""
    reasons = _validate_identity_document_structure(
        evidence,
        label="evidence",
        expected_attempt_id=expected_attempt_id,
        expected_commit=expected_commit,
    )
    if reasons:
        return reasons

    if freeze is not None:
        freeze_reasons = _validate_identity_document_structure(
            freeze,
            label="freeze",
            expected_attempt_id=expected_attempt_id,
            expected_commit=expected_commit,
        )
        if freeze_reasons:
            return list(dict.fromkeys(reasons + freeze_reasons))
        for field in ("attempt_id", "baseline_commit"):
            if str(evidence.get(field) or "") != str(freeze.get(field) or ""):
                reasons.append(f"process_identity_evidence_{field}_freeze_mismatch")
        for role in ("launcher", "supervisor"):
            frozen_record = freeze.get(role)
            evidence_record = evidence.get(role)
            frozen_pid = (
                _optional_int(frozen_record.get("pid")) if isinstance(frozen_record, Mapping) else None
            )
            evidence_pid = (
                _optional_int(evidence_record.get("pid"))
                if isinstance(evidence_record, Mapping)
                else None
            )
            if frozen_pid is None or evidence_pid is None or frozen_pid != evidence_pid:
                reasons.append(f"process_identity_evidence_{role}_pid_mismatch")
        frozen_services = freeze.get("managed_services")
        evidence_services = evidence.get("managed_services")
        frozen_names = set(frozen_services) if isinstance(frozen_services, Mapping) else set()
        evidence_names = set(evidence_services) if isinstance(evidence_services, Mapping) else set()
        if frozen_names != evidence_names:
            reasons.append("process_identity_evidence_managed_services_mismatch")

    return list(dict.fromkeys(reasons))


def validate_process_identity_freeze(
    freeze: Any,
    *,
    package_root: Path | str | None = None,
    evidence: Mapping[str, Any] | None = None,
    expected_attempt_id: str | None = None,
    expected_commit: str | None = None,
) -> list[str]:
    """Fail-closed validation of the process-identity freeze mapping.

    When ``package_root`` is supplied the persisted ``PROCESS_IDENTITY.json`` is
    loaded with the strict reader and reconciled against the freeze.
    """
    reasons = _validate_identity_document_structure(
        freeze,
        label="freeze",
        expected_attempt_id=expected_attempt_id,
        expected_commit=expected_commit,
    )
    if reasons:
        return reasons

    if expected_attempt_id not in (None, "") and str(freeze.get("attempt_id") or "") != str(
        expected_attempt_id
    ):
        reasons.append("process_identity_freeze_attempt_id_mismatch")
    if expected_commit not in (None, "") and str(freeze.get("baseline_commit") or "") != str(
        expected_commit
    ):
        reasons.append("process_identity_freeze_commit_mismatch")

    loaded_evidence = evidence
    if package_root is not None and loaded_evidence is None:
        loaded_evidence, load_reasons = load_process_identity_evidence(package_root)
        if load_reasons:
            return list(dict.fromkeys(reasons + load_reasons))
    if loaded_evidence is not None:
        reasons.extend(
            validate_process_identity_evidence(
                loaded_evidence,
                freeze=freeze,
                expected_attempt_id=expected_attempt_id,
                expected_commit=expected_commit,
            )
        )
    return list(dict.fromkeys(reasons))


def _identity_service_names(value: Mapping[str, Any] | None) -> list[str]:
    services = value.get("managed_services") if isinstance(value, Mapping) else None
    if not isinstance(services, Mapping):
        return []
    return sorted(str(name) for name in services if isinstance(name, str) and name.strip())


@dataclass(frozen=True, slots=True)
class _ProcessIdentityReconciliationResult:
    schema_version: str
    expected_run_id: str
    expected_commit: str
    frozen_identity_digest: str
    persisted_identity_evidence_digest: str
    classification: str
    verified_roles: tuple[str, ...]
    verified_services: tuple[str, ...]
    reasons: tuple[str, ...]


def _reconciliation_result_payload(result: _ProcessIdentityReconciliationResult) -> dict[str, Any]:
    return {
        "schema_version": result.schema_version,
        "expected_run_id": result.expected_run_id,
        "expected_commit": result.expected_commit,
        "frozen_identity_digest": result.frozen_identity_digest,
        "persisted_identity_evidence_digest": result.persisted_identity_evidence_digest,
        "classification": result.classification,
        "verified_roles": list(result.verified_roles),
        "verified_services": list(result.verified_services),
        "reasons": list(result.reasons),
    }


def _build_authoritative_process_identity_reconciliation(
    *,
    expected_run_id: str,
    expected_commit: str,
    freeze: Mapping[str, Any],
    evidence: Mapping[str, Any],
    reasons: Sequence[str],
) -> _ProcessIdentityReconciliationResult:
    reason_list = [str(reason) for reason in reasons]
    verified_services = tuple(_identity_service_names(freeze)) if not reason_list else ()
    return _ProcessIdentityReconciliationResult(
        schema_version=PROCESS_IDENTITY_RECONCILIATION_SCHEMA,
        expected_run_id=str(expected_run_id),
        expected_commit=str(expected_commit),
        frozen_identity_digest=_canonical_payload_digest(freeze),
        persisted_identity_evidence_digest=_canonical_payload_digest(evidence),
        classification="SUCCESS" if not reason_list else "FAILED",
        verified_roles=("launcher", "supervisor") if not reason_list else (),
        verified_services=verified_services,
        reasons=tuple(reason_list),
    )


def build_process_identity_reconciliation_result(
    *,
    expected_run_id: str,
    expected_commit: str,
    freeze: Mapping[str, Any],
    evidence: Mapping[str, Any],
    reasons: Sequence[str],
) -> dict[str, Any]:
    """Non-authoritative audit payload; final certification rejects this mapping."""
    return _reconciliation_result_payload(
        _build_authoritative_process_identity_reconciliation(
            expected_run_id=expected_run_id,
            expected_commit=expected_commit,
            freeze=freeze,
            evidence=evidence,
            reasons=reasons,
        )
    )


def validate_process_identity_reconciliation_result(
    result: Any,
    *,
    expected_run_id: str | None,
    expected_commit: str | None,
    freeze: Mapping[str, Any] | None,
    evidence: Mapping[str, Any] | None,
) -> list[str]:
    if result is None:
        return ["process_identity_reconciliation_result_missing"]
    if isinstance(result, Mapping):
        return ["process_identity_reconciliation_result_not_authoritative"]
    if type(result) is not _ProcessIdentityReconciliationResult:
        return ["process_identity_reconciliation_result_malformed"]
    reasons: list[str] = []
    if result.schema_version != PROCESS_IDENTITY_RECONCILIATION_SCHEMA:
        reasons.append("process_identity_reconciliation_schema_version_mismatch")
    if expected_run_id in (None, ""):
        reasons.append("expected_run_id_missing")
    elif result.expected_run_id != str(expected_run_id):
        reasons.append("process_identity_reconciliation_attempt_id_mismatch")
    if expected_commit in (None, ""):
        reasons.append("expected_commit_missing")
    elif result.expected_commit != str(expected_commit):
        reasons.append("process_identity_reconciliation_commit_mismatch")

    if not _is_lower_sha256_hex(result.frozen_identity_digest):
        reasons.append("process_identity_reconciliation_freeze_digest_malformed")
    elif freeze is not None and result.frozen_identity_digest != _canonical_payload_digest(freeze):
        reasons.append("process_identity_reconciliation_freeze_digest_mismatch")
    if not _is_lower_sha256_hex(result.persisted_identity_evidence_digest):
        reasons.append("process_identity_reconciliation_evidence_digest_malformed")
    elif evidence is not None and result.persisted_identity_evidence_digest != _canonical_payload_digest(evidence):
        reasons.append("process_identity_reconciliation_evidence_digest_mismatch")

    result_reasons = result.reasons
    if not isinstance(result_reasons, tuple) or any(not isinstance(item, str) for item in result_reasons):
        reasons.append("process_identity_reconciliation_reasons_malformed")
        result_reasons = ()
    classification = result.classification
    if classification not in {"SUCCESS", "FAILED"}:
        reasons.append("process_identity_reconciliation_classification_malformed")
    if classification != "SUCCESS":
        reasons.append("process_identity_reconciliation_not_success")
    if result_reasons:
        reasons.extend(result_reasons)

    verified_roles = result.verified_roles
    if verified_roles != ("launcher", "supervisor"):
        reasons.append("process_identity_reconciliation_verified_roles_mismatch")
    verified_services = result.verified_services
    expected_services = tuple(_identity_service_names(freeze))
    if verified_services != expected_services:
        reasons.append("process_identity_reconciliation_verified_services_mismatch")
    return list(dict.fromkeys(reasons))


def classify_restart_event(
    *,
    event_type: str,
    restart_count_before: int,
) -> dict[str, Any]:
    """Distinguish initial startup from restart. Incomplete info fails closed."""
    et = str(event_type or "").strip().lower()
    if not et:
        return {
            "classification": "UNKNOWN",
            "counts_as_restart": True,
            "fail_closed": True,
            "reason": "restart_event_type_missing",
        }
    if et in {"supervisor_start", "initial_startup", "controlled_startup"}:
        return {
            "classification": "INITIAL_STARTUP",
            "counts_as_restart": False,
            "fail_closed": False,
            "reason": et,
        }
    if et in {"controlled_shutdown"}:
        return {
            "classification": "CONTROLLED_SHUTDOWN",
            "counts_as_restart": False,
            "fail_closed": False,
            "reason": et,
        }
    if et in {
        "unexpected_failure",
        "unexpected_restart_attempt",
        "unexpected_restart_success",
        "restart_attempt",
        "restart_limit_exhausted",
    }:
        return {
            "classification": "UNEXPECTED_RESTART",
            "counts_as_restart": True,
            "fail_closed": False,
            "reason": et,
            "restart_count_before": restart_count_before,
        }
    return {
        "classification": "UNKNOWN",
        "counts_as_restart": True,
        "fail_closed": True,
        "reason": f"unclassified_restart_event:{et}",
    }


def critical_alert_digest(events: Sequence[Mapping[str, Any]]) -> str:
    """Deterministic digest over critical alert / ledger material."""
    rows: list[str] = []
    for event in sorted(
        events,
        key=lambda item: (
            _optional_int(item.get("sequence")) or 0,
            str(item.get("alert_id") or ""),
            str(item.get("timestamp") or ""),
        ),
    ):
        material = "|".join(
            [
                str(event.get("sequence") or ""),
                str(event.get("alert_id") or ""),
                str(event.get("code") or ""),
                str(event.get("timestamp") or ""),
                str(event.get("severity") or ""),
            ]
        )
        rows.append(material)
    payload = "\n".join(rows)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_critical_event_ledger(path: Path | str) -> dict[str, Any]:
    """Load monotonic critical-event ledger. Missing file is empty OK; truncated/malformed fails closed."""
    dest = Path(path)
    if not dest.exists():
        return {
            "ok": True,
            "events": [],
            "count": 0,
            "sequence": 0,
            "digest": critical_alert_digest([]),
            "complete": True,
            "errors": [],
        }

    try:
        raw = dest.read_text(encoding="utf-8")
    except OSError as exc:
        return {
            "ok": False,
            "events": [],
            "count": 0,
            "sequence": 0,
            "digest": "",
            "complete": False,
            "errors": [f"ledger_unreadable:{type(exc).__name__}"],
        }

    errors: list[str] = []
    if raw and not raw.endswith("\n"):
        errors.append("ledger_truncated")

    events: list[dict[str, Any]] = []
    for line_no, line in enumerate(raw.splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        try:
            row = strict_json_loads(text, source=f"{dest.name}:{line_no}")
        except PersistenceError:
            errors.append(f"ledger_malformed_line:{line_no}")
            continue
        if not isinstance(row, dict):
            errors.append(f"ledger_not_object:{line_no}")
            continue
        events.append(row)

    sequence = 0
    for row in events:
        seq = _optional_int(row.get("sequence"))
        if seq is not None:
            sequence = max(sequence, seq)

    digest = critical_alert_digest(events)
    complete = not errors
    return {
        "ok": complete,
        "events": events,
        "count": len(events),
        "sequence": sequence,
        "digest": digest,
        "complete": complete,
        "errors": list(dict.fromkeys(errors)),
    }


def append_critical_event(
    path: Path | str,
    *,
    attempt_id: str,
    baseline_commit: str,
    event: Mapping[str, Any],
    expected_root: Path | str | None = None,
) -> dict[str, Any]:
    """Append one ledger row with monotonic sequence via atomic JSONL append."""
    if not attempt_id or not baseline_commit:
        raise ContinuityError("critical_ledger_identity_missing")
    if not isinstance(event, Mapping):
        raise ContinuityError("critical_event_malformed")

    ledger = load_critical_event_ledger(path)
    if not ledger.get("complete"):
        raise ContinuityError("critical_ledger_incomplete", ",".join(ledger.get("errors") or []))

    next_sequence = int(ledger.get("sequence") or 0) + 1
    record = {
        "schema_version": CRITICAL_LEDGER_SCHEMA,
        "sequence": next_sequence,
        "attempt_id": str(attempt_id),
        "baseline_commit": str(baseline_commit),
        "appended_at_utc": _utc_now_iso(),
        **dict(event),
    }
    try:
        lock_path = Path(path).with_name(Path(path).name + ".writer.lock")
        from backend.certification.ov002_persistence import acquire_writer_lock

        with acquire_writer_lock(
            lock_path,
            attempt_id=attempt_id,
            writer_role="ov002_critical_ledger",
            expected_root=expected_root,
        ):
            atomic_append_jsonl(path, record, expected_root=expected_root)
    except PersistenceError as exc:
        raise ContinuityError("critical_ledger_append_failed", exc.code) from exc
    return record


def reconcile_critical_ledger_with_alerts(
    *,
    ledger: Mapping[str, Any],
    critical_alerts: Sequence[Mapping[str, Any]],
    expected_attempt_id: str,
    expected_commit: str,
) -> dict[str, Any]:
    """Reconcile ledger completeness, identity binding, digest, count, and sequence 1..n."""
    reasons: list[str] = []
    if not ledger.get("complete"):
        reasons.extend(str(e) for e in ledger.get("errors") or [])
        reasons.append("critical_ledger_incomplete")

    if str(ledger.get("attempt_id") or "") and str(ledger.get("attempt_id")) != str(expected_attempt_id):
        reasons.append("critical_ledger_attempt_id_mismatch")
    if str(ledger.get("baseline_commit") or "") and str(ledger.get("baseline_commit")) != str(expected_commit):
        reasons.append("critical_ledger_commit_mismatch")

    events = list(ledger.get("events") or [])
    alert_count = len(critical_alerts)
    if int(ledger.get("count") or 0) != len(events):
        reasons.append("critical_ledger_count_mismatch")
    if len(events) != alert_count:
        reasons.append("critical_alert_count_mismatch")

    sequences = []
    for row in events:
        seq = _optional_int(row.get("sequence"))
        if seq is None:
            reasons.append("critical_ledger_sequence_malformed")
            continue
        sequences.append(seq)
    if sequences:
        expected_seq = list(range(1, len(sequences) + 1))
        if sorted(sequences) != expected_seq:
            reasons.append("critical_ledger_sequence_gap")

    computed_digest = critical_alert_digest(events)
    stored_digest = str(ledger.get("digest") or "")
    if stored_digest and stored_digest != computed_digest:
        reasons.append("critical_ledger_digest_mismatch")

    alert_digest = critical_alert_digest(critical_alerts)
    if events and alert_digest != computed_digest:
        reasons.append("critical_alert_digest_mismatch")

    for row in events:
        if str(row.get("attempt_id") or expected_attempt_id) != str(expected_attempt_id):
            reasons.append("critical_event_attempt_id_mismatch")
        if str(row.get("baseline_commit") or expected_commit) != str(expected_commit):
            reasons.append("critical_event_commit_mismatch")

    unique = list(dict.fromkeys(reasons))
    return {
        "ok": not unique,
        "reasons": unique,
        "digest": computed_digest,
        "count": len(events),
        "sequence": int(ledger.get("sequence") or 0),
    }


@dataclass(frozen=True)
class FinalCertificationResult:
    attempt_state: str
    certification: str
    eligible: bool
    reasons: tuple[str, ...]
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempt_state": self.attempt_state,
            "certification": self.certification,
            "eligible": self.eligible,
            "reasons": list(self.reasons),
            "recommendation": self.recommendation,
            "phase181": STATE_NOT_CERTIFIED,
            "live_trading": "BLOCKED",
            "ov002_authority": True,
        }


def reject_legacy_certification_authority(payload: Mapping[str, Any] | None) -> list[str]:
    """Legacy marathon/validation outputs are never authoritative for OV002 or Phase 181."""
    if not payload:
        return []
    reasons = [
        "legacy_certification_non_authoritative_ov002",
        "legacy_certification_non_authoritative_phase181",
    ]
    text_blob = json.dumps(payload, sort_keys=True, default=str).upper()
    for token in ("PASS", "GO", "CERTIFIED", "PHASE181_CERTIFIED"):
        if token in text_blob:
            reasons.append(f"legacy_authority_token:{token}")
    return list(dict.fromkeys(reasons))


def evaluate_final_certification(
    *,
    run_meta: Mapping[str, Any],
    run_status: Mapping[str, Any],
    invalidation: Mapping[str, Any] | None,
    reconciliation_ok: bool,
    reconciliation_reasons: Sequence[str],
    alert_errors: Sequence[str],
    expected_run_id: Optional[str] = None,
    expected_commit: Optional[str] = None,
    phase181_auto_certify: bool = False,
    alert_scan_complete: bool = True,
    critical_ledger: Mapping[str, Any] | None = None,
    critical_alerts: Sequence[Mapping[str, Any]] | None = None,
    legacy_authority_payload: Mapping[str, Any] | None = None,
    process_identity_freeze: Mapping[str, Any] | None = None,
    process_identity_evidence: Mapping[str, Any] | None = None,
    process_identity_reasons: Sequence[str] | None = None,
    process_identity_reconciliation: Any | None = None,
    require_process_identity_continuity: bool = True,
) -> FinalCertificationResult:
    """Final gate: never CERTIFIED while continuity faults, partial scans, or legacy authority."""
    reasons: list[str] = []

    if legacy_authority_payload is not None:
        reasons.extend(reject_legacy_certification_authority(legacy_authority_payload))
        unique_legacy = tuple(dict.fromkeys(reasons))
        return FinalCertificationResult(
            attempt_state=STATE_NOT_CERTIFIED,
            certification=STATE_NOT_CERTIFIED,
            eligible=False,
            reasons=unique_legacy,
            recommendation="REJECT_LEGACY_CERTIFICATION_AUTHORITY",
        )

    if invalidation or str(run_status.get("status") or "").upper() == STATE_INVALIDATED:
        reasons.append("attempt_invalidated")
        inv_reasons = list(invalidation.get("reasons") or []) if invalidation else []
        return FinalCertificationResult(
            attempt_state=STATE_INVALIDATED,
            certification=STATE_NOT_CERTIFIED,
            eligible=False,
            reasons=tuple(dict.fromkeys(reasons + inv_reasons)),
            recommendation="ENDURANCE INVALIDATED",
        )

    if not run_meta:
        reasons.append("run_meta_missing")
    attempt_id = str(run_meta.get("run_id") or run_meta.get("attempt_id") or "")
    commit = str(run_meta.get("frozen_sha") or run_meta.get("baseline_commit") or run_meta.get("git_sha") or "")
    if expected_run_id is not None and attempt_id != str(expected_run_id):
        reasons.append("attempt_id_mismatch")
    if expected_commit is not None and commit != str(expected_commit):
        reasons.append("commit_mismatch")

    if not alert_scan_complete:
        reasons.append("alert_scan_incomplete")

    if require_process_identity_continuity:
        if expected_run_id in (None, ""):
            reasons.append("expected_run_id_missing")
        if expected_commit in (None, ""):
            reasons.append("expected_commit_missing")
        freeze_source = process_identity_freeze
        if freeze_source is None:
            freeze_source = run_meta.get("process_identity_freeze") if run_meta else None
        reasons.extend(
            validate_process_identity_freeze(
                freeze_source,
                evidence=process_identity_evidence,
                expected_attempt_id=str(expected_run_id) if expected_run_id not in (None, "") else None,
                expected_commit=str(expected_commit) if expected_commit not in (None, "") else None,
            )
        )
        if process_identity_evidence is None:
            reasons.append("process_identity_evidence_missing")
        reasons.extend(str(r) for r in process_identity_reasons or [])
        reasons.extend(
            validate_process_identity_reconciliation_result(
                process_identity_reconciliation,
                expected_run_id=str(expected_run_id) if expected_run_id not in (None, "") else None,
                expected_commit=str(expected_commit) if expected_commit not in (None, "") else None,
                freeze=freeze_source if isinstance(freeze_source, Mapping) else None,
                evidence=process_identity_evidence,
            )
        )

    if not reconciliation_ok:
        reasons.extend(str(r) for r in reconciliation_reasons)
        reasons.append("reconciliation_not_ok")
    if alert_errors:
        reasons.extend(f"alert_evidence:{e}" for e in alert_errors)

    if critical_ledger is not None:
        if not critical_ledger.get("complete"):
            reasons.append("critical_ledger_incomplete")
            reasons.extend(str(e) for e in critical_ledger.get("errors") or [])
        reconcile = reconcile_critical_ledger_with_alerts(
            ledger=critical_ledger,
            critical_alerts=list(critical_alerts or []),
            expected_attempt_id=str(expected_run_id or attempt_id),
            expected_commit=str(expected_commit or commit),
        )
        if not reconcile.get("ok"):
            reasons.extend(str(r) for r in reconcile.get("reasons") or [])

    if phase181_auto_certify:
        reasons.append("phase181_auto_certify_forbidden")

    unique = tuple(dict.fromkeys(reasons))
    if unique:
        return FinalCertificationResult(
            attempt_state=STATE_NOT_CERTIFIED,
            certification=STATE_NOT_CERTIFIED,
            eligible=False,
            reasons=unique,
            recommendation="ENDURANCE NOT_CERTIFIED",
        )

    return FinalCertificationResult(
        attempt_state=STATE_COMPLETED_ELIGIBLE,
        certification=STATE_NOT_CERTIFIED,
        eligible=True,
        reasons=(),
        recommendation="ENDURANCE COMPLETED_ELIGIBLE (Phase 181 NOT_CERTIFIED)",
    )


def reject_historical_attempt2_as_pass(attempt2_summary: Mapping[str, Any]) -> FinalCertificationResult:
    """Attempt 2 evidence cannot be reclassified as valid/PASS."""
    reasons = [
        "historical_attempt2_invalidated",
        "unexpected_restarts_observed",
        "engine_heartbeat_lost",
        "restart_limit_exceeded",
        "monitor_pass_without_alert_reconciliation",
    ]
    if attempt2_summary.get("restart_count", 0):
        reasons.append(f"restart_count={attempt2_summary.get('restart_count')}")
    if attempt2_summary.get("heartbeat_lost_count", 0):
        reasons.append(f"heartbeat_lost_count={attempt2_summary.get('heartbeat_lost_count')}")
    return FinalCertificationResult(
        attempt_state=STATE_INVALIDATED,
        certification=STATE_NOT_CERTIFIED,
        eligible=False,
        reasons=tuple(dict.fromkeys(reasons)),
        recommendation="ENDURANCE INVALIDATED",
    )


def persist_attempt_state(
    path: Path | str,
    *,
    target_state: str,
    attempt_id: str,
    baseline_commit: str,
    writer_role: str = "ov002_monitor",
    expected_root: Path | str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Monotonic, identity-bound attempt state with locked atomic persistence."""
    if not attempt_id or not baseline_commit:
        raise ContinuityError("attempt_identity_missing")

    dest = Path(path)
    target = str(target_state or "").upper()

    if dest.exists():
        try:
            existing = read_json_object(dest)
        except PersistenceError as exc:
            raise ContinuityError("attempt_state_read_failed", exc.code) from exc

        current = str(existing.get("attempt_state") or existing.get("state") or "").upper()
        if current not in KNOWN_ATTEMPT_STATES:
            raise ContinuityError("unknown_attempt_state", current)

        stored_attempt = str(existing.get("attempt_id") or existing.get("run_id") or "")
        stored_commit = str(existing.get("baseline_commit") or existing.get("frozen_sha") or "")
        if stored_attempt and stored_attempt != str(attempt_id):
            raise ContinuityError("attempt_id_mismatch", stored_attempt)
        if stored_commit and stored_commit != str(baseline_commit):
            raise ContinuityError("baseline_commit_mismatch", stored_commit)

        if current == STATE_INVALIDATED:
            if target == STATE_INVALIDATED:
                return existing
            raise ContinuityError("invalidated_terminal", f"cannot leave {current}")
        if current in TERMINAL_STATES and target != current:
            raise ContinuityError("terminal_state_immutable", f"{current}->{target}")

        new_state = transition_attempt_state(current, target)
    else:
        if target == STATE_INITIALIZING:
            new_state = STATE_INITIALIZING
        elif target == STATE_RUNNING:
            new_state = transition_attempt_state(STATE_INITIALIZING, STATE_RUNNING)
        elif target == STATE_INVALIDATED:
            new_state = STATE_INVALIDATED
        else:
            raise ContinuityError("illegal_initial_state", target)

    payload = {
        "schema_version": ATTEMPT_STATE_SCHEMA,
        "attempt_state": new_state,
        "attempt_id": str(attempt_id),
        "baseline_commit": str(baseline_commit),
        "run_id": str(attempt_id),
        "frozen_sha": str(baseline_commit),
        "updated_at_utc": _utc_now_iso(),
        **extra,
    }

    try:
        locked_atomic_write_json(
            dest,
            payload,
            attempt_id=str(attempt_id),
            writer_role=str(writer_role),
            expected_root=expected_root,
        )
    except WriterLockError as exc:
        raise ContinuityError("writer_lock_failed", exc.code) from exc
    except PersistenceError as exc:
        raise ContinuityError("persistence_failed", exc.code) from exc

    return payload


def write_attempt_state(path: Path | str, *, state: str, **extra: Any) -> dict[str, Any]:
    """Backward-compatible attempt state writer delegating to persist_attempt_state."""
    dest = Path(path)
    attempt_id = str(extra.pop("attempt_id", None) or extra.pop("run_id", None) or "")
    baseline_commit = str(extra.pop("baseline_commit", None) or extra.pop("frozen_sha", None) or "")
    writer_role = str(extra.pop("writer_role", "ov002_monitor"))
    expected_root = extra.pop("expected_root", None)

    if dest.exists() and (not attempt_id or not baseline_commit):
        try:
            existing = read_json_object(dest)
            if not attempt_id:
                attempt_id = str(existing.get("attempt_id") or existing.get("run_id") or "")
            if not baseline_commit:
                baseline_commit = str(
                    existing.get("baseline_commit") or existing.get("frozen_sha") or ""
                )
        except PersistenceError:
            pass

    if not attempt_id or not baseline_commit:
        raise ContinuityError("attempt_identity_missing")
    return persist_attempt_state(
        path,
        target_state=state,
        attempt_id=attempt_id,
        baseline_commit=baseline_commit,
        writer_role=writer_role,
        expected_root=expected_root,
        **extra,
    )
