# CSS dotenv / CI Environment Action Record

**Task:** CSS-PKG-D-001
**Date (UTC):** 2026-08-19
**Authority:** Environment/tooling record only
**Runtime import redesign:** **not performed**

## Facts

| Item | Status |
| --- | --- |
| Declared dependency | `python-dotenv==1.2.2` in repository `requirements.txt` |
| Also declared | `python-dotenv` (unpinned) in `backend/requirements.txt` |
| Cloud Agent venv at CSS-CONSOL-CERT-001 | `ModuleNotFoundError: No module named 'dotenv'` |
| Tests importing `dotenv` directly | Generally **no** |
| Production modules importing `dotenv` at **module import time** | Yes |

This is a **TEST ENVIRONMENT GAP** plus an **ARCHITECTURAL IMPORT-BOUNDARY** problem. It is **not** a TAI / MI-EXT / CONSOL product failure.

## Production import sites (do not change in this package)

| Module | Import |
| --- | --- |
| `backend/runtime/environment_bootstrap.py` | `from dotenv import dotenv_values` |
| `backend/runtime/broker_environment_profiles.py` | `from dotenv import dotenv_values` |
| `backend/app/brokers/credential_loader.py` | `from dotenv import load_dotenv` |
| `dashboard/runtime/broker_credential_check.py` | `from dotenv import load_dotenv` |

Typical collection chain:

`test → launcher / Mission Control web app / api_bridge / frontend_contract → broker diagnostics or OANDA auth trace → credential_loader / environment_bootstrap → dotenv`

`OandaAdapter.__init__` calls `load_credentials("oanda", ...)` when credentials are omitted, so firewall tests fail at construction even when they collect.

## Suites blocked in CSS-CONSOL-CERT-001 (exact)

Collection ERROR (~269 tests): phase166a, 152a, 152b, 153b, 153i, 154b, 155ab, mc002, mc003, mc004, canonical order-limit config, trade-tab ranking, css_mobile_launcher, ov002 R1 blocker repairs, mobile live-order kill-switch.

Runtime dotenv failures after collect: `test_oanda_live_firewall.py` (30), two `test_security_phase_alpha.py` OANDA constructor cases.

## Recommended action order

1. **CI / Cloud Agent image alignment (first).** Install already-declared `python-dotenv==1.2.2` from `requirements.txt` in the agent/CI image. Do **not** add live `.env` secrets. Installing the pin is **not** AR-040 broker evidence and **not** live authorization.
2. **Separately queue** (future governed task, not Package D): lazy-import `dotenv` inside bootstrap/credential **functions** so offline unit collection does not require the package; optional empty-credentials path for `OandaAdapter` unit tests.
3. Do **not** treat dotenv collection errors as merge breakage of intelligence or offline-market packages.

## Explicit non-actions (this package)

- Did not install `python-dotenv` in this environment.
- Did not redesign imports.
- Did not add secrets.
- Did not enable live network or broker sessions.
