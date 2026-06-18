# CSS Emergency Shutdown Runbook

## Purpose

This runbook defines immediate actions for stopping controlled CSS paper-trading operations during a safety, runtime, session, dashboard, broker-mode, or evidence integrity concern.

This document is documentation-only. It does not change runtime, execution, broker, dashboard, credential, risk, margin, or trading logic.

## Emergency Shutdown Triggers

Initiate emergency shutdown if any of the following occur:

* Live mode is enabled unexpectedly.
* Live execution appears armed.
* Broker execution is attempted during a paper-only run.
* Credentials, tokens, API keys, or account identifiers are printed or exposed.
* Trade gates are bypassed or unavailable.
* Session state is corrupt, unknown, or cannot be closed.
* Legal acceptance cannot be verified.
* Dashboard displays paper and live state inconsistently.
* Runtime crashes in a way that may compromise evidence or safety.
* Robert or an authorized operator instructs shutdown.

## Immediate Actions

1. Stop initiating new paper trades.
2. Stop dashboard or runtime loop input if safe to do so.
3. Do not attempt to place, cancel, or modify broker orders.
4. Do not edit credentials or `.env` files.
5. Preserve terminal output and logs.
6. Record the time, branch, HEAD, operator, and observed trigger.
7. If live mode is suspected, treat the incident as CRITICAL until reviewed.

## Session Handling

1. Attempt graceful session close if the runtime supports it and doing so does not risk additional execution.
2. If graceful close fails, preserve the error output.
3. Do not manually edit session database records during the emergency.
4. Mark session state as requiring review in the incident notes.

## Audit Preservation

Preserve:

* Terminal output.
* Dashboard output or screenshots.
* Runtime logs.
* Evidence files already captured.
* Git branch and HEAD.
* Any exception traceback.
* Operator actions taken.

Do not delete failed-run evidence. Failed-run evidence is certification evidence.

## Recovery Preparation

Before restart:

1. Identify whether the incident was runtime, dashboard, broker-mode, credential, session, legal acceptance, risk, margin, or PnL related.
2. Confirm no live order was placed.
3. Confirm credentials were not modified.
4. Confirm the working tree has no unintended runtime changes.
5. Follow `docs/operations/CSS_RECOVERY_AND_RESTART_RUNBOOK.md`.

## Emergency Shutdown Checklist

| Step | Required |
| --- | --- |
| Stop new paper trade creation | Yes |
| Preserve logs/output | Yes |
| Record branch and HEAD | Yes |
| Record operator and time | Yes |
| Attempt graceful session close if safe | Yes |
| Confirm no credential changes | Yes |
| Confirm no broker execution if possible | Yes |
| Create incident record | Yes |
| Robert review for HIGH/CRITICAL incidents | Yes |

## Post-Shutdown Rule

Do not resume controlled paper operation until the incident is classified, evidence is preserved, and the restart checklist is complete.
