# QRO / Phone Integration Validation Gate

Prepared 2026-09-13.

This gate is designed to run immediately after the staged no-commit merge created by `sync_qro_and_stage_phone_merge.ps1`.

It intentionally does not create a commit.

## Gate sequence

1. Require the dedicated integration branch.
2. Refuse unresolved merge conflicts.
3. Refuse protected runtime files in staging.
4. Scan staged diff for obvious credential/token material.
5. Compile backend/dashboard/engine/tests.
6. Discover and run QRO/Questrade/Simulator focused tests.
7. Run the full pytest suite with a private Windows basetemp.
8. Perform a static scan for broker mutation method names.
9. Stop for manual review before any integration commit.

## Command

```powershell
Set-Location 'C:\rasib\source\capital-strata-systems-QRO001'
powershell -ExecutionPolicy Bypass -File scripts\ops\validate_qro_phone_integration.ps1
```

A PASS means the staged integration is test-clean. It does not itself authorize live execution, live Questrade access, or a merge to main.
