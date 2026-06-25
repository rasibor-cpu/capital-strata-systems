# CSS Validation Bundle V2C

## 48-Hour Certification Execution Prep

## Scope

Created an operational wrapper and runbook for executing the 48-hour paper marathon certification flow.

## Deliverables

- `scripts/run_48h_paper_marathon.py`
- `tests/test_run_48h_paper_marathon.py`
- `PHASE_V2C_48_HOUR_CERTIFICATION_EXECUTION.md`

## Execution Behavior

- Runs V2A readiness first.
- Refuses execution unless readiness is `GO`.
- Enforces paper/practice mode and fails closed on live mode detection.
- Supports default 48-hour duration and smoke overrides with `--duration-minutes`.
- Supports `--cycle-interval-seconds`.
- Writes run evidence to `artifacts/marathon/<run_id>/`.
- Writes final certification report to `final_certification_report.json`.
- Emits clear status lines: `STARTED`, `STOPPED`, `FAILED`, `CERTIFIED`.

## Smoke Command

```powershell
python scripts/run_48h_paper_marathon.py --duration-minutes 0 --cycle-interval-seconds 1 --dry-run
```

## Non-Goals

- No broker execution changes.
- No live mode enablement.
- No RBAC changes.
- No UI changes.
- No trading logic changes.