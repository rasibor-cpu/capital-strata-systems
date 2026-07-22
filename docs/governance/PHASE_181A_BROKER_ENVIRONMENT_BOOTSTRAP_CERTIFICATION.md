# Phase 181A — Broker Environment Bootstrap Certification

## Certification scope

Phase 181A determines why Desktop-launched CSS processes did not receive the
canonical repository `.env`, introduces one deterministic and redacted
bootstrap, and verifies the change without restarting CSS, authenticating a
broker, contacting a broker API, staging, committing, or pushing.

Certified starting point:

- Branch: `css-unified-consolidation-2026-07-13`
- HEAD: `4ea738d86c167373deccbe4edf217e929de4414d`
- Initial `git diff --check`: PASS
- Existing untracked paths were preserved.

## Root cause

The failure had three cooperating causes:

1. `backend/runtime/broker_environment_profiles.py::_load_profile_files`
   selected a broker profile before considering the legacy canonical `.env`.
   No broker profile selector exists in the current `.env`, so the unselected
   branch skipped `.env` and all profile files. The launcher therefore called
   an environment loader, but no broker settings entered the process.
2. Desktop startup is fragmented. `launch_css.bat` uses the supervised
   launcher, `launchers/CSS Dashboard.cmd` launches
   `scripts/css_live_dashboard.py` directly, and
   `launchers/CSS Mobile Server.cmd` launches the port-8090 ASGI module
   directly. The direct runtime script established the repository root and
   loaded the environment only after numerous broker/runtime imports; the
   port-8090 app used a separate request-time `load_dotenv` path.
3. Legacy credential helpers reloaded `.env` later than canonical startup.
   This created inconsistent precedence and allowed profile aliases to compete
   with explicit process values. Child processes inherited only the parent
   snapshot available when `CSSServiceManager` was constructed.

The current working directory was not the canonical file-resolution defect:
the profile loader already received a repository root. The defect was profile
selection preventing `.env` loading, late/direct entry points, and competing
loaders.

## Preserved process evidence

Ten CSS-related Python processes were active before implementation. Their
sanitized command identities included:

- `launcher.css_runtime_launcher`
- `scripts/css_live_dashboard.py`
- `launcher.css_mobile_launcher`
- `uvicorn dashboard.mobile.mobile_app:app --port 8090`
- `uvicorn dashboard.web.web_app:app --port 8000`

Observed process IDs were `5764`, `6508`, `12132`, `12480`, `15368`, `16904`,
`20920`, `21356`, `21924`, and `24568`. No process was stopped or restarted.

## Startup sequence

### Supervised stack

1. `launch_css.bat` resolves the repository root, sets `PYTHONPATH`, changes
   directory, and runs `.venv\Scripts\python.exe -m
   launcher.css_runtime_launcher`.
2. `launcher/css_runtime_launcher.py` resolves the root and calls
   `load_css_runtime_environment` before importing the supervisor, launcher
   configuration, or service manager.
3. `load_css_runtime_environment` invokes the centralized canonical bootstrap.
4. The supervisor starts in the parent process.
5. The initialized parent environment is copied, `PYTHONPATH` is set to the
   repository root, and the copy is supplied to both managed children.
6. Managed children start `scripts/css_live_dashboard.py` and
   `launcher.css_mobile_launcher`.
7. Broker selection and adapter validation occur later in the runtime script.

### Direct Desktop dashboard

1. `launchers/CSS Dashboard.cmd` changes to the repository root.
2. It runs `scripts/css_live_dashboard.py`.
3. The script now resolves and inserts the repository root, then invokes the
   canonical loader before importing broker startup, readiness, diagnostics,
   or adapter modules.

### Port 8090 mobile server

1. `launchers/CSS Mobile Server.cmd` changes to the repository root.
2. It runs Uvicorn with `dashboard.mobile.mobile_app:app`.
3. Module import invokes the canonical bootstrap before broker and dashboard
   consumers are imported.

### Port 8765 launcher

`launcher.css_mobile_launcher` already called
`load_css_runtime_environment` at the beginning of module import. That loader
now delegates to the centralized bootstrap, so the direct and supervised
port-8765 paths use the same contract.

`start_css.bat` and `start_css.ps1` do not exist in this repository. The actual
root batch entry point is `launch_css.bat`.

## Bootstrap architecture

`backend/runtime/environment_bootstrap.py` is the sole canonical `.env`
bootstrap introduced by this phase.

Properties:

- repository root resolved from the module path or an explicit root;
- canonical `.env` resolved by absolute path;
- idempotent, lock-protected initialization per environment mapping and root;
- `dotenv_values` parsing with no implicit current-working-directory search;
- existing process values take precedence;
- truthy live-enable variables are the only precedence exception and are
  forced to `false`;
- duplicate reporting contains names and occurrence counts only;
- private-key references are checked for presence, file type, and readability
  without reading their contents;
- diagnostics contain no environment values, credentials, account IDs, URLs,
  hashes, or private paths;
- no broker client import, broker authentication, or broker network call;
- execution is always reported disabled, blocked, unarmed, and advisory-only;
- canonical real `.env` loading is skipped when imported by pytest, while
  explicit temporary environment mappings remain testable.

