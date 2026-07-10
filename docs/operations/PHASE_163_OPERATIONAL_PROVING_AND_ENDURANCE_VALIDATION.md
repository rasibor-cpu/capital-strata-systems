# CSS Phase 163 — Operational Proving & Endurance Validation

This document records the framework design for Phase 163, including system session resumption, host reboot detection, and capital disarm parameters.

---

## 1. Uptime Verification & Host Reboot Detection

The platform enforces strict session continuity checks (`CanonicalEnduranceEvidence`):
* **Host Reboot Tracking:** System boot time is verified using the Windows kernel Tick counter via `ctypes.windll.kernel32.GetTickCount64()`. 
* **State Resolution:** If the machine boot time changes by more than 15 seconds compared to the saved session boot time, a host reboot is logged, resetting the uninterrupted runtime counter to 0.0 hours.
* **Process Restart Tracking:** If the PID changes but the boot time remains identical, a CSS process restart is logged.

---

## 2. Canonical Endurance Evidence Model

Endurance metrics are structured into a canonical model:
* **`elapsed_duration`**: Total elapsed hours since validation start.
* **`uninterrupted_runtime_duration`**: Total hours run without a process restart or host reboot.
* **`host_restart_count` / `restart_count`**: Total counts of reboots/restarts.
* **`memory_baseline` / `memory_peak`**: Tracks Working Set memory usage (fail gate active if growth exceeds 150MB).
* **`evidence_completeness`**: Completion percentage against the target (72 hours).

---

## 3. Controlled Pilot Decision Gate

The Go/No-Go Gate (`ControlledPilotGate`) requires all the following criteria to evaluate as **GO**:
1. **Endurance Progress:** Evidence completeness must be 100% (72.0 hours reached).
2. **Uptime Continuity:** Zero critical blockers (e.g. memory leaks, excessive restarts) in the endurance log.
3. **Operational Acceptance:** Acceptance check is PASS.
4. **Governance Approvals:** Operator, risk committee, and deployment approvals present.
5. **Config Check:** Uptime environment `.env` variables present.
