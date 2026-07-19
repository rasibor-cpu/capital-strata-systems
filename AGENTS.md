# REA Capital Trading Engine / Capital Strata Systems (CSS)

Python multi-asset algorithmic trading engine (crypto, FX, futures, options) with
governance, risk gates, ledger/accounting, and audit certification. See `README.md`,
`RUNBOOK.md`, and `.codex-instructions.md` for product/operating context.

## Cursor Cloud specific instructions

**Canonical repo/environment:** Always use the GitHub repo/environment
`rasibor-cpu/capital-strata-systems` (checked out at `/workspace` on the Linux VM) until
explicitly advised otherwise. This is the same product formerly named
`REA-capital-trading-engine`; ignore/do not switch to that old name. There is no Windows
`C:\` filesystem on the Cloud VM — Windows paths in docs/launchers refer to a local machine only.

This is a **Python-only** project (Python 3.12 in this environment; CI targets 3.11).
There is no Node/JS toolchain — the files under `ui/` and `frontend/` are loose static
assets with no `package.json`, build step, or lockfile.

### Environment
- Dependencies live in a virtualenv at `.venv/` (gitignored). Activate with
  `. .venv/bin/activate`, or call binaries directly as `.venv/bin/python` / `.venv/bin/pytest`.
- The startup update script recreates `.venv` and installs deps, so you normally do not
  need to install anything manually.
- Copy `.env.example` → `.env` for local config. Default modes (`SIMULATION` / `PAPER` /
  `REPLAY`) need **no** live broker credentials; live OANDA/Coinbase/etc. adapters are only
  exercised if you supply real tokens.

### Dependency gotchas (important)
- `requirements.txt` is **incomplete**: it omits `pandas`, `numpy` (imported by many engine
  modules) and `beautifulsoup4` (used by dashboard tests). The update script installs these.
- **FastAPI must be pinned to `0.115.x`.** `requirements.txt` is unpinned; the latest FastAPI
  (0.139+, which ships Starlette 1.x) breaks `APIRouter` route merging via `include_router`,
  so `dashboard/runtime/api_bridge.create_app()` registers zero API routes. This silently
  breaks the web dashboard API and two dashboard tests. The update script installs
  `fastapi==0.115.6` to override the latest.

### How to run / test / lint
- Core engine end-to-end smoke (governed decision pipeline, no broker calls):
  `python run_css.py` — emits a JSON trace of caps → sizing → governance gate. A
  fail-closed `BLOCK` is expected/safe behavior, not an error.
- Tests: `python -m pytest -q` (config in `pytest.ini`, `testpaths = tests`).
- Lint / syntax validation (what CI runs): `python -m compileall .`
- Web dashboard (read-only demo, optional):
  `python -m uvicorn dashboard.web.web_app:app --host 0.0.0.0 --port 8091`
  then open `/dashboard`, `/positions`, `/risk-governance`, `/broker`. API under `/api/v1/*`.
- Mobile web app (optional): `python -m uvicorn dashboard.mobile.mobile_app:app --port 8090`.

### Known pre-existing breakages (NOT environment issues — do not "fix" as part of setup)
- `scripts/css_live_dashboard.py` imports `backend.data.price_feed`, a module that does not
  exist in the repo. This causes ~31 collection **errors** in `tests/scripts/*`. The rest of
  the suite (450 tests) passes.
- `run_demo_end_to_end.py` and root `main.py` reference stale APIs/modules
  (`EngineLoop(min_bars_required=...)`, top-level `taxonomy`) and fail on run. Use
  `run_css.py` for an end-to-end engine smoke instead.
- `css_live_dashboard_v5.py` is a retired non-canonical entrypoint and exits immediately by design.
