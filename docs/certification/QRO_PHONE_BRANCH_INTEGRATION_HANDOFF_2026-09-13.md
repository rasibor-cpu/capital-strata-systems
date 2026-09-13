# QRO ↔ Phone Branch Integration Handoff

Prepared: 2026-09-13

This handoff is intentionally fail-closed. It does not merge anything into main and does not authorize live broker execution.

## Known source heads

- Expected local QRO head: `feaa42bd036bf1dc945aef09c306b6d28f82530f`
- QRO branch: `css-qro001-questrade-readonly-provider`
- Remote phone branch: `css-phone-remote-work-2026-09-13`
- Phone branch validated baseline before closeout evidence: `b9ab7fc9d579ae5e0622c6ab9979131a234b4a82`
- Phone branch current closeout lineage contains Simulator & Academy Phases 1–5, governance repair, cloud regression workflow, repository-completeness repairs, and certification evidence.

## One-time desktop action

Run:

```powershell
Set-Location 'C:\rasib\source\capital-strata-systems-QRO001'
powershell -ExecutionPolicy Bypass -File scripts\ops\sync_qro_and_stage_phone_merge.ps1
```

If the script is not yet present locally because the phone branch has not been fetched, first run only:

```powershell
Set-Location 'C:\rasib\source\capital-strata-systems-QRO001'
git fetch origin css-phone-remote-work-2026-09-13
git show origin/css-phone-remote-work-2026-09-13:scripts/ops/sync_qro_and_stage_phone_merge.ps1 > $env:TEMP\sync_qro_and_stage_phone_merge.ps1
powershell -ExecutionPolicy Bypass -File $env:TEMP\sync_qro_and_stage_phone_merge.ps1
```

## What the script does

1. Requires a clean QRO worktree.
2. Requires the exact expected QRO branch and SHA.
3. Fetches origin.
4. Pushes the QRO branch and verifies the remote SHA.
5. Fetches the phone-work branch.
6. Creates a new integration branch from the exact QRO head.
7. Performs a `--no-commit` merge only.
8. Aborts if protected runtime files appear.
9. Aborts if obvious secret/token patterns appear.
10. Stops before commit so the merged diff can be reviewed and tested.

## What the script does NOT do

- no force push;
- no main-branch modification;
- no automatic merge commit;
- no live Questrade request;
- no credential handling;
- no order submission/cancellation;
- no transfer, withdrawal, deposit, funding, or money movement.

## Post-merge gate

After a clean staged merge:

1. inspect `git diff --cached --stat` and `git diff --cached`;
2. run QRO focused tests;
3. run Simulator & Academy tests;
4. run the full regression suite;
5. run static safety/secret scans;
6. reconcile any cloud compatibility file against the newer QRO implementation;
7. only then make an explicit integration commit.

QRO-004X begins after this reconciliation, on the integrated newer QRO lineage.
