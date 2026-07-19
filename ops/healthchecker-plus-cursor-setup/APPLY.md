# Apply HealthChecker+ Cursor setup

## Blocker

The Cursor GitHub App currently has write access only to `rasibor-cpu/capital-strata-systems`.
It cannot push to `rasibor-cpu/HealthChecker-` until that repo is included in the app installation.

## 1) Grant GitHub access (required)

1. Open https://cursor.com/dashboard/integrations
2. Next to GitHub, click **Manage Connections** / configure repository access
3. Include `rasibor-cpu/HealthChecker-` (or choose **All repositories**)
4. Confirm at https://github.com/settings/installations if prompted

## 2) Apply this setup to HealthChecker-

### Option A — Cloud Agent (recommended after access grant)

Start a Cloud Agent on `rasibor-cpu/HealthChecker-` and ask it to apply the patch/bundle from this artifact, or re-run: “Set up HealthChecker+ for Cursor Cloud Agents”.

### Option B — Local apply with patch

```bash
git clone https://github.com/rasibor-cpu/HealthChecker-.git
cd HealthChecker-
git checkout -b css-agent/cursor-cloud-setup-a78b
git am /path/to/0001-cursor-cloud-setup.patch
git push -u origin css-agent/cursor-cloud-setup-a78b
gh pr create --base main --title "Add Cursor Cloud Agent setup" --body "Configures HealthChecker+ for Cursor via GitHub."
```

### Option C — Bundle fetch

```bash
git clone https://github.com/rasibor-cpu/HealthChecker-.git
cd HealthChecker-
git fetch /path/to/cursor-cloud-setup.bundle HEAD:css-agent/cursor-cloud-setup-a78b
git checkout css-agent/cursor-cloud-setup-a78b
git push -u origin css-agent/cursor-cloud-setup-a78b
```

## What this setup adds

- `.cursor/environment.json` — install hook + port 8080 web terminal
- `scripts/cursor-install.sh` — idempotent checks + unit tests
- `AGENTS.md` — cloud agent guidance
- `tests/test_foot_pain_engine.py` — smoke tests for the intelligence engine
- README updates for Cursor/GitHub usage
