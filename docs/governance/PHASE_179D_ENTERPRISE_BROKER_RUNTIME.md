# Phase 179D — Enterprise Broker Runtime

## Certified boundary

The Enterprise Broker Runtime accepts only `SecretHandle`, `OAuthHandle`,
`RuntimeSecretLease`, and `BrokerCapabilityContract` objects. Credential
material remains encrypted in the Enterprise Vault and is available only as a
short-lived, consumer-bound memory view inside an audited lease context.

Legacy credential dictionaries and broker-owned token stores are compatibility
paths. They cannot be classified as Enterprise Managed and prevent production
certification until retired.

## Questrade runtime

The Questrade runtime is advisory-only. It supports account discovery and
aliases, balances, buying power, margin metadata, holdings, equity and option
positions, watchlists, market permissions, quotes, and option-chain metadata.
Its default provider is disabled. It contains no OAuth authorization, refresh,
browser, order, trading, or execution implementation.

Provider data must be injected through the read-only enterprise provider
contract. Provider failures produce canonical fail-closed advisory states and
never generate replacement values.

## Authorities

Holdings:

1. Broker Holdings
2. Enterprise Cache
3. CSS Derived
4. Unavailable

Collateral:

1. Broker Buying Power
2. Broker Margin
3. Broker Option Collateral
4. Enterprise Estimate
5. Unavailable

All accepted rows retain provenance. Missing data remains unavailable.

## Runtime state priority

`FAILURE > DATA_DEPENDENCY_BLOCKED > PROVIDER_UNAVAILABLE > STALE >
PARTIAL_DATA > NO_CURRENT_OPPORTUNITIES > ADVISORY_READY`

## Safety posture

- Execution: `DISABLED`
- Execution authority: `BLOCKED`
- Runtime: `FAIL_CLOSED`
- Usage: `ADVISORY_ONLY`
- OAuth authorization and refresh: unavailable
- Default Questrade transport: disabled
- Order and trading endpoints: absent

Production activation remains prohibited until legacy broker credential paths
are retired and the focused and bounded regression suites pass.
