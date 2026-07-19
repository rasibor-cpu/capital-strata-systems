# Apply HealthChecker+ Cursor setup

## Why this package lives here temporarily

Cloud Agents started on `capital-strata-systems` receive a GitHub token scoped to that repo only.
They cannot push to `rasibor-cpu/HealthChecker-` even when the Cursor GitHub App can see both repos.
A new Cloud Agent must be started **with repository = HealthChecker-**.

## Recommended: new Cloud Agent on HealthChecker-

1. Go to https://cursor.com/agents
2. Select repository **`rasibor-cpu/HealthChecker-`**
3. Prompt:

```
Apply the Cursor Cloud Agent setup for this repo.

Fetch and apply this patch onto a branch css-agent/cursor-cloud-setup-a78b:

https://raw.githubusercontent.com/rasibor-cpu/capital-strata-systems/css-agent/healthchecker-plus-cursor-setup-a78b/ops/healthchecker-plus-cursor-setup/0001-cursor-cloud-setup.patch

Then push the branch and open a PR into main.
Verify with: bash scripts/cursor-install.sh
```

## Local apply

```bash
git clone https://github.com/rasibor-cpu/HealthChecker-.git
cd HealthChecker-
git checkout -b css-agent/cursor-cloud-setup-a78b
curl -fsSL \
  https://raw.githubusercontent.com/rasibor-cpu/capital-strata-systems/css-agent/healthchecker-plus-cursor-setup-a78b/ops/healthchecker-plus-cursor-setup/0001-cursor-cloud-setup.patch \
  | git am
git push -u origin css-agent/cursor-cloud-setup-a78b
```

## What the setup adds

- `.cursor/environment.json` — install hook + port 8080 web terminal
- `scripts/cursor-install.sh` — idempotent checks + unit tests
- `AGENTS.md` — cloud agent guidance
- `tests/test_foot_pain_engine.py` — intelligence engine smoke tests
- README / gitignore / Cursor rules
