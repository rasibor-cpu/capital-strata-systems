# CSS Enterprise RC1.1 — Final Acceptance and Deployment Record

## Release identity

- Release: CSS Enterprise RC1.1
- Branch: `css-unified-consolidation-2026-07-13`
- Starting HEAD: `0e0fb6eaba76b5c470d761b85e3e714be0438de1`
- Release commit: the Git commit containing this record; its immutable SHA is
  recorded in the Phase 180C operator output and remote branch.

## Accepted scope

- canonical CSS Branding Service and approved icon family;
- PWA manifests, service-worker controls, and centralized mobile metadata;
- shared report watermark and executive document branding;
- Reports Center routing/viewer remediation;
- canonical broker balance presentation and paper-margin remediation;
- Phase 180A and Phase 180B governance documentation;
- mobile PWA installation guide;
- structurally recovered `backend/app/main.py`, based on historical commit
  `7005e36b77b789349f0e7abbb4d3ae3e9bf837fd`, with the later legitimate
  read-only `/alerts` route preserved;
- focused and bounded certification tests.

## Excluded artifacts

The following are deliberately excluded from release staging:

- `CSS_Overnight_Runtime_Review.txt` — local operational review;
- `runtime_reports/` — generated runtime and test evidence;
- caches, bytecode, logs, databases, session state, local environment files,
  credentials, tokens, private keys, and any uncertain local artifact.

## Verification evidence

- `python -m py_compile backend/app/main.py`: exit `0`;
- direct `backend.app.main` import: `MAIN_IMPORT_OK`, exit `0`;
- focused main/API recovery: `14 passed`, no failures, skips, or deselections;
- `python -m compileall backend dashboard tests`: exit `0`;
- authoritative RC1.1 suite: `205 passed`, no failures, skips, or deselections;
- `git diff --check`: required exit `0`.

The sole pytest warning is the existing Starlette `TestClient` deprecation
warning.

## Branding certification

The Phase 180A icon/PWA implementation and Phase 180B canonical Brand Service,
watermark, and document standard are accepted. The approved source artwork and
asset version remain unchanged. PWA and report rendering remain read-only.

## Safety controls

Acceptance does not authorize execution. Required posture remains:

- `DISABLED`;
- `BLOCKED`;
- `FAIL_CLOSED`;
- `ADVISORY_ONLY`.

No authentication, RBAC, broker readiness, kill switch, order limit, runtime
mode, secret authority, or live-trading control was weakened.

## Push acceptance

The push is accepted only when:

```text
git rev-parse HEAD
git rev-parse origin/css-unified-consolidation-2026-07-13
```

return the same SHA. The exact push output and matching SHA are retained in the
Phase 180C operator record.

## Desktop pull procedure

Run this block manually on the Desktop server. It does not discard changes and
stops before any CSS restart.

```powershell
$ErrorActionPreference = "Stop"
$Repo = "C:\rasib\source\capital-strata-systems"
$Branch = "css-unified-consolidation-2026-07-13"

Set-Location $Repo

$PreDeploymentBranch = (git branch --show-current).Trim()
$PreDeploymentSha = (git rev-parse HEAD).Trim()
$PreDeploymentStatus = git status --short

Write-Output "PreDeploymentBranch=$PreDeploymentBranch"
Write-Output "PreDeploymentSha=$PreDeploymentSha"
git status --short

if ($LASTEXITCODE -ne 0) {
    throw "Unable to inspect Desktop worktree."
}
if ($PreDeploymentStatus) {
    throw "DEPLOYMENT_REFUSED: Desktop worktree is not clean. Preserve and review it; do not discard changes."
}

git fetch origin
if ($LASTEXITCODE -ne 0) { throw "git fetch failed" }

git checkout $Branch
if ($LASTEXITCODE -ne 0) { throw "branch checkout failed" }

git merge --ff-only "origin/$Branch"
if ($LASTEXITCODE -ne 0) { throw "fast-forward pull failed" }

$ExpectedSha = (git rev-parse "origin/$Branch").Trim()
$DeployedSha = (git rev-parse HEAD).Trim()
Write-Output "ExpectedSha=$ExpectedSha"
Write-Output "DeployedSha=$DeployedSha"
if ($DeployedSha -ne $ExpectedSha) {
    throw "DEPLOYMENT_REFUSED: deployed SHA does not match origin."
}

.\.venv\Scripts\python.exe -m py_compile backend\app\main.py
if ($LASTEXITCODE -ne 0) { throw "main.py compile smoke failed" }

.\.venv\Scripts\python.exe -m compileall backend\common\branding dashboard\reports_viewer dashboard\mobile launcher -q
if ($LASTEXITCODE -ne 0) { throw "focused compile smoke failed" }

.\.venv\Scripts\python.exe -m pytest `
  tests\test_backend_app_main_recovery.py `
  tests\test_phase180b_branding_certification.py `
  tests\test_phase180a_mobile_pwa_icon_remediation.py `
  -q --maxfail=1
if ($LASTEXITCODE -ne 0) { throw "post-pull smoke suite failed" }

Write-Output "SOURCE_PULL_AND_SMOKE_COMPLETE"
Write-Output "STOP: Do not restart CSS until operator review authorizes it."
Write-Output "Rollback reference: $PreDeploymentSha"
```

