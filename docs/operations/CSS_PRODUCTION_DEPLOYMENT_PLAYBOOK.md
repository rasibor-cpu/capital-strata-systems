# Capital Strata Systems (CSS) Production Deployment Playbook

**Programme:** Release Gate 2 — Final Close-Out (AR-016)  
**CD mode:** `manual_with_approvals`  
**Automated production deploy:** **NOT PRESENT**  
**Safety posture:** `DISABLED / BLOCKED / FAIL_CLOSED / ADVISORY_ONLY`

This playbook defines controlled deployment runbooks, startup verifications, rollback triggers, and emergency incident response. It does **not** claim automated CD.

Authority companion: `docs/governance/CSS_DEPLOYMENT_APPROVAL_FRAMEWORK.md`

---

## 0. Controlled CD path (Gate 2)

```text
RC branch → Gate-2 CI green (compile + bounded pytest)
  → Dual authorization (Lead Engineer + Operations Manager)
  → Pre-deployment checklist complete
  → Manual deploy to named host / artifact
  → Post-start verification
  → Rollback target identified
```

### Promote checklist

- [ ] Release SHA recorded (`git rev-parse HEAD`)
- [ ] Gate-2 CI workflow green for that SHA
- [ ] Dual sign-off recorded
- [ ] `advisory_only` / live-trading-blocked controls confirmed
- [ ] Rollback owner named
- [ ] Post-start health/ops check planned (`/health`, `/ops/health` where applicable)

### Rollback target

- Previous known-good SHA + prior artifact/config snapshot
- Immediate fail-closed: set live trading blocked / disarm paths per §3

---

## 1. Deployment Checklist

### Pre-Deployment

- [ ] Confirm environment files for the target profile are present (no secrets in git).
- [ ] Verify that advisory-only / live-trading-blocked controls remain engaged.
- [ ] Confirm Gate-2 CI green for the candidate SHA.
- [ ] Confirm dual authorization completed.

### Pilot / controlled host startup

- [ ] Launch the approved host entrypoint for the environment (e.g. `launch_css.bat` for local pilot).
- [ ] Confirm startup diagnostics do not claim live execution authority.
- [ ] Access Mission Control / Command Centre in read-only / advisory posture as applicable.

---

## 2. Startup Verification & Health Check

Prefer fail-closed observations over fabricated GO scores:

```python
# Ops host health (Wave 2/3 activation)
# GET /ops/health on the headless API when enabled

# Do NOT treat simulated readiness fixtures as production authorization.
```

If using dashboard readiness helpers, treat `GO` only when independently verified evidence exists for the release SHA. Missing evidence → **NO-GO**.

---

## 3. Rollback Runbook (Emergency Disarm)

If rollback criteria are met (connectivity loss, unexpected execution arming, critical health RED):

1. **Trigger Manual Disarm:** Set live-trading blocked / disarm supervisor controls.
2. **Revert to rollback SHA** if the promote is unsafe.
3. **Notify Risk / Operations:** Record reason, SHA, and timestamp.

---

## 4. Incident Response

* **Flapping Connection:** If reconnect attempts exceed policy limits, suspend trading adapter activity.
* **Memory Leak Alert:** If process memory usage grows beyond policy, restart via supervisor.
* **Pre-Trade Gate Failure:** New order events remain blocked (fail closed).

---

## 5. Explicit non-claims

* This playbook does not automate production deployment.
* This playbook does not authorize live trading.
* This playbook does not mint Phase 181 certification.
