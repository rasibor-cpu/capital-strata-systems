from __future__ import annotations

import glob
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_local_env(mode: str | None = None) -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    if str(mode or "").strip().lower() != "live":
        load_dotenv(PROJECT_ROOT / ".env.practice", override=False)


def check_oanda() -> bool:
    token = (
        os.getenv("OANDA_API_KEY")
        or os.getenv("OANDA_API_TOKEN")
        or os.getenv("OANDA_PRACTICE_TOKEN")
        or os.getenv("OANDA_LIVE_TOKEN")
        or ""
    ).strip()
    account_id = (
        os.getenv("OANDA_ACCOUNT_ID")
        or os.getenv("OANDA_PRACTICE_ACCOUNT_ID")
        or os.getenv("OANDA_LIVE_ACCOUNT_ID")
        or ""
    ).strip()
    configured_base_url = (os.getenv("OANDA_BASE_URL") or "").strip().rstrip("/")
    base_url = configured_base_url

    if not configured_base_url:
        env_name = (os.getenv("OANDA_ENV") or "practice").strip().lower()
        if env_name == "live":
            base_url = "https://api-fxtrade.oanda.com"
        else:
            base_url = "https://api-fxpractice.oanda.com"

    print("=== OANDA READ-ONLY CHECK ===")
    print(f"OANDA_TOKEN_PRESENT: {'YES' if bool(token) else 'NO'}")
    print(f"OANDA_ACCOUNT_ID_PRESENT: {'YES' if bool(account_id) else 'NO'}")
    print(f"OANDA_BASE_URL_PRESENT: {'YES' if bool(base_url) else 'NO'}")

    if not token or not base_url:
        print("OANDA_RESULT: FAIL_MISSING_TOKEN_OR_BASE_URL")
        return False

    accounts_ok, accounts_status, accounts_data, base_url = _oanda_get_accounts(
        base_url=base_url,
        token=token,
        allow_live_practice_probe=not configured_base_url,
    )
    print(f"OANDA_ACCOUNTS_STATUS: {accounts_status}")
    print(f"OANDA_ACCOUNTS_OK: {'YES' if accounts_ok else 'NO'}")

    accounts = []
    if isinstance(accounts_data, dict):
        raw_accounts = accounts_data.get("accounts", [])
        if isinstance(raw_accounts, list):
            accounts = raw_accounts

    print(f"OANDA_ACCOUNT_COUNT: {len(accounts)}")

    if not account_id and len(accounts) == 1 and isinstance(accounts[0], dict):
        account_id = str(accounts[0].get("id", "") or "").strip()
        print("OANDA_ACCOUNT_ID_DISCOVERED: YES")
    elif not account_id:
        print("OANDA_ACCOUNT_ID_DISCOVERED: NO")

    if not accounts_ok:
        print("OANDA_RESULT: FAIL_ACCOUNTS_ENDPOINT")
        return False

    if not account_id:
        print("OANDA_RESULT: PARTIAL_TOKEN_OK_ACCOUNT_ID_REQUIRED")
        return False

    summary_ok, summary_status, summary_data = _oanda_get_json(
        base_url=base_url,
        token=token,
        path=f"/v3/accounts/{account_id}/summary",
    )
    print(f"OANDA_SUMMARY_STATUS: {summary_status}")
    print(f"OANDA_SUMMARY_OK: {'YES' if summary_ok else 'NO'}")

    balance_present = False
    if isinstance(summary_data, dict):
        account = summary_data.get("account", {})
        if isinstance(account, dict):
            balance_present = account.get("balance") is not None

    print(f"OANDA_BALANCE_PRESENT: {'YES' if balance_present else 'NO'}")

    if summary_ok:
        print("OANDA_RESULT: PASS")
        return True

    print("OANDA_RESULT: FAIL_SUMMARY_ENDPOINT")
    return False


def _oanda_get_accounts(
    *,
    base_url: str,
    token: str,
    allow_live_practice_probe: bool,
) -> Tuple[bool, Optional[int], Any, str]:
    attempts = [base_url]

    if allow_live_practice_probe:
        for candidate in [
            "https://api-fxpractice.oanda.com",
            "https://api-fxtrade.oanda.com",
        ]:
            if candidate not in attempts:
                attempts.append(candidate)

    last_ok = False
    last_status: Optional[int] = None
    last_data: Any = None
    last_base = base_url

    for candidate in attempts:
        ok, status, data = _oanda_get_json(
            base_url=candidate,
            token=token,
            path="/v3/accounts",
        )

        last_ok = ok
        last_status = status
        last_data = data
        last_base = candidate

        if ok:
            return ok, status, data, candidate

    return last_ok, last_status, last_data, last_base