`load_css_runtime_environment` uses an isolated copy for profile analysis when
no explicit mode/profile is supplied. This preserves the initialized process
environment for child inheritance while profile certification remains
fail-closed.

## Safe `.env` audit

The canonical `.env` exists and is readable.

Configuration findings:

- Coinbase identity: PRESENT
- Coinbase private-key reference: PRESENT
- OANDA token: PRESENT
- OANDA account identifier: PRESENT
- Referenced Coinbase key files: absolute, present, regular files, readable
- Explicit broker environment profile selector: NOT SET

Duplicates use last-occurrence-wins semantics:

- `COINBASE_KEY_NAME`: two occurrences; second wins
- `COINBASE_ENABLE_LIVE_ORDERS`: two occurrences; second wins
- `OANDA_API_KEY`: two occurrences; second wins

Conflicting Coinbase private-key aliases are present. The file was not
normalized or rewritten.

Safety findings:

- `ALLOW_LIVE_TRADING` is truthy in the file.
- `COINBASE_ENABLE_LIVE_ORDERS` is truthy in the file.
- OANDA live-enable flags are false.

The bootstrap blocks the two truthy file values and installs `false` in the
process environment. No credential value was changed.

## Files changed

- `.gitignore` — explicitly permits the new canonical runtime bootstrap source
  under the otherwise generated-runtime exclusion.
- `backend/runtime/environment_bootstrap.py` — centralized bootstrap and
  redacted diagnostics.
- `backend/runtime/live_environment_loader.py` — earliest canonical delegation
  and non-destructive profile analysis for unselected startup.
- `backend/app/brokers/credential_loader.py` — centralized loading and
  deterministic explicit/profile alias precedence.
- `dashboard/runtime/broker_credential_check.py` — removes duplicate canonical
  `.env` loading.
- `dashboard/mobile/mobile_app.py` — early direct-ASGI bootstrap.
- `scripts/css_live_dashboard.py` — moves root and environment initialization
  before broker imports.
- `scripts/start_css_mobile_app.py` — bootstraps the alternative mobile entry.
- `tests/test_phase181a_broker_environment_bootstrap.py` — focused fake-value
  bootstrap, safety, startup, reference, and inheritance tests.
- `broker_environment_bootstrap_verification.txt` — sanitized one-shot
  verification artifact.
- This certification record.

No launcher batch file, credential file, `.env`, authentication control, RBAC
rule, broker readiness gate, order limit, kill switch, or execution authority
was modified.

## Verification results

### Compilation

- Changed-file `py_compile`: PASS, exit 0
- `python -m compileall backend dashboard launcher tests -q`: PASS, exit 0

### Focused and broker regressions

- Phase 181A focused plus canonical credential suites: 34 passed
- Broker/mobile/launcher/safety regression excluding the independently failing
  Phase 153i file: 129 passed, 1 deprecation warning
- Credential profile and discovery regression: 21 passed

### Outstanding regression

`tests/test_phase153i_live_execution_authority.py::
test_phase153i_startup_summary_reconciles_operator_intent_with_authority`
fails because `format_live_startup_summary` does not emit the expected
`Authority Reason: Credentials Missing` line. The same test fails in isolation.
Phase 181A did not modify `backend/runtime/startup_summary.py`; the failure is
independent of environment bootstrap behavior. It was not bypassed or changed.

## Controlled one-shot dry run

The separate process completed with exit 0 and wrote
`broker_environment_bootstrap_verification.txt`.

Sanitized result:

- canonical `.env`: exists and readable
- loaded entries: 33
- duplicates: 3
- Coinbase identity and private-key reference: visible
- OANDA token and account identifier: visible
- all reported private-key references: present, files, readable
- `ALLOW_LIVE_TRADING`: DISABLED after bootstrap
- `COINBASE_ENABLE_LIVE_ORDERS`: DISABLED after bootstrap
- OANDA live-enable flags: DISABLED
- execution allowed: false
- live trading blocked: true
- broker execution armed: false
- advisory only: true
- broker authentication attempted: false
- broker network attempted: false
- secrets redacted: true

## Safety certification

The implementation does not grant execution authority. It does not initialize
or authenticate a broker client. It does not perform a live connectivity test.
It leaves authentication, RBAC, readiness, order limits, kill switches, and
execution firewalls unchanged. The running CSS services retain their original
process environments until a separately authorized restart.

## Restart recommendation

**NO-GO for controlled restart at this time.**

The Phase 181A bootstrap itself passes focused tests, compilation, dry-run, and
the affected broker/mobile/launcher regressions. However, the requested safety
regression gate is not fully green because the isolated Phase 153i startup
summary assertion remains failing. A controlled restart should require an
explicit disposition or narrowly scoped correction of that independent
regression, followed by a complete green rerun.

## Rollback plan

Before any restart, rollback consists of restoring the modified tracked files
to certified SHA `4ea738d86c167373deccbe4edf217e929de4414d` and removing only the
Phase 181A new files. The existing `.env`, credentials, runtime artifacts, and
pre-existing untracked files must remain untouched. Re-run `py_compile`,
`compileall`, focused tests, and `git diff --check` before considering a later
restart.
