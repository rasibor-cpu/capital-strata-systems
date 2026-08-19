> **RC-LIVE-CONSOL-001 recovery addendum**
> Recovered onto `css-v1.0.1-maintenance` as an **offline read-only certification framework**.
> No network, credentials, funded session, or order submission. AST firewall remains mandatory.



## Explicit safety statement

**NO NETWORK. NO AUTHENTICATION. NO LIVE CONNECTION. NO EXECUTION.**

Phase 187A is architectural preparation only. It does not contact OANDA, does not
authenticate, does not start CSS runtime, does not fetch market data, and does not
submit, cancel, or modify orders. It does not arm live authority, enable
execution, or modify AntiBleed, RiskGovernor, Phase 152A, Margin, or kill switch.

## 1. Objective

Create the governance and certification framework for **ONLINE READ-ONLY** OANDA
certification so a future phase can validate connectivity and account scope under
strict read-only constraints. This phase ships contracts, a deterministic state
machine, gates, evidence packaging, execution-boundary AST checks, and offline
tests only.

## 2. Existing OANDA audit

| File | Purpose | Status | Reused? | Deprecated? | Authoritative? | Live dep? | Auth dep? | Market-data dep? | Account dep? |
|---|---|---|---|---|---|---|---|---|---|
| `backend/runtime/oanda_live_read_only_adapter.py` | Canonical LIVE read-only adapter (no order methods) | active | **reuse later** for online RO ops | no | **yes** for live RO ops | yes (when wired) | yes | yes | yes |
| `backend/runtime/oanda_readiness.py` | Credential / readiness diagnostics | active | reuse diagnostics patterns | no | yes for readiness envelope | env only in this phase | presence checks | no | presence |
| `backend/runtime/oanda_connectivity_certificate.py` | Connectivity certificate artifacts | active | reference for evidence shape | no | ops certificate | yes when run | yes | partial | partial |
| `backend/runtime/oanda_authentication_trace.py` | Auth trace diagnostics | active | reference only | no | auth tracing | yes when run | yes | no | no |
| `backend/runtime/oanda_live_read_only_operational_validation.py` | Operational validation for live RO | active | future online phase | no | ops validation | yes | yes | yes | yes |
| `backend/app/brokers/oanda_adapter.py` | Full broker adapter incl. `place_order` + live firewall | active | **do not** use for RO cert path | no (quarantined writes) | execution path (firewalled) | yes | yes | yes | yes |
| `backend/app/brokers/plugins/oanda.py` | Broker plugin registration | active | leave alone | no | plugin map | indirect | indirect | indirect | indirect |
| `backend/app/oanda_trade_smoketest.py` | Trade smoke test helper | legacy/ops | **not** for RO cert | prefer quarantine | no | yes | yes | yes | yes |
| `live_data/oanda_adapter.py` | Legacy live_data adapter | legacy | **do not reuse** | prefer deprecate | no | yes | yes | yes | yes |
| `broker_oanda.py` | Root-level broker helper | legacy/ops | avoid | candidate deprecate | no | yes | yes | yes | yes |
| `engine/brokers/oanda_paper_broker.py` | Paper broker simulation | active paper | not for online RO | no | paper only | no | no | sim | sim |
| `engine/risk/oanda_margin_adapter.py` | Margin calculations | active | separate from cert | no | margin math | no (calc) | no | no | inputs |
| `backend/app/market/providers/oanda_fixture_market_provider.py` | Phase 186A offline fixtures | active offline | **reuse offline only** | no | offline market cert | no | no | fixtures | no |
| `tools/download_oanda_m5_*.py` / `normalize_oanda_raw_to_replay.py` | Historical download / replay tools | tools | not runtime cert | n/a | data tooling | yes (tools) | yes | yes | no |
| `docs/governance/PHASE_165B_*` / certification reports | Prior auth / RO certification docs | historical | reference | n/a | historical evidence | n/a | n/a | n/a | n/a |

### Duplication

Multiple adapters and readiness helpers exist (`oanda_adapter`, live RO adapter,
legacy `live_data`, paper broker, download tools). Credential presence checks are
duplicated across readiness and the live RO adapter.

### Authoritative online provider path (recommendation)

**Single authoritative path for future ONLINE READ-ONLY certification:**

1. **Phase 187A framework** (`backend/app/market/oanda_readonly_certification/`) —
   authoritative certification state machine, contracts, gates, evidence, and
   execution boundary (this phase; offline only).
2. **`OandaLiveReadOnlyAdapter`** — authoritative *runtime* read-only I/O adapter
   for a later online validation phase (not invoked by 187A).
3. **Do not** route certification through `backend/app/brokers/oanda_adapter.py`
   (execution surface). Keep that adapter behind live firewall / write quarantine
   and out of the RO certification provider path.
4. **Do not** use Phase 186A fixture providers for online certification; they remain
   offline-only.

## 3. Contracts

Immutable dataclasses (schema_version / provider_version / framework `187A.2`):

- `OandaConnectionStatus`
- `OandaAuthenticationStatus`
- `OandaAccountStatus`
- `OandaMarketDataStatus`
- `OandaReadOnlyCertification`

Common fields: `schema_id`, `schema_version`, `provider_name`, `provider_version`,
`timestamp`, `certification_state`, `failure_reason`, `diagnostics`.

**187A-R1 lineage fields (every certification object):**

- `certification_id`
- `certification_generation`
- `certification_timestamp`
- `schema_id` / `schema_version`

Generation increments **only** through controlled revalidation success. Silent reuse
of an older certified generation is forbidden.

`OandaReadOnlyCertification.execution_authority` is always `False` and cannot be
set true.

