# HealthChecker+

HealthChecker+ Web App (iOS Compatible Version)

LocalStorage-first health tracking UI with trend intelligence screens and a Python foot-pain diagnostic helper under `backend/intelligence/`.

## Quick start

```bash
python3 -m http.server 8080 --bind 127.0.0.1
```

Open [http://127.0.0.1:8080/](http://127.0.0.1:8080/).

## Tests

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -q
```

## Cursor Cloud Agents (GitHub)

This repository is configured for Cursor Cloud Agents:

1. Grant the Cursor GitHub App access to `rasibor-cpu/HealthChecker-`  
   Dashboard → [Integrations](https://cursor.com/dashboard/integrations) → GitHub → include this repository (or all repos).
2. Start a Cloud Agent on this repo from [cursor.com/agents](https://cursor.com/agents), or comment `@cursor` on a PR/issue.
3. Agents use `.cursor/environment.json`:
   - `install` runs `scripts/cursor-install.sh` (idempotent checks + unit tests)
   - `web` terminal serves the app on port `8080`
4. See `AGENTS.md` for layout, commands, and cloud-specific guidance.
