# CSS 72-Hour Paper-Trading Runbook

This runbook guides operators through initializing, maintaining, and verifying the 72-hour paper-trading endurance marathon.

---

## 1. Initializing the Endurance Run

1. **Purge Old Session Data:** Ensure there are no stale session cache files. Delete `artifacts/operations/endurance_session.json` if it exists.
2. **Confirm Advisory Lock:** Verify in `.env`:
   ```ini
   advisory_only=true
   live_trading_blocked=true
   ```
3. **Start the Application:** Run `launch_css.bat`.
4. **Inspect Uptime Utiils:** Verify the baseline memory and boot ticks are logged correctly on the Console.

---

## 2. Operator Checks during Validation

* **24-Hour Checkpoint:**
  - Verify that `endurance_elapsed_time` is >= 24.0 hours.
  - Check that `css_restart_count` is 0.
  - Verify memory usage has not increased by more than 50MB.

* **48-Hour Checkpoint:**
  - Verify that `endurance_elapsed_time` is >= 48.0 hours.
  - Verify `broker_reconnect_count` is less than 5.

* **72-Hour Final Checkpoint:**
  - Confirm `evidence_completeness` is 100.0%.
  - Verify `current_endurance_status` is `PASS`.

---

## 3. Handling Interruptions & Reboots

* **CSS Process Crash:**
  - The supervisor will automatically relaunch CSS. 
  - The session file will preserve elapsed time but reset `uninterrupted_runtime_duration` and log `css_process_restart_detected` warning.

* **Host Machine Uptime Interruption:**
  - If Windows restarts, boot tick verification will log `host_reboot_detected`.
  - Restart the application immediately. The session will resume from the last saved state, but uninterrupted runtime will reset.
