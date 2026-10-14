# CSS Binance Spot — Read-Only Access and Binance-Price Paper Trading

Status: **REVIEW CANDIDATE (draft PR, stacked on PR #112). Read-only and simulated only.**
`LIVE_TRADING_ALLOWED=FALSE` · `PRODUCTION_GO=NO`

## What this adds

| Capability | Credentials | Can it change anything on Binance? |
|---|---|---|
| Public Spot market data (BTCUSDT, ETHUSDT) from `data-api.binance.vision` | none | No |
| Shadow paper trading on Binance prices (`--source binance`), with all PR #112 gates | none | No: fills are simulated |
| Read-only account check: key permissions, account status, non-zero balances, recent orders and trades | read-only API key | No: GET-only client with a hard endpoint allowlist |

The read-only client can call exactly these endpoints, all with `GET`:

- `/api/v3/ping`
- `/api/v3/time`
- `/api/v3/exchangeInfo`
- `/sapi/v1/account/apiRestrictions`
- `/sapi/v1/account/status`
- `/api/v3/account`
- `/api/v3/allOrders`
- `/api/v3/myTrades`

There is no code for orders, cancels, transfers, withdrawals, margin, futures or
options. The paper runner refuses to start if the authenticated client is loaded
into its process.

## Eligibility: read this first

Authenticated access is refused unless **every** one of these holds:

1. **Operator attestation.**
   - **Where the host is right now.** It is refused for jurisdictions Binance.com
     does not serve. Canada (`CA`) and the United States (`US`) are refused.
   - **KYC country.** Nigeria (`NG`) is accepted with a review warning: confirm
     with Binance that the account is in good standing.
   - **No VPN or proxy.** You attest that no VPN or proxy is used to appear
     elsewhere.
   - **Read-only key.** You attest that the key has only "Enable Reading".
2. **Binance does not return HTTP 451** ("restricted location"). A 451 response is
   final. There is no fallback host, proxy or retry.
3. **The key's own permission report**
   (`/sapi/v1/account/apiRestrictions`) shows `enableReading=true` and **every**
   trading, withdrawal, transfer, margin, futures and options permission off.
   An unknown permission reported as on also fails.
4. **Account status is `Normal`.**

Only after all four pass does the client unlock balances and order/trade history.

**Your situation.** The account's KYC country is Nigeria, and it was opened while
you were visiting Canada.

- **If this Windows host is in Canada**, the check will stop at step 1 and must
  not be worked around. Binance.com does not serve Canada, and using a VPN to
  change location would breach Binance's terms.
- **From Canada**, the Coinbase source in PR #112 remains available for real-price
  paper observation.
- **Opening the account while visiting Canada** is a compliance question for you
  and Binance, not something this code can settle. Confirm with Binance support
  before relying on authenticated access.
- **The restricted-country list** in `backend/binance_readonly/eligibility.py`
  reflects Binance's published restrictions as known when this was written.
  Re-verify it against Binance's current Terms of Use.

## Step 0: check the API key you already created (on binance.com)

1. Go to **Account → API Management**.
2. On the key, **only "Enable Reading"** may be ticked.
   - Untick "Enable Spot & Margin Trading", "Enable Withdrawals", "Enable Margin",
     "Enable Futures", "Permits Universal Transfer" and any options or transfer
     permission.
   - If Binance won't let you remove a permission, **delete the key and create a
     new one with reading only**.
3. Recommended: **Restrict access to trusted IPs only**, using this host's public IP.
4. Never paste the secret into chat, email, a PR, a ticket or any file in the
   repository.
   - If the secret has ever been shown or shared anywhere, delete the key on
     Binance and create a new one.

This integration supports Binance **system-generated (HMAC)** keys. Self-generated
Ed25519 or RSA keys are not supported yet.

## Step 1: isolated worktree (does not touch your checkout or PR #112's Stage B)

```powershell
$Sha  = "<PR_HEAD_SHA>"   # from the draft PR
$Root = "C:\CSS_Evidence\BINANCE_" + (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
git -C C:\rasib\source\capital-strata-systems fetch origin claude/css-binance-readonly-paper
git -C C:\rasib\source\capital-strata-systems worktree add --detach "$Root\worktree" $Sha
py -3.11 -m venv "$Root\venv311"
& "$Root\venv311\Scripts\python.exe" -m pip install -r "$Root\worktree\requirements.txt" pytest
cd "$Root\worktree"
$env:CSS_TEST_MODE="1"
& "$Root\venv311\Scripts\python.exe" -m pytest -q tests\test_binance_readonly.py tests\test_binance_shadow_paper.py tests\test_shadow_paper_runner.py
Remove-Item Env:CSS_TEST_MODE
```

## Step 2: store credentials securely (once)

```powershell
powershell -ExecutionPolicy Bypass -File "$Root\worktree\scripts\windows\css_binance_readonly.ps1" -Setup
```

- You are prompted for the key and the secret. Input is hidden.
- They are encrypted with Windows DPAPI for **your Windows user on this machine only**.
- They are saved to `%LOCALAPPDATA%\CSS\binance_readonly.cred`, outside the
  repository, and the file's access is restricted to your user.
- Nothing goes into `.env`, the repository or any log.
- To delete them: run the same command with `-Remove`.
- To rotate: create a new key on Binance, run `-Setup` again, then delete the old
  key on Binance.

## Step 3: read-only connectivity and eligibility test

```powershell
powershell -ExecutionPolicy Bypass -File "$Root\worktree\scripts\windows\css_binance_readonly.ps1" -Check `
  -RepoRoot "$Root\worktree" -PythonExe "$Root\venv311\Scripts\python.exe" `
  -OperatorId <YOUR_ID> -OperatingCountry <WHERE_THIS_PC_IS_NOW> -KycCountry NG `
  -AttestNoGeoBypass -AttestReadOnlyKey
```

The credentials exist in memory only for that one Python process.

| Exit | Meaning |
|---|---|
| 0 | All stages passed: key verified read-only; balances and recent orders/trades read |
| 10 | Public connectivity blocked, including **HTTP 451 restricted location**. Stop; do not work around it |
| 11 | Attestation failed, e.g. operating country `CA`/`US`, or a missing attestation |
| 12 | Credentials missing, malformed, or found in a repository `.env` |
| 13 | Key or account not eligible: a write permission is on, or the status is not `Normal` |
| 14 | Other Binance API error (shown without key or signature) |

**Evidence** is written to `C:\CSS_Evidence\BINANCE_RO_<UTC>\binance_readonly_journal.jsonl`.
It is hash-chained and verifiable. It contains the key **fingerprint only**: never
the key, the secret or a signature. It does contain your balances and recent
orders/trades, so share it at your discretion.

## Step 4: Binance-price paper preflight (no credentials, no trades)

```powershell
& "$Root\venv311\Scripts\python.exe" scripts\css_shadow_paper_runner.py preflight --source binance `
  --evidence-dir "$Root\shadow_binance" --operator-id <YOUR_ID>
```

Exit 0 means both BTCUSDT and ETHUSDT quotes were accepted (real, fresh, valid
bid/ask). Exit 5 means the feed is not ready; a `RESTRICTED_LOCATION` reason means
Binance refused this location.

**Running paper cycles** (`run --source binance`) is a shakedown like Stage C and
needs the same explicit authorization. It uses the same gates and acceptance
criteria (`verify`) as `CSS_SHADOW_PAPER_RUNNER_RUNBOOK.md`.

Binance-specific notes:
- Prices are in USDT, and paper equity and notional are treated as USDT.
- R7 and R14F still use the uncalibrated proxy inputs documented in PR #112.

## Never

- Enable trading, withdrawal, transfer, margin, futures or options permissions on
  the key.
- Run with a VPN or proxy to change the apparent location.
- Store credentials in the repository.
- Merge, deploy or enable live execution from this work.
