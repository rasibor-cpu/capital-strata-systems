# Phase 114E: Always-On Runtime Launcher

**Date:** 2026-06-21
**Environment:** Control Branch `css-evening-consolidation-2026-06-09`

## Objective
Provide an operational foundation for running CSS unattended by introducing a top-level runtime launcher. This launcher wraps both the backend engine and the newly created mobile web dashboard, bringing them up via a single script (`launch_css.bat`).

## System Components
1. **Service Manager** (`css_service_manager.py`):
   - A lightweight subprocess orchestrator wrapping `subprocess.Popen`.
   - Tracks the states (`STARTING`, `RUNNING`, `STOPPED`, `FAILED`) of the CSS live dashboard and Mobile Launcher.
   - Ensures correct environment variable propagation (particularly `PYTHONPATH`).

2. **Runtime Launcher** (`css_runtime_launcher.py`):
   - Performs pre-flight checks: ensures the mobile launcher's default port (8765) is free and that all required execution scripts exist.
   - Instantiates the `CSSRuntimeSupervisor` to handle overall process health tracking.
   - Monitors the wrapped processes every 10 seconds.
   - Emits alerts through the CSS Alert Service if either process dies unexpectedly.
   - Records "restart eligibility" internally (automated restarts are deferred to a later phase).

3. **Execution Script** (`launch_css.bat`):
   - Sets the `PYTHONPATH` correctly for the runtime environment.
   - Triggers the runtime launcher.
   - Prints an `OPERATIONAL` status block upon successful launch.

## Security & Limitations
- **No live broker arming**: The launcher does not automatically override engine defaults. The engine starts in its default state (Paper/Simulated).
- **No automated restarts**: While the system tracks if a process has died (`restart_eligibility`), it does not restart it. This fail-safe preserves logs and prevents crash-loop scenarios in unattended environments for now.
- **No Windows Service Integration**: The launcher must currently be run manually or triggered via a terminal. Backgrounding as a native Windows Service will be handled in a later phase.

## Validation Strategy
The test suite validates:
- `CSSServiceManager` accurately models the entire process lifecycle.
- Processes intentionally exited with an error code correctly emit `FAILED` states.
- The pre-flight port checker correctly prevents dual-launches.
