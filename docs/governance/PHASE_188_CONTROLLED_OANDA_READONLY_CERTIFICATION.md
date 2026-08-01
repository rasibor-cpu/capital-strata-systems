# PHASE 188 — Controlled OANDA Read-Only Certification

## Explicit safety statement

Phase 188 performs **controlled read-only** certification only. It does not enable
live trading, does not designate a freeze SHA, and does not grant execution
authority.

- Execution remains impossible through the certified provider.
- `backend.app.brokers.oanda_adapter.OandaAdapter` is **not** used for certification.
- Canonical runtime adapter: `backend.runtime.oanda_live_read_only_adapter.OandaLiveReadOnlyAdapter`.

## 1. Provider

| Item | Value |
|---|---|
| Package | `backend/app/market/oanda_controlled_readonly/` |
| Provider | `CertifiedOandaReadOnlyProvider` |
| Version | `188.1` |
| Runtime adapter | `OandaLiveReadOnlyAdapter` only |
| Transport | `OandaReadOnlyHttpTransport` (GET/HEAD only) |
| Framework | Phase 187A / 187A-R1 state machine + lineage |

## 2. Endpoint

Endpoint is taken from `OANDA_BASE_URL` when credentials are present.

- LIVE pattern: `https://api-fxtrade.oanda.com`
- PRACTICE pattern: `https://api-fxpractice.oanda.com`
- Non-HTTPS endpoints fail `config_validated`

Controlled network is enabled only when credentials already exist (or a test
`read_client` is injected). Missing credentials → fail closed, no network.

## 3. Read-only validation

Validates: credentials, environment, endpoint, DNS, TLS, authentication, account
scope, instrument visibility, market quote, provider/schema versions, freshness,
latency.

Deterministic diagnostics are emitted into the Phase 187A evidence package with
redaction of tokens, API keys, secrets, passwords, and account IDs (suffix-only).

Balances / NAV / equity are **not** included in certification evidence
(`financials_excluded=true`).

## 4. Evidence

Immutable evidence includes:

- provider fingerprint
- certification generation / lineage
- diagnostics (redacted)
- timestamps / latency
- endpoint
- gate results
- market freshness
- schema / provider versions
- SHA-256 hashes

## 5. Execution firewall

Static + runtime checks prove the certified provider cannot:

- submit / cancel / modify orders
- arm live authority / enable execution
- modify AntiBleed / Margin / RiskGovernor / Phase 152A

AST scan rejects imports of `backend.app.brokers.oanda_adapter` from Phase 188
modules. Transport hard-denies non-GET methods and order endpoints.

## 6. Limitations

- This environment had **no OANDA credentials** at implementation time → live
  broker contact was **not** performed.
- Full online certification requires founder-supplied credentials and explicit
  controlled-network run.
- Phase 188 does not change AntiBleed, ExecutionGate, RiskGovernor, Margin, or
  live authority policy.

## 7. Security

- Secrets never written to evidence.
- Account IDs redacted to last-4 form.
- No write HTTP verbs on the RO transport.
- Fail closed on missing credentials.

## 8. Future execution path

Execution remains outside Phase 188. A future live-execution phase would still
require live authority, kill switch, AntiBleed, Phase 152A, founder GO/NO-GO,
and freeze SHA — none of which Phase 188 unlocks.
