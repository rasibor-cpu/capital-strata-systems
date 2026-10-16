# CSS Deployment Package — Release Candidate (paper readiness)

**Candidate baseline:** PR #122 / `claude/css118-closeout` @ `09b2cbd1` plus integration
branch `css-final-integration` engineering closeouts (B1/B5/B6/Windows probe/docs).

**PRODUCTION_GO=NO. LIVE_READY=NO until separate owner authorization.**

## 1. Versioned release candidate
- Record the exact commit SHA of `css-final-integration` at certification time.
- Do not merge to frozen production (`9bc3c52`) without independent authorization.

## 2. Build / install
```
git checkout <rc-sha>
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
CSS_TEST_MODE=1 PYTHONPATH=. python -m pytest -q -p no:cacheprovider -rfEs
```

## 3. Environment templates
- Copy `.env.example` / host profiles from existing launcher docs.
- Required for paper profiles: `CSS_COPY_MANDATE_SIGNING_KEY` (lab key), never production anchor keys.
- Live kill switches default blocked: `CSS_LIVE_ORDER_KILL_SWITCH` unset/not ARMED.

## 4. Secrets / key custody
- See `docs/governance/CSS118_B3_LEDGER_ANCHOR_CUSTODY.md`.
- Broker tokens: OS secret stores only (DPAPI / equivalent). Never commit.

## 5. Monitoring
- Supervisor heartbeat: `runtime/supervisor/css_runtime_supervisor_state.json`
- Safety flags: `GET /api/v1/safety-flags`
- Mission Control read-only broker continuity surfaces

## 6. Broker connectivity (sandbox / paper only)
- Validate OANDA / Coinbase / Questrade **read-only** and paper paths.
- Confirm live order paths remain fail-closed (`LIVE_TICKET_DISABLED_CSS118`, adapter quarantine).

## 7. Audit / reconciliation
- Trading-profile ledgers under `artifacts/trading_profiles/`
- Optional anchoring once owner enrolls keys (B3)
- `tools/verify_css_ledger_anchors.py` for independent verification

## 8. Incident response / emergency shutdown
- Kill switches independent of UI
- Emergency risk reduction exempt from consent (`test_emergency_risk_reduction_still_works_without_acceptance`)
- Pause controls: `/mobile/control/pause`

## 9. Rollback
- Revert integration commits; closeout rollback matrix in `docs/governance/CSS118_CLOSEOUT.md` §4
- Archive rather than delete `artifacts/trading_profiles/`

## 10. User documentation
- `docs/user/CSS_USER_OPERATING_MANUAL.md` + consent receipts
- Acknowledgement text enforced in `backend/trading_profiles/manual.py`

## 11. Regulatory / legal checklist (owner / counsel)
- Confirm jurisdictions, advice vs execution-only posture, performance-fee rules
- Do not invent fees; commercial programme: `docs/commercial/`

## 12. Controlled live-launch runbook (authorization gate)
Requires a **separate** owner document naming: account, capital, instruments, limits,
market-data subscriptions, emergency monitors, pause/rollback triggers.

Until that document exists and is signed: **do not** enable real-money submission.
