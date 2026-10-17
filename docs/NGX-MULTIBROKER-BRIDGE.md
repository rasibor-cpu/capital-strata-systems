# NGX multi-broker and registrar bridge (initial read-only core)

## Sources
- Investment One, Meristem, CardinalStone, Coronation Securities: **broker candidates**
- GT Registrars: **registrar candidate**, used for corroboration of dividend/shareholder records, not as a trading broker.

All API statuses default to `not_authorized`. No authenticated API integration has been established by this change. No orders, credential storage, network calls or production configuration are included.

## Input contract
`reconcile_ngx_positions(broker_positions, registrar_records)` accepts pre-normalized authorized snapshots. Broker rows: `broker`, `account_key` (opaque non-secret alias, **not** CSCS/CHN), `symbol`, `quantity`, optional `currency` (NGN only). Registrar rows: `registrar`, `symbol`, `quantity`. Decimal quantities must be finite and nonnegative. Duplicate broker/account/symbol rows fail closed.

Consolidated quantities are sourced **only from broker snapshots**. Registrar quantities are corroboration-only and are never added to portfolio holdings. A registrar mismatch is marked `UNVERIFIED`, not treated as an automatic trade or adjustment. This simple first-pass comparison assumes same beneficial owner and snapshot date; future versions must align record dates, beneficial owner, pending settlement, corporate actions and registrar scope before making stronger reconciliation claims.

## Next implementation gates
1. Confirm broker-specific API/statement import contracts and data-use permissions.
2. Add encrypted local/managed secret handling and separate CSCS/CHN identity mapping; never commit account identifiers.
3. Implement broker-specific authenticated read-only transports with mocked contract tests.
4. Add GT Registrars dividend entitlements, payments, withholding and claim-status reconciliation with provenance and deduplication.
5. Add dated valuation, FX, liquidity and fee models; do not infer PnL from share quantities.
6. CI tests, independent review, and explicit approval before any production integration. **No live execution.**

## Stanbic IBTC Pension Managers
Added as a **pension provider**, not as Stanbic IBTC Stockbrokers and not as a trading broker. The initial `summarize_pension_snapshot` accepts a normalized, user-supplied NGN balance and an opaque account alias; labels it unverified and keeps it **outside CSS deployable trading capital**. No pension API access, pension account credentials, or automated pension transactions are implemented. Future permitted read-only statements/API imports may add RSA balance, contribution history, fund type, unit values and pension performance, subject to provider permission and user verification.

## User-configurable institutions
The named Nigerian institutions are **examples only**, not an allowlist. `register_institution(source_id, kind, display_name=...)` creates fail-closed metadata for arbitrary user-defined brokers, registrars and pension providers. The normalized reconciliation functions accept custom source IDs. Registering an institution does **not** grant an API connection, credential access or trading authority. A production implementation must persist per-user institutions and connector assignments in a secure datastore, add UI flows, enforce tenant isolation, and support bank/other provider types after suitable data contracts are defined. The present module is a reusable core, **not yet a user-facing add-institution workflow**.