## Post-restart validation checklist

- backend is online;
- heartbeat is active;
- supervisor is running;
- runtime mode is unchanged;
- live authority remains blocked unless separately and explicitly authorized;
- authentication and role enforcement work;
- mobile dashboard loads;
- manifest and service worker return HTTP 200;
- regular and maskable icon routes return HTTP 200;
- Reports Center pages load;
- paginated viewer completes without stalling;
- watermark is faint, proportional, and does not obscure content;
- absent balances render as unavailable rather than fabricated zero;
- broker readiness and all execution safety gates remain unchanged.

## Phone PWA replacement

1. Remove the existing CSS Mission Control icon.
2. Uninstall the old CSS web app entry if Android lists it as installed.
3. Open the operator-approved canonical CSS mobile URL in Chrome.
4. Choose **Install app**, not a browser shortcut.
5. Confirm standalone display.
6. Confirm no Chrome badge.
7. Confirm the approved CSS icon is clean and correctly sized.

## Rollback procedure

Use the `PreDeploymentSha` printed by the deployment block. This preserves the
new release branch and creates a separate rollback branch; it does not reset,
clean, or delete local files.

```powershell
$ErrorActionPreference = "Stop"
$Repo = "C:\rasib\source\capital-strata-systems"
$PreDeploymentSha = "<PASTE_PreDeploymentSha_FROM_DEPLOYMENT_OUTPUT>"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Evidence = "C:\rasib\evidence\css-rc11-rollback-$Stamp"

Set-Location $Repo
New-Item -ItemType Directory -Force -Path $Evidence | Out-Null
git branch --show-current | Set-Content "$Evidence\branch.txt"
git rev-parse HEAD | Set-Content "$Evidence\head.txt"
git status --short | Set-Content "$Evidence\status.txt"
git diff | Set-Content "$Evidence\working-tree.diff"

$Status = git status --short
if ($Status) {
    throw "ROLLBACK_REFUSED: worktree is not clean. Evidence was preserved; review without discarding changes."
}

git cat-file -e "$PreDeploymentSha^{commit}"
if ($LASTEXITCODE -ne 0) { throw "Rollback SHA is not a valid local commit." }

$RollbackBranch = "rollback/rc11-$Stamp"
git checkout -b $RollbackBranch $PreDeploymentSha
if ($LASTEXITCODE -ne 0) { throw "Rollback branch checkout failed." }

.\.venv\Scripts\python.exe -m py_compile backend\app\main.py
if ($LASTEXITCODE -ne 0) { throw "Rollback compile validation failed." }

Write-Output "ROLLBACK_SOURCE_READY"
Write-Output "RollbackBranch=$RollbackBranch"
Write-Output "RollbackSha=$(git rev-parse HEAD)"
Write-Output "STOP: restart only through the approved operator runbook."
```

After an operator-authorized restart, repeat the complete post-restart
validation checklist above. Rollback does not authorize live trading.
