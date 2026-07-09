# Capital Strata Systems (CSS) Executive Operations Guide

This guide is the manual for CSS operators, explaining how to utilize the Consolidated Command Centre, evaluate decision intelligence, review audit logs, and inspect readiness checks.

---

## 1. Operating the Command Centre

The Consolidated Command Centre consolidates all telemetry metrics into a single view. To fetch this view programmatically:
```python
# Initialize Dashboard Service
view = dashboard_service.get_operational_command_centre_view()

# View unified statuses
print(view["broker_health"])
print(view["portfolio_health"])
print(view["diagnostics"])
```

### Operators Action Checklist:
1. **Monitor Broker Health:** If `broker_health` is `AMBER` or `RED`, check API connection status in the logs.
2. **Review Heartbeats:** Verify `diagnostics.heartbeat_age_seconds` is less than 60 seconds.
3. **Assess Exposure:** Ensure `capital_deployment.mode` remains strictly `ADVISORY`.

---

## 2. Reading Decision Intelligence

Decision Intelligence rationales are published inside the `ExecutiveDecisionBrief`:
```python
brief = brief_engine.generate_brief(...)
intel = brief["decision_intelligence"]

print(f"Confidence Level: {intel['confidence_level']}")
print(f"Why Now: {intel['why_now']}")
print(f"Rejected Alternatives: {intel['rejected_alternatives']}")
```
Operators must check that the `confidence_level` is greater than 80.0% before presenting recommendation briefs to the Investment Committee.

---

## 3. Auditing Subsystem Changes

Audit logs are compiled automatically. To export a formal markdown report for compliance audits:
```python
report_md = dashboard_service.get_audit_trail_report()
with open("audit_report.md", "w") as f:
    f.write(report_md)
```

---

## 4. Runbook: Preparing for Production Pilot (Phase 162)

To verify the system is ready to launch the Phase 162 pilot:
1. **Confirm Dotenv Config:** Execute the infrastructure checks.
2. **Run Readiness Evaluation:** Verify readiness view:
   ```python
   readiness = dashboard_service.get_canonical_readiness_view()
   assert readiness["go_no_go"] == "GO"
   ```
3. **Validate Production Boundaries:** Check safety triggers:
   ```python
   validation = dashboard_service.get_production_validation_view()
   assert "safety_validation_advisory_only_locked" in validation["informational_findings"]
   ```
