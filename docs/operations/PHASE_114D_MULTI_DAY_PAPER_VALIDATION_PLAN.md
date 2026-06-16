# Phase 114D: Multi-Day Paper Validation Plan

## 1. Objective
Ensure Capital Strata Systems operates flawlessly without manual intervention over a sustained timeframe, validating crash safety, persistence, memory stability, and broker connectivity resilience.

## 2. Validation Targets
- **Minimum Target:** 48 hours of uninterrupted paper execution.
- **Preferred Target:** 72 hours spanning major market session transitions (e.g., Tokyo -> London -> NY).

## 3. Monitoring Cadence
- **Hourly:** Automated heartbeat check.
- **Every 6 Hours:** Manual operator visual check of the dashboard HUD.
- **Every 24 Hours:** Deep operational dive into logs and PnL persistence files.

## 4. Evidence Cadence
- **T+0 (Start):** Capture full startup sequence and environmental bindings.
- **T+24, T+48, T+72:** Snapshot dashboard states, `audit.log` hashes, and memory profiles.
- **End of Run:** Collect all Phase 114C required evidence artifacts into the final certification bundle.

## 5. Incident Handling
- In the event of a disconnection (e.g., OANDA API rate limits or network drop), the system's exponential backoff and recovery mechanism must be allowed to trigger.
- If the system completely stalls or crashes, the validation run is immediately aborted. The error must be isolated, fixed via the standard governance workflow, and the 48-hour clock reset to zero.

## 6. Daily Review Process
- Operators will run `css_session_analyzer.py` on the active session file.
- Verify that `unrealized_pnl` is updating dynamically and `realized_pnl` is cleanly segregated.
- Assess if the intelligence signal generator is behaving deterministically or diverging into hallucinated states.

## 7. Pass/Fail Criteria
- **PASS:** System completes the 48-72 hour envelope with zero fatal crashes, perfect state persistence, zero memory leaks >15%, and perfect risk-gate adherence.
- **FAIL:** A crash occurs, an invalid trade executes, or the application freezes requiring a hard `SIGKILL`.
