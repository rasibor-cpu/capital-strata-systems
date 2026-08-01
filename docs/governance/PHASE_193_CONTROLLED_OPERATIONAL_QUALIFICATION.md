# PHASE 193 — Controlled Multi-Broker Read-Only Operational Qualification

**Programme:** CSS RC-LIVE / Multi-Broker Readiness
**Phase:** 193
**Branch:** `css-rc-live-001-candidate`
**Starting HEAD (post Phase 192):** `b15c69f2a6a6ca604846c7353f3100c8d407b20c`
**Type:** Offline qualification framework only
**Score formula:** `193.2-hardened`
**Status:** HARDENED — READY FOR COMMIT REVIEW — **STOP BEFORE COMMIT**

### Explicit boundary

**NO NETWORK · NO AUTH · NO EXECUTION · NO RUNTIME ACTIVATION · NO FREEZE SHA · NO LIVE TRADING**

Qualification never implies execution authority. `execution_authority` is always `false`.
RC-004 remains **`LIVE_TRADING_NOT_AUTHORIZED`**.

Package: `backend/app/brokers/operational_qualification/`

---

## 1. Objective

Prepare a broker-independent **controlled operational qualification** workflow for all
supported brokers while remaining completely read-only and offline.

Reuses Phase 187–192 infrastructure (capability profiles, presence-only precheck, RC-004,
Enterprise Certification Registry + claim guard).

---

## 2. Hardened scoring model (`193.2-hardened`)

Three separate scores:

| Score | Meaning |
| --- | --- |
| `implementation_maturity_score` | Declared implementation / capability maturity (0–100) |
| `operational_readiness_score` | Config/registry/governance operational readiness (0–100) |
| `aggregate_qualification_score` | `floor((impl + ops) / 2)` after mandatory caps |

`readiness_score` is an alias of `aggregate_qualification_score`.

### Mandatory caps

| Condition | Cap |
| --- | --- |
| `NOT_CONFIGURED` or credentials absent | `operational_readiness_score <= 25` |
| invalid / missing / suspended registry | `operational_readiness_score = 0` |
| implementation `BLOCKED` | `aggregate_qualification_score <= 25` |
| `read_only_qualification == NOT_READY` | stage may never be `QUALIFIED` or `READ_ONLY_READY` |
| execution authority | always `false` |

### Readiness labels (from aggregate)

| Aggregate | Label |
| --- | --- |
| 0–24 | `BLOCKED` |
| 25–49 | `FOUNDATION_ONLY` |
| 50–69 | `PARTIAL` |
| 70–84 | `PRECHECK_READY` |
| 85–99 | `READ_ONLY_READY` |
| 100 | `QUALIFIED` |

Labels describe score bands only. **Scores alone cannot advance state.**

---

## 3. State model and constraints

| State | Meaning |
| --- | --- |
| `NOT_STARTED` | Initial / gates incomplete |
| `PRECHECK_READY` | Configuration present + offline precheck gates |
| `CONFIG_READY` | Endpoint configured |
| `AUTH_READY` | Credential keys present (not authenticated) |
| `READ_ONLY_READY` | Requires authenticated online result |
| `QUALIFIED` | Requires authenticated online result + completion gates |
| `BLOCKED` | Hard fail-closed terminal |

Hard constraints:

- missing configuration (no endpoint) → cannot be `PRECHECK_READY` or above
- missing credentials → cannot reach `AUTH_READY`
- no authenticated online result → cannot reach `READ_ONLY_READY` or `QUALIFIED`
- Phase 193 always sets `authenticated_online=false` (no broker contact)

---

## 4. Evidence model

Immutable evidence includes:

- qualification_id, broker, asset class, provider, schema
- capability profile, registry generation, RC-004 posture
- qualification stage
- `implementation_maturity_score`, `operational_readiness_score`, `aggregate_qualification_score`
- `readiness_label`, `mandatory_gate_results`, `score_formula_version`, `blocker_count`
- blocker list, evidence hash, timestamp
- `execution_authority=false`

Hash = SHA-256 of canonical JSON over material facts (sorted blockers).
Secret values are never copied into evidence.

---

## 5. Empty-environment expectation

With empty env (no credentials / endpoints):

- stages remain at `NOT_STARTED` or `BLOCKED` (never `PRECHECK_READY+`)
- operational scores are capped (`<= 25` or `0` if registry invalid)
- labels typically `FOUNDATION_ONLY` / `PARTIAL` / `BLOCKED`
- `read_only_qualification` remains `NOT_READY`
- live execution certification remains `NOT_AUTHORIZED`

---

## 6. Registry / RC-004 / fail-closed

Authoritative registry: Phase 191. Fail closed on absent/suspended/stale/fingerprint/scope.
RC-004 live posture must remain denied. RO TTL (`READ_ONLY_OPERATIONAL`) ≠ live-authority TTL.

---

## 7. Remaining blockers

- Authenticated controlled online RO (future phase)
- Freeze SHA not designated
- OANDA/Coinbase live money path not certified
- IBKR roadmap-excluded / suspended
- Binance dedicated RO adapter not started
- Plugin capabilities must be explicitly declared + registered
- Live-authority TTL incomplete
- Founder live GO absent

---

## 8. Future authenticated read-only qualification procedure

Design only (not executed in Phase 193):

1. Founder approves controlled online window.
2. Operator supplies credentials out-of-band (never logged in evidence).
3. Run Phase 189 RO TTL issuance (`READ_ONLY_OPERATIONAL` only).
4. Perform GET-only account/market checks under Phase 187A/188 constraints.
5. Set authenticated-online gate true only with sealed redacted evidence.
6. Do **not** arm live authority, clear kill switch, or designate freeze.

---

## 9. Non-claims

Phase 193 does not authenticate, contact brokers, restart CSS, designate a freeze SHA,
enable live trading, or alter AntiBleed / Margin / RiskGovernor / Phase 152A / kill switch.