def check_coinbase() -> bool:
    print("")
    print("=== COINBASE READ-ONLY CHECK ===")

    api_key, api_secret, source = _load_coinbase_credentials()

    print(f"COINBASE_KEY_PRESENT: {'YES' if bool(api_key) else 'NO'}")
    print(f"COINBASE_PRIVATE_KEY_PRESENT: {'YES' if bool(api_secret) else 'NO'}")
    print(f"COINBASE_CREDENTIAL_SOURCE: {source}")
    print(
        "COINBASE_LIVE_ORDERS_FLAG: "
        f"{'ON' if _coinbase_live_orders_enabled() else 'OFF'}"
    )

    if not api_key or not api_secret:
        print("COINBASE_RESULT: FAIL_MISSING_KEY_OR_PRIVATE_KEY")
        return False

    try:
        from coinbase.rest import RESTClient  # type: ignore
    except Exception as exc:
        print("COINBASE_RESULT: FAIL_RESTCLIENT_IMPORT")
        print(f"COINBASE_ERROR_TYPE: {type(exc).__name__}")
        return False

    try:
        client = RESTClient(api_key=api_key, api_secret=api_secret)
        accounts_resp = client.get_accounts()
        accounts_data = _to_dict(accounts_resp)
    except Exception as exc:
        print("COINBASE_RESULT: FAIL_ACCOUNTS_ENDPOINT")
        print(f"COINBASE_ERROR_TYPE: {type(exc).__name__}")
        return False

    accounts = _extract_coinbase_accounts(accounts_data)
    print("COINBASE_ACCOUNTS_OK: YES")
    print(f"COINBASE_ACCOUNT_COUNT: {len(accounts)}")
    print("COINBASE_RESULT: PASS")
    return True


def _oanda_get_json(
    *,
    base_url: str,
    token: str,
    path: str,
) -> Tuple[bool, Optional[int], Any]:
    url = f"{base_url}/{path.lstrip('/')}"
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8")
            status = int(getattr(response, "status", 0) or 0)
            return 200 <= status < 300, status, json.loads(body)
    except urllib.error.HTTPError as exc:
        return False, int(exc.code), None
    except Exception:
        return False, None, None


def _load_coinbase_credentials() -> Tuple[str, str, str]:
    api_key = (
        os.getenv("COINBASE_CDP_KEY_NAME")
        or os.getenv("COINBASE_KEY_NAME")
        or os.getenv("COINBASE_API_KEY")
        or ""
    ).strip()
    api_secret = (os.getenv("COINBASE_API_SECRET") or "").strip()

    private_key_path = (
        os.getenv("COINBASE_CDP_PRIVATE_KEY_PATH")
        or os.getenv("COINBASE_PRIVATE_KEY_PATH")
        or ""
    ).strip()

    if not api_secret and os.getenv("COINBASE_PRIVATE_KEY"):
        api_secret = str(os.getenv("COINBASE_PRIVATE_KEY") or "").strip()

    if not api_secret and private_key_path:
        try:
            api_secret = Path(private_key_path).read_text(encoding="utf-8").strip()
        except Exception:
            api_secret = ""

    if api_key and api_secret:
        return api_key, api_secret, "ENV"

    for path in _coinbase_key_candidates():
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception:
            continue

        api_key = str(
            _coalesce(
                payload.get("name"),
                payload.get("apiKey"),
                payload.get("key"),
                payload.get("client_id"),
            )
            or ""
        ).strip()
        api_secret = str(
            _coalesce(
                payload.get("privateKey"),
                payload.get("apiSecret"),
                payload.get("secret"),
                payload.get("private_key"),
            )
            or ""
        ).strip()

        if api_key and api_secret:
            source = "KEYS_DIR" if str(path).startswith(str(PROJECT_ROOT)) else "DOWNLOADS"
            return api_key, api_secret, source

    return "", "", "NONE"


def _coinbase_key_candidates() -> Iterable[str]:
    patterns = [
        str(PROJECT_ROOT / "keys" / "cdp_api_key*.json"),
        str(Path.home() / "Downloads" / "cdp_api_key*.json"),
        str(Path.home() / "Downloads" / "cdp_api-key*.json"),
    ]

    candidates = []
    for pattern in patterns:
        candidates.extend(glob.glob(pattern))

    candidates.sort(key=lambda path: os.path.getmtime(path), reverse=True)
    return candidates


def _coinbase_live_orders_enabled() -> bool:
    return (os.getenv("COINBASE_ENABLE_LIVE_ORDERS") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }


def _to_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value

    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        data = to_dict()
        if isinstance(data, dict):
            return data

    return {}


def _extract_coinbase_accounts(data: Dict[str, Any]) -> list[Any]:
    accounts = data.get("accounts")
    if isinstance(accounts, list):
        return accounts

    nested = data.get("data")
    if isinstance(nested, dict) and isinstance(nested.get("accounts"), list):
        return nested["accounts"]

    return []


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def main() -> int:
    load_local_env()

    oanda_ok = check_oanda()
    coinbase_ok = check_coinbase()

    print("")
    print("=== BROKER CREDENTIAL CHECK SUMMARY ===")
    print(f"OANDA: {'PASS' if oanda_ok else 'FAIL'}")
    print(f"COINBASE: {'PASS' if coinbase_ok else 'FAIL'}")

    return 0 if oanda_ok and coinbase_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
