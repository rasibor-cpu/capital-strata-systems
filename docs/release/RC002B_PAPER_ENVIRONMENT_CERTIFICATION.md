# RC-002B — Paper Environment Certification

**Programme:** CSS Release Gate A.5 / RC-002B  
**Baseline HEAD:** `d8673ae6ba7fb3540d07fbed4be4082f8ae0f116`  
**Branch:** `css-unified-consolidation-2026-07-13`  
**Scope:** Environment configuration and governance only  
**Does not authorize:** production deployment, live trading, OV-002, release certification

---

## Purpose

Certify a dedicated **paper-trading environment profile** suitable for re-running  
**RC-003 Controlled Paper Trading Acceptance** after Phase 1 stopped on unsafe  
local `.env` live-enable flags.

## Canonical profile artifacts

| Artifact | Role | Secrets |
| --- | --- | --- |
| `.env.paper.example` | Committed certified template | None (placeholders / flags only) |
| `.env.paper` | Local operator copy (gitignored) | Operator-supplied practice credentials only if needed; never commit |
| `CSS_BROKER_ENVIRONMENT_PROFILE=PAPER` | Explicit profile selection | N/A |

Existing runtime loaders already support `.env.paper` via  
`backend.runtime.broker_environment_profiles` / `load_css_runtime_environment`.  
**No application logic was changed for RC-002B.**

## Required certified flag values

| Key | Required value |
| --- | --- |
| `CSS_BROKER_ENVIRONMENT_PROFILE` | `PAPER` |
| `CSS_ENV` | `paper` (non-production) |
| `DEFAULT_EXECUTION_MODE` | `paper` |
| `ALLOW_LIVE_TRADING` | `false` |
| `COINBASE_ENABLE_LIVE_ORDERS` | `false` |
| `COINBASE_ENABLE_LIVE_TRADING` | `false` |
| `OANDA_ENABLE_LIVE_ORDERS` | `false` |
| `OANDA_ENABLE_LIVE_TRADING` | `false` |
| `OANDA_ENV` | `practice` |
| `CSS_LIVE_ORDER_KILL_SWITCH` | `1` (engaged for RC-003 safety) |
| `ENABLE_RISK_GOVERNOR` | `true` |
| `ENABLE_EXECUTION_GATES` | `true` |

## Operator activation (RC-003)

1. Copy `.env.paper.example` → `.env.paper` (local only).
2. Ensure local `.env` does **not** leave live-enable keys truthy on disk for RC-003  
   Phase 1 file audits (`ALLOW_LIVE_TRADING`, `COINBASE_ENABLE_LIVE_ORDERS`, etc.).  
   Prefer aligning those keys to `false` and `CSS_ENV=paper` in the local `.env`  
   used for the RC-003 campaign.
3. Start with `launch_css.bat` only after Phase 1 passes.
4. Before any paper order, confirm HTTP probes:
   - `GET /api/v1/live-execution-authority` → `execution_authority=false`,  
     `can_live_execute=false`, `live_authority_state=BLOCKED`
   - `GET /api/runtime-mode` → paper / advisory posture (not LIVE armed)

## Static live-execution certification (no runtime start)

`load_css_runtime_environment(..., mode="paper")` returns fail-closed defaults:

- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`
- `advisory_only=true`

`evaluate_live_execution_authority({})` with empty/incomplete evidence yields  
`live_authority_state=BLOCKED` and `can_live_execute=false` (all authority  
conditions fail closed).

Bootstrap additionally forces truthy `LIVE_ENABLE_KEYS` to `false` when the  
canonical `.env` is loaded — preserving fail-closed even if a local file was  
misconfigured historically.

## Side-effect confirmation

RC-002B must not modify:

- runtime authority modules
- execution authority modules
- certification logic
- broker adapters
- safety / kill-switch / mobile control source

Only environment templates, gitignore allow-list for the example file, and this  
governance document are in scope.

## RC-003 readiness

After local `.env.paper` exists and local live-enable disk flags are `false`:

**READY_TO_RERUN_RC003** (environment gate only — still does not authorize live  
trading, production, or OV-002).

---

*End of RC002B_PAPER_ENVIRONMENT_CERTIFICATION.md*
