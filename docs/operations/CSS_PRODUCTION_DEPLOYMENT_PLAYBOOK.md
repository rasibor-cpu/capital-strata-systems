# Capital Strata Systems (CSS) Production Deployment Playbook

This playbook defines deployment runbooks, startup verifications, rollback triggers, and emergency incident response guidelines.

---

## 1. Deployment Checklist

### Pre-Deployment
- [ ] Confirm `.env` is loaded with correct OANDA/Coinbase credentials.
- [ ] Verify that `advisory_only=true` is set.
- [ ] Verify that `live_trading_blocked=true` is set.

### Pilot Startup
- [ ] Launch `launch_css.bat`.
- [ ] Confirm startup diagnostic print lists all environment keys as `FOUND`.
- [ ] Access the Consolidated Command Centre.

---

## 2. Startup Verification & Health Check

Verify status views programmatically:
```python
# Execute readiness evaluation
readiness = dashboard_service.get_canonical_readiness_view()
assert readiness["readiness_score"] >= 90.0
assert readiness["go_no_go"] == "GO"

# Execute acceptance validation
acceptance = dashboard_service.validate_acceptance()
assert acceptance["status"] == "PASS"
```

---

## 3. Rollback Runbook (Emergency Disarm)

If any pilot rollback criteria are met (drawdown > 2.0% or connection drops >= 3):
1. **Trigger Manual Disarm:** Run the supervisor disarm script or set `live_trading_blocked=true`.
2. **Examine Rollback Log:** Check dashboard summary:
   ```python
   summary = pilot_framework.get_completion_summary()
   print(summary["rollback_reason"])
   ```
3. **Notify Risk Committee:** Send the rollback reason and P&L status report to stakeholders.

---

## 4. Incident Response

* **Flapping Connection:** If reconnect attempts exceed 5 in an hour, suspend trading adapter activity.
* **Memory Leak Alert:** If process memory usage grows > 100MB, trigger process restart via supervisor.
* **Pre-Trade Gate Failure:** If a gate fails, all new order events are blocked and fail closed.