## 4. State machine

Deterministic states:

`NOT_STARTED` → `CONFIG_PRESENT` → `CONFIG_VALIDATED` → `DNS_OK` → `TLS_OK` →
`AUTH_PENDING` → `AUTH_OK` → `ACCOUNT_OK` → `ACCOUNT_SCOPE_OK` → `MARKETDATA_OK` →
`READ_ONLY_CERTIFIED`

**187A-R1 revalidation lifecycle:**

`READ_ONLY_CERTIFIED` / prior certified lineage
→ (invalidation) → `REVALIDATION_PENDING`
→ (start) → `REVALIDATION_RUNNING`
→ (complete) → `REVALIDATED`
→ (settle) → `READ_ONLY_CERTIFIED` (new generation)

Terminal / explicit failure: `FAILED`, `BLOCKED`.

Rules:

- Advance at most one step per evaluate when required evidence flag is true.
- No silent skips.
- Invalidation **never** lands directly on `READ_ONLY_CERTIFIED` / `REVALIDATED`.
- `failed=True` / `blocked=True` force explicit terminal states with reasons.
- Offline evaluation uses injected boolean evidence only (no sockets).

## 4A. Provider fingerprint (187A-R1)

Immutable `ProviderFingerprint`:

- `provider_name`
- `provider_version`
- `adapter_version`
- `endpoint`
- `api_version`
- `schema_version`

Fingerprint hash changes invalidate prior certification until revalidated.

## 4B. Deterministic invalidation rules (187A-R1)

Triggers (always → `REVALIDATION_PENDING`, never → `CERTIFIED`):

| Trigger | Meaning |
|---|---|
| `provider_version_change` | Provider version differs |
| `adapter_version_change` | Adapter version differs |
| `endpoint_change` | Endpoint differs |
| `api_version_change` | API version differs |
| `schema_version_change` | Schema version differs |
| `certificate_rotation` | TLS/server certificate rotated |
| `credential_rotation` | Credential material rotated (presence/fingerprint only; no secrets) |

## 4C. Replay protection (187A-R1)

Reject:

- reused evidence hashes
- mismatched provider fingerprints (while locked)
- stale certification generations
- downgraded schema versions

## 4D. Evidence lineage (187A-R1)

`OandaReadOnlyEvidencePackage` also carries immutable:

- `parent_certification_id`
- `previous_evidence_hash`
- `current_evidence_hash` (alias of custody hash)
- `lineage_generation`
- `provider_fingerprint_hash`
- `certification_id`

## 5. Read-only gates

| ID | Gate | Evidence key |
|---|---|---|
| G01 | credentials present | `config_present` |
| G02 | environment valid | `config_validated` |
| G03 | endpoint valid | `config_validated` |
| G04 | DNS OK | `dns_ok` |
| G05 | TLS certificate valid | `tls_ok` |
| G06 | clock skew OK | `tls_ok` |
| G07 | authentication OK | `auth_ok` |
| G08 | account permissions OK | `account_ok` |
| G09 | account scope OK | `account_scope_ok` |
| G10 | instrument visibility | `marketdata_ok` |
| G11 | rate limits OK | `marketdata_ok` |
| G12 | schema compatibility | `config_validated` |
| G13 | provider version OK | `config_validated` |
| G14 | market freshness OK | `marketdata_ok` |

**No gate grants execution authority** (`grants_execution` always false).

## 6. Execution boundary

Proven by:

1. Framework `__getattribute__` denial of order/auth/network methods.
2. AST scan (`boundary.verify_execution_boundary`) forbidding network imports and
   order/arm/execution calls inside the Phase 187A package.
3. Contract invariant rejecting `execution_authority=True`.

Read-only provider framework cannot: submit/cancel/modify orders; arm live
authority; enable execution; modify AntiBleed / RiskGovernor / Phase 152A /
Margin / kill switch.

## 7. Evidence package

`OandaReadOnlyEvidencePackage` captures only:

- connection diagnostics (redacted)
- provider / schema versions
- latency maps
- endpoint
- timestamps
- certificate info (non-secret)
- account scope (no balances unless later approved)
- market-data quality
- gate results
- SHA-256 `evidence_hash` / `current_evidence_hash`
- lineage fields (`parent_certification_id`, `previous_evidence_hash`,
  `lineage_generation`, fingerprint hash, certification id)

Redaction strips tokens, secrets, passwords, API keys, authorization material, and
balance/NAV/equity fields.

## 8. Tests

`tests/test_phase187a_oanda_readonly_certification_framework.py` — offline only:

- all forward transitions
- stall / fail / block paths
- no skip-ahead
- gates never grant execution
- schema/provider versions
- execution method denial
- credential redaction
- evidence hashing
- AST boundary
- generation increments (controlled revalidation only)
- provider fingerprint stability / change invalidation
- evidence lineage integrity
- replay protection
- invalidation → `REVALIDATION_PENDING` only
- revalidation transitions

## 9. Future online validation (explicitly out of scope for 187A)

A later phase may:

- perform DNS/TLS checks
- authenticate read-only
- verify account scope and instrument visibility
- publish a `READ_ONLY_CERTIFIED` evidence package from live diagnostics

That phase must still forbid order submission and must not weaken AntiBleed,
RiskGovernor, Phase 152A, Margin, or kill switch.

## 10. Non-goals (this phase)

**NO NETWORK. NO AUTHENTICATION. NO LIVE CONNECTION. NO EXECUTION.**

- NO CSS restart
- NO freeze SHA
- NO live testing
- NO broker authentication
- NO commit/push in the implementation agent step unless founder-authorized