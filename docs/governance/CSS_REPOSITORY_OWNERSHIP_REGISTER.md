# CSS Repository Ownership Register

**Document type:** Governance ownership authority  
**Remediation:** AR-003 (Release Gate 2)  
**Effective date:** 2026-07-21  
**Baseline SHA:** `4ea738d86c167373deccbe4edf217e929de4414d`  
**Companion:** `.github/CODEOWNERS`

This register is the authoritative map of **accountable roles** for CSS repository domains and Critical remediation items. GitHub user/team bindings are recorded here when assigned by the Executive Sponsor; until then, role ownership is mandatory for Gate 2 execution.

No runtime behaviour is defined or changed by this document.

---

## 1. Accountable roles

| Role ID | Role name | Accountability |
| --- | --- | --- |
| R-EXEC | Executive Sponsor | Final Gate 2 / production-claim approval; owner assignment |
| R-LEAD | Lead Engineer | Trading, execution, lifecycle, API integrity, engineering ARs |
| R-OPS | Platform Operations | Runtime, health, OAT, endurance ops evidence |
| R-SEC | Security Officer | Credentials, authn/authz, secrets, broker write boundaries |
| R-BROKER | Broker / Operations | Coinbase/OANDA/IBKR readiness evidence and adapter boundaries |
| R-REPORT | Reporting Owner | Reports Centre, institutional MVP, executive reporting honesty |
| R-CERT | RC1 Certification Authority | Phase 181 production certification package |
| R-DEVOPS | DevOps / Lead Engineer | CI/CD, deployment playbooks, evidence automation |
| R-QA | Quality Engineering | Regression suites, Phase 153i, test evidence custody |
| R-GOV | Governance Approver | Release-status supersession, ownership register maintenance |

---

## 2. Critical domain ownership

| Domain | Primary paths | Primary owner | Backup |
| --- | --- | --- | --- |
| Runtime | `backend/runtime/`, `launcher/` | R-OPS | R-LEAD |
| Trading / Execution | `backend/engine/`, `backend/execution/`, `engine/` | R-LEAD | R-OPS |
| Asset lifecycle / persistence | `backend/execution/canonical_trade_lifecycle.py`, `backend/app/persistence/` | R-LEAD | R-OPS |
| Brokers | `backend/app/brokers/`, `backend/brokers/`, `backend/runtime/*oanda*`, `backend/runtime/*coinbase*` | R-BROKER | R-SEC |
| Security / Auth | `backend/security/`, `backend/app/auth/`, `dashboard/auth/` | R-SEC | R-LEAD |
| Reporting | `backend/reports_center/`, `backend/executive_reporting/`, `backend/financial_reporting/`, `backend/executive_intelligence/` | R-REPORT | R-LEAD |
| Certification / Readiness | `backend/certification/`, `backend/validation/`, `backend/governance/` | R-CERT | R-OPS |
| Health / Operations Centre | `backend/operations/`, `backend/monitoring/` | R-OPS | R-CERT |
| Deployment / CI | `.github/workflows/`, `docs/deployment/`, `docs/operations/*DEPLOY*` | R-DEVOPS | R-LEAD |
| Documentation / Release status | `docs/release/`, `README.md`, `CSS_V1_MASTER_COMPLETION_AUDIT.md` | R-GOV | R-LEAD |
| Tests / QA evidence | `tests/`, `pytest.ini` | R-QA | R-LEAD |
| Mission Control / Dashboards | `dashboard/mission_control/`, `dashboard/web/`, `dashboard/mobile/` | R-LEAD | R-OPS |

---

## 3. Critical AR ownership (Gate 2)

Every Critical remediation must have a named role owner before engineering execution.

| AR ID | Title | Owner |
| --- | --- | --- |
| AR-001 | Reconcile contradictory production GO claims | R-GOV *(CLOSED)* |
| AR-002 | Clean worktree and evidence custody | R-OPS + R-GOV |
| AR-005 | Resolve or waive Phase 153i regression | R-QA + R-LEAD |
| AR-006 | Designate singular paper trading authority | R-LEAD |
| AR-007 | Replace synthetic unified-execution acceptance | R-LEAD |
| AR-008 | Align equities taxonomy and strict persistence | R-LEAD |
| AR-009 | Eliminate fail-open empty-check scoring | R-OPS |
| AR-010 | Fail-closed missing telemetry in HealthValidator | R-OPS + R-CERT |
| AR-011 | Capture verified Phase 181 evidence package | R-CERT |
| AR-012 | Current-SHA compile and bounded regression evidence | R-QA |
| AR-013 | Execute and archive Operational Acceptance Testing | R-OPS |
| AR-014 | Wall-clock endurance evidence | R-OPS |
| AR-015 | Backup / restore drill with measured RTO/RPO | R-OPS |
| AR-016 | Establish CI gates and controlled CD path | R-DEVOPS |
| AR-017 | Define and deliver V1 report MVP; honest catalogue | R-REPORT + R-EXEC |
| AR-022 | Real notification transports and startup wiring | R-OPS + R-SEC |
| AR-023 | Remove default credentials; strengthen auth policy | R-SEC |
| AR-024 | Authenticate mutations; durable sessions; CSRF | R-SEC + R-LEAD |
| AR-026 | Isolate/deprecate legacy executable OANDA methods | R-BROKER + R-SEC |

High-severity closed item retained for traceability:

| AR ID | Title | Owner |
| --- | --- | --- |
| AR-027 | Quarantine misleading IBKR ready health | R-BROKER *(CLOSED)* |

---

## 4. GitHub identity binding (to be completed by R-EXEC)

| Role ID | GitHub user or team | Bound date | Bound by |
| --- | --- | --- | --- |
| R-EXEC | _TBD_ | | |
| R-LEAD | _TBD_ | | |
| R-OPS | _TBD_ | | |
| R-SEC | _TBD_ | | |
| R-BROKER | _TBD_ | | |
| R-REPORT | _TBD_ | | |
| R-CERT | _TBD_ | | |
| R-DEVOPS | _TBD_ | | |
| R-QA | _TBD_ | | |
| R-GOV | _TBD_ | | |

Until bindings exist, Gate 2 uses this register as the process ownership authority. `.github/CODEOWNERS` documents path domains and defers auto-request until bindings are filled.

---

## 5. Related authorities

- Module-level runtime/execution map: `docs/governance/CSS_RUNTIME_AUTHORITY_MAP.md`
- Canonical release claims: `docs/release/CSS_CANONICAL_RELEASE_STATUS.md`
- Evidence custody: `docs/release/CSS_EVIDENCE_CUSTODY_STANDARD.md`
- Remediation backlog: `docs/release/CSS_AUDIT_REMEDIATION_REGISTER.md`

---

*AR-003 remediation artifact. Does not authorize deployment, restart, broker authentication, or live trading.*
