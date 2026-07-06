# Phase 155D - Canonical Broker Credential Diagnostics

## Purpose

Phase 155D adds a broker-independent credential diagnostics layer used before broker authentication. The layer explains why authentication cannot proceed and publishes a consistent dashboard/API schema for Coinbase and OANDA.

This phase is diagnostic-only. It does not enable live execution, broker execution arming, Live Micro-Pilot arming, order submission, order cancellation, or order modification.

## Canonical Output

Every broker publishes the same credential diagnostic fields:

- `broker`
- `credentials_present`
- `key_present`
- `secret_present`
- `private_key_present`
- `token_present`
- `account_present`
- `base_url_present`
- `pem_valid`
- `jwt_generated`
- `authentication_attempted`
- `authenticated`
- `failure_reason`
- `recommended_action`
- `severity`
- `timestamp`
- `missing_credentials`

The payload contains presence booleans and diagnostic metadata only. Secret values, private keys, tokens, passphrases, signatures, and raw credentials are never exposed.

## Canonical Failure Reasons

The canonical failure reason set includes:

- `MISSING_CREDENTIALS`
- `KEY_MISSING`
- `SECRET_MISSING`
- `PRIVATE_KEY_INVALID`
- `PEM_INVALID`
- `JWT_GENERATION_FAILED`
- `JWT_SIGNATURE_INVALID`
- `TOKEN_INVALID`
- `ACCOUNT_ID_MISSING`
- `AUTH_FAILED`
- `UNAUTHORIZED`
- `FORBIDDEN`
- `NETWORK_ERROR`
- `DNS_ERROR`
- `TLS_ERROR`
- `TIMEOUT`
- `RATE_LIMIT`
- `BROKER_UNAVAILABLE`
- `CLOCK_SKEW`
- `UNKNOWN_ERROR`

## Integration

Broker readiness consumes canonical diagnostics and replaces generic credential blocker text with specific authority reasons such as `Account ID Missing`, `Token Invalid`, `JWT Generation Failed`, or `Authentication Failed`.

LiveExecutionAuthority consumes the diagnostic payload only to explain a blocked state. It remains fail-closed and still requires the complete live authority chain before execution can become true.

Dashboard and mobile expose the read-only `/api/v1/broker-credential-diagnostics` endpoint and a Broker Credential Diagnostics card.

## Safety

Phase 155D does not change:

- Unified Trade Gate
- Margin Gate
- AntiBleedGuard
- Kill Switch
- LiveExecutionAuthority requirements
- Phase 152A CAD 20 Governor
- broker execution controls

Broker execution remains disabled unless the existing independent authority chain passes in full.
