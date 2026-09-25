# CSS Windows Persistent Runtime

## Purpose

CSS on Windows must be started through the canonical always-on runtime launcher. The standalone mobile launcher is not the normal production/operator startup path because it does not own the canonical supervisor heartbeat.

Canonical startup:

```powershell
.\.venv\Scripts\python.exe launcher\css_runtime_launcher.py
```

The canonical launcher:

- starts `CSSRuntimeSupervisor`;
- starts the runtime dashboard child;
- starts the mobile launcher child;
- refreshes the authoritative supervisor heartbeat every 10 seconds;
- records strong process identity and duplicate-owner evidence;
- monitors managed child services and applies bounded restart logic;
- remains fail-closed: `execution_allowed=false`, `live_trading_blocked=true`, `broker_execution_armed=false`, `advisory_only=true`.

## Persistent startup

Use the committed wrapper:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_css_canonical.ps1
```

The wrapper refuses to start when port 8765 is already owned and exits successfully if the canonical runtime is already running under the repository virtual environment.

To install automatic startup at Windows user logon:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install_css_logon_task.ps1 -StartNow
```

The task is named `CapitalStrataSystems-CanonicalRuntime`. It uses `IgnoreNew` multiple-instance behavior and bounded task restart settings. The wrapper also performs its own duplicate-owner and port checks.

## Standalone mobile development override

Direct standalone mobile startup is blocked by default. For deliberate development-only testing:

```powershell
$env:CSS_ALLOW_STANDALONE_MOBILE='1'
.\.venv\Scripts\python.exe launcher\css_mobile_launcher.py
```

Do not use the override for normal operation. It intentionally bypasses canonical supervisor ownership and can cause runtime evidence to become stale while the UI remains reachable.

## Freshness behavior

Freshness is evidence-based. If the canonical runtime actually stops, loses its heartbeat, or the host is powered off, Mission Control must show stale/unavailable state and remain fail-closed. The persistence layer is designed to restart the canonical runtime at logon and avoid accidental standalone operation; it must never falsify a fresh heartbeat.

## Logs

Detached startup writes:

- `runtime/logs/css_canonical_runtime.out.log`
- `runtime/logs/css_canonical_runtime.err.log`

These logs are the first place to inspect if the scheduled task starts but Mission Control remains stale.
