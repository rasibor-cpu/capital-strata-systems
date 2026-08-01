# PHASE 191 — Enterprise Certification Registry

## Explicit safety statement

**NO RUNTIME ACTIVATION. NO BROKER AUTHENTICATION. NO BROKER CONTACT. NO LIVE EXECUTION. NO FREEZE SHA.**

The Enterprise Certification Registry is the single authoritative offline source for
broker, provider, asset, operational readiness, evidence, and governance status.
Execution authority is always false.

## 1. Registry architecture

Package: `backend/app/governance/enterprise_certification_registry/`

| Component | Role |
|---|---|
| `CertificationRegistryEntry` | Immutable entry model |
| `RegistryRepository` | Authoritative in-memory store |
| `RegistryValidator` | Deterministic validation rules |
| `RegistryQuery` | Read queries by type/broker/asset/phase |
| `RegistryAudit` | Registration audit view |
| `RegistrySnapshot` | Immutable point-in-time capture + hash |
| `RegistryExporter` | Redacted export payload |
| `RegistryHash` | Canonical SHA-256 hashing |
| `assert_valid_certification_claim` | Runtime rule: no claim without entry |
| `seed_phase_registry` | Seeds Phases 187A–191 |

## 2. Entity model

Required fields (declared, never inferred):

`registry_id`, `entity_type`, `entity_name`, `broker_type`, `asset_class`,
`provider_name`, `provider_version`, `schema_version`, `capability_profile`,
`certification_status`, `operational_readiness`, `paper_status`,
`read_only_status`, `live_status`, `execution_authority` (**always false**),
`authorization_ttl_status`, `certification_generation`, `evidence_hash`,
`last_validation`, `next_validation`, `suspension_status`, `blocker_list`.

### Entity types

`BROKER`, `PROVIDER`, `ASSET`, `MARKET_DATA`, `FX`, `MICROSTRUCTURE`,
`PLUGIN`, `GOVERNANCE`, `PHASE`, plus extensible `CUSTOM`.

## 3. Governance rules

1. Every certification phase registers itself (`phase:187A` … `phase:191`).
2. Future phases register new `PHASE` entries without redesign.
3. Nothing may claim certification without `assert_valid_certification_claim`.
4. Suspended/revoked entries cannot be claimed as active.
5. `live_status` remains non-authorized in Phase 191.
6. `execution_authority` cannot be true (constructor + validator + claim checks).

## 4. Validation rules

- Unique `registry_id`
- Known status enumerations
- RO certified entries require `evidence_hash`
- No secret material in exports (redaction)
- Snapshot hash covers all entries deterministically

## 5. Runtime integration

Phase 191 does **not** start CSS or arm brokers. Integration surface is the claim
guard for future callers:

```text
assert_valid_certification_claim(repo, registry_id=...)
```

Invalid/missing → `CertificationClaimError`. Valid entry still has
`execution_authority=false`.

## 6. Seeded coverage (187–190 reuse)

| ID | Type | Status summary |
|---|---|---|
| phase:187A–191 | PHASE | Framework / review registrations |
| broker:OANDA/COINBASE/IBKR | BROKER | PARTIAL / PARTIAL / BLOCKED |
| provider:* | PROVIDER | 187A/188/189 frameworks |
| asset:FX/CRYPTO | ASSET | Partial |
| market_data / fx / microstructure | specialty | Framework ready / blockers listed |
| governance:RC004 | GOVERNANCE | PAPER_ONLY; live unlock absent |

## 7. Future extension strategy

1. Add enum value or use `CUSTOM` / `PLUGIN`.
2. Declare full `CertificationRegistryEntry` (no inference).
3. `repository.register(entry)` after validation.
4. Include `phase_refs` for lineage.
5. Capture `RegistrySnapshot` for evidence packages.

## 8. Non-goals

- No runtime activation
- No broker authentication
- No live execution unlock
- No freeze SHA designation
