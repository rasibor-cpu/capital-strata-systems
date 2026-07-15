# Mission Control Runtime Validation

## Purpose

This runbook validates Mission Control runtime evidence without mutating CSS
runtime or broker state.

## Validation Steps

1. Fetch `/mission-control/api/state`.
2. Fetch `/mission-control/api/runtime`.
3. Fetch `/mission-control/api/heartbeat`.
4. Fetch `/mission-control/api/page-metadata`.
5. Fetch `/mission-control/api/final-certification`.
6. Compare runtime id and runtime hash across responses.
7. Confirm final certification overall status.
8. Confirm safety flags remain fixed.

## Expected Fail-Closed Conditions

Mission Control must fail closed for missing runtime artifacts, stale heartbeat,
corrupt runtime payloads, missing portfolio evidence, missing broker evidence,
source mismatch, hash mismatch, non-finite values, invalid permissions, or
unsafe safety flags.

## Evidence Handling

Do not record secrets, tokens, account identifiers, credential paths, private
key material, or JWT values in runtime validation notes.
