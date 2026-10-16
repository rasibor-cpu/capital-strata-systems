# H2: Questrade OAuth refresh-token concurrency and durable persistence (audit and fix)

Origin: finding H2 in the independent review of PR #131 at `7416fe6`. Owner: Grok. H1 and M1 (Binance weight guard) belong to Claude in #131 and are out of scope here.
Base audited: `css-final-integration` @ `a7a9bcd5`. `oauth_refresh.py`, `token_lifecycle.py` and `dpapi_refresh_token_store.py` there are byte-identical to the #131 base `a3118da`, and #131 @ `8c8cb687` does not modify them.

## Scope read
- `backend/brokers/questrade/oauth_refresh.py`: `QuestradeBoundedOAuthRefresh`, the POST-only token transport
- `backend/brokers/questrade/token_lifecycle.py`: `QuestradeTokenBundle`, `InMemoryRefreshTokenStore`, `TokenLifecycle`
- `backend/brokers/questrade/dpapi_refresh_token_store.py`: `WindowsDpapiRefreshTokenStore` (PowerShell DPAPI, CurrentUser)
- Callers:
  - `live_readonly_activation.compose_questrade_live_readonly` is the only caller that performs a refresh;
  - `mission_control_activation.QuestradeMissionControlActivation.activate` guards with an in-process lock plus an `_attempted` flag, and its own `refresh()` never performs OAuth;
  - `TokenLifecycle.refresh()` is an inert stub.
  - #131 @ `8c8cb687` adds no new refresh callers. Its `QuestradeCandles` and `get_order_history` consume the in-memory `TokenLifecycle` built by the activation, so they share whatever the activation obtained.

## Findings (pre-fix)
| ID | Severity | Finding |
|---|---|---|
| H2-1 | High | **No cross-process single-flight.** Two processes (for example launcher plus mission-control, or a restart overlap) can both load refresh token T0 and POST it. Questrade tokens are single-use, so the loser gets 401 (`QUESTRADE_AUTHORIZATION_REVOKED`). If the loser's later write happens after the winner's, it can also overwrite the store with nothing useful. |
| H2-2 | High | **The rotated token is discarded when persistence fails.** `_complete` returned `QUESTRADE_TOKEN_REPLACE_FAILED` and dropped the bundle after Questrade had already spent T0. Re-authorisation was then unavoidable. |
| H2-3 | Medium | **No in-process single-flight.** It relies on each caller's own guard (mission control has one; direct `compose_questrade_live_readonly` users do not). |
| H2-4 | Medium | **A rotated token is lost when `api_server` is rejected.** If the response carried an unacceptable `api_server`, the new refresh token was thrown away even though T0 was already spent. |
| H2-5 | Medium | **Persistence durability:** a fixed `<name>.tmp` path (two writers collide), no directory fsync on POSIX, and the exception was chained (`from exc`). The chain is not a secret leak today, because messages are codes, but it is unnecessary. The previous file was preserved (os.replace), which is good. |
| H2-6 | Low | `_powershell_protect` passes the plaintext token to PowerShell via an environment variable of the child process. Other same-user processes can read it during the call. This is pre-existing and documented, not changed here. |
| H2-7 | Info | Access tokens are memory-only, bundle fields are `repr=False`, results never include token values, and the token URL, redirect rejection and `api_server` validation are sound. |

## Fix (this PR)
- **New module `refresh_coordination.py`:**
  - an in-process lock registry keyed by the store's `coordination_key()`, or a unique per-object key;
  - `InterProcessFileLock`, which uses `fcntl.flock` on POSIX and `msvcrt.locking` on Windows, with a bounded timeout. Lock files left by a dead holder are reclaimed, because the OS releases the lock on process exit. A held lock is never broken.
- **`QuestradeBoundedOAuthRefresh.refresh()`:**
  - Peeks the token, takes the thread lock, takes the process lock, then re-reads the store under the lock.
  - Reuses a bundle another caller in this process just obtained, with no POST.
  - If another process rotated the token while this caller waited, it returns `QUESTRADE_REFRESH_ROTATED_BY_PEER` (retryable, no POST) instead of chaining a second rotation.
  - A lock timeout gives `QUESTRADE_REFRESH_LOCK_TIMEOUT` with no POST.
- **Persistence:**
  - The rotated bundle is held in a pending slot until it is durable, with bounded retries and exponential backoff.
  - On final failure the status is `DEGRADED` with `operator_action_required`, and `memory_bundle` is `None`, so no API client receives the unsaved token.
  - The next `refresh()` in this process persists the held token without a network call.
  - The spent token is never re-POSTed by this process.
- **`api_server` rejection:** the rotated refresh token is still saved through `save_refresh_token`, and the result reports `rotated_refresh_token_persisted`.
- **DPAPI store:**
  - unique `mkstemp` temp in the same directory, `fchmod 0600` (POSIX), write, flush, fsync, `os.replace`, directory fsync (POSIX);
  - the temp file is removed on any failure, and the exception carries no cause;
  - DPAPI encryption is unchanged;
  - adds `coordination_key()` and `lock_path()` (`<token file>.lock`).

## Residual risk (documented, not eliminated)
1. **Crash window:** if the process dies after Questrade returns the new token and before it is durable, the rotation is lost and the operator must re-authorise. A test asserts this is reported as revoked and not retried in a loop.
2. **Peer access token:** a process that loses the race gets `ROTATED_BY_PEER`, not an access token, because access tokens are memory-only by design. The deployment should run one live read-only session owner.
3. **Lock semantics:** advisory locks only coordinate code that uses them. `flock` on NFS and SMB network drives may not be honoured. Keep the token store on a local disk.
4. **"Protected memory":** CPython cannot pin or zero memory. The held token lives in a module-level dict with redacted reprs. It is not swappable-memory protected.
5. **DPAPI scope:** CurrentUser DPAPI protects against other Windows users and offline disk theft, not against malware running as the same user.
6. **Directory fsync on Windows:** this is not available. Durability relies on NTFS `MoveFileEx` semantics.
