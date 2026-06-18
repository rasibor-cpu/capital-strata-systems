# Phase 108B Secret and Environment Configuration Framework

## A. Secret Inventory
The following logical secrets are required for Capital Strata Systems (CSS) but must **never** be stored in the repository:
- `OANDA_BEARER_TOKEN`: Authorizes connection to the OANDA v20 API.
- `COINBASE_API_KEY` / `COINBASE_API_SECRET`: Authorizes connection to the Coinbase Advanced Trade API.
- `JWT_SECRET_KEY`: Authorizes and signs internal authentication tokens for the dashboard.
- `DATABASE_URL` (Production): Connection string to the remote secure PostgreSQL/TimescaleDB cluster.

## B. Environment Variable Inventory
CSS relies on strict environment variable toggles to dictate execution modes. These are not secrets but are critical runtime bounds:
- `REA_ENGINE_MODE`: Must be set to `SIMULATION`, `PAPER`, or `LIVE`. Defaults to `SIMULATION`.
- `REA_LIVE_ARM`: Must be `1` to authorize the execution gate. Defaults to `0`.
- `REA_CONFIRM_LIVE`: Must be `1` to confirm dual-key arming. Defaults to `0`.
- `OANDA_ENABLE_LIVE_TRADING`: Must be `True` to allow OANDA adapter egress.
- `ACCOUNT_EQUITY`: Canonical baseline capital snapshot.

## C. Required Production Secrets
To operate in a production Live environment, a remote secure key vault (e.g., AWS Secrets Manager, HashiCorp Vault) must provision the following at runtime:
1. `JWT_SECRET_KEY` (Strong cryptographic random).
2. Live `OANDA_BEARER_TOKEN` (Not the paper `fxpractice` token).
3. Production `DATABASE_URL` (pointing to the VPC-bound canonical DB).
4. `REA_ENGINE_MODE=LIVE`, `REA_LIVE_ARM=1`, `REA_CONFIRM_LIVE=1`.

## D. Secret Ownership Matrix
- **Runtime Nodes**: Only have read access to the specific environment variables they are provisioned with at startup. They cannot fetch arbitrary keys from the vault.
- **CI/CD Pipeline**: Only has access to paper/simulation credentials for integration testing. No live credentials exist in GitHub Actions.
- **Operations Governors**: The designated risk administrators who physically inject or rotate the live tokens in the vault.

## E. Rotation Procedures
1. **OANDA/Coinbase Keys**: Must be revoked at the broker level and regenerated every 90 days. The new key is placed into the secure vault, and the CSS runtime nodes are restarted.
2. **JWT Secret**: Rotated every 180 days. A rotation instantly invalidates all active sessions, forcing a re-authentication against the new secret boundary.
3. **Database URI**: Passwords rotated annually or upon operator departure.

## F. Deployment Profiles

### Development
- `REA_ENGINE_MODE=SIMULATION`
- `REA_LIVE_ARM=0`
- `OANDA_ENABLE_LIVE_TRADING=False`
- Secrets: Empty or generic test stubs. Database is local SQLite.

### Paper Trading
- `REA_ENGINE_MODE=PAPER`
- `REA_LIVE_ARM=1`
- `OANDA_ENABLE_LIVE_TRADING=False` (Adapter natively routes to fxpractice if `OANDA_ENVIRONMENT=practice`)
- Secrets: Read-only or practice API tokens.

### Production
- `REA_ENGINE_MODE=LIVE`
- `REA_LIVE_ARM=1`
- `REA_CONFIRM_LIVE=1`
- `OANDA_ENABLE_LIVE_TRADING=True`
- Secrets: Real production tokens injected strictly at boot by the secure orchestrator.

## G. Secret Loading Rules
1. **No Disk Caching**: Tokens are loaded into memory (`os.getenv()`) and never written to disk logs or dashboards.
2. **Fail-Closed Missing Secrets**: If a secret is omitted (e.g., `OANDA_BEARER_TOKEN` is `None`), the adapter natively raises an exception and halts initialization.
3. **Lazy Initialization**: Adapters only evaluate secrets when called upon.

## H. Prohibited Practices
- **NO** committing `.env` files.
- **NO** hardcoding default fallback tokens in code.
- **NO** printing `os.environ` or request headers in application logs.
- **NO** using production tokens in local developer environments.

## I. Production Configuration Readiness
With this framework documented, CSS successfully closes GAP-108-01. The repository architecture fully supports externalized secret management, ensuring the codebase is inherently disconnected from live operational risks until explicitly provisioned by a secure remote authority.
