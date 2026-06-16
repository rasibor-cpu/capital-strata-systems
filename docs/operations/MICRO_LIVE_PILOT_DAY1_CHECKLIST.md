# Micro-Live Pilot Day 1 Checklist

## PRE-LAUNCH
- [ ] Verify branch (`css-evening-consolidation-2026-06-09`).
- [ ] Verify clean git status.
- [ ] Verify OANDA credentials exist in isolated `.env` file.
- [ ] Verify broker connectivity manually via `curl` or script.
- [ ] Verify reconciliation status (no legacy errors in DB).
- [ ] Verify security validation (`python -m pytest` passes completely).

## SESSION START
- [ ] Launch dashboard (`python scripts/css_live_dashboard.py`).
- [ ] Verify broker health indicates `GREEN`.
- [ ] Verify account balance matches expectations (≤ $1,000 USD).
- [ ] Verify session lock status (System is active and UNLOCKED).

## DURING SESSION
- [ ] Monitor trade activity.
- [ ] Monitor continuous reconciliation logs.
- [ ] Monitor repair records for anomalies.
- [ ] Monitor broker health for API degradation.

## SESSION END
- [ ] Export dashboard logs safely.
- [ ] Save screenshots of final daily PnL state.
- [ ] Archive evidence per Evidence Register.
- [ ] Update Evidence Register log list.

## ABORT PROCEDURE
- [ ] Trigger manual session lock.
- [ ] Disarm broker execution.
- [ ] Capture all logs immediately.
- [ ] Record incident via Repair Workflow.

## PILOT PARAMETERS
- **Maximum Capital:** $1,000
- **Maximum Daily Loss:** $20
- **Maximum Total Loss:** $50
- **Maximum Open Positions:** 3
- **Pilot Duration:** 5 Active Trading Days
