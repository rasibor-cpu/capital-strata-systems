from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.brokers.questrade_client import QuestradeReadOnlyClient
from backend.brokers.questrade_oauth_manager import FileQuestradeCredentialStore, QuestradeOAuthManager
from backend.brokers.questrade_provider_config import mask_account_identifier, select_account

STORE_PATH = Path("state") / "questrade" / "credentials.json"
TOKEN_ENDPOINT = "https://login.questrade.com/oauth2/token"


class _TokenTransport:
    def post_token(self, **kwargs: str) -> dict[str, Any]:
        body = urllib.parse.urlencode({"grant_type": "refresh_token", **kwargs}).encode("ascii")
        request = urllib.request.Request(TOKEN_ENDPOINT, data=body, method="POST")
        request.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeError("malformed token response")
        return payload


class _Response:
    def __init__(self, payload: Any, status_code: int, headers: Any) -> None:
        self.payload = payload
        self.status_code = status_code
        self.headers = dict(headers)

    def json(self) -> Any:
        return self.payload


class _Transport:
    def get(self, url: str, *, headers: dict[str, str], timeout: float) -> _Response:
        request = urllib.request.Request(url, headers=dict(headers), method="GET")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return _Response(json.loads(response.read().decode("utf-8")), response.status, response.headers)


def validate(*, client_id: str, client_secret: str, account_id: str | None = None, store_path: Path = STORE_PATH) -> dict[str, Any]:
    store = FileQuestradeCredentialStore(str(store_path))
    oauth = QuestradeOAuthManager(client_id=client_id, client_secret=client_secret, token_transport=_TokenTransport(), credential_store=store)
    session = oauth.refresh()
    client = QuestradeReadOnlyClient(session=session, transport=_Transport(), oauth=oauth)
    client.get_time()
    accounts = client.get_accounts().get("accounts", [])
    account = select_account(accounts, account_id)
    selected_id = str(account.get("number") or account.get("accountId"))
    balances = client.get_balances(selected_id)
    positions = client.get_positions(selected_id)
    return {
        "provider_status": "AVAILABLE",
        "account": mask_account_identifier(selected_id),
        "currency": account.get("currency"),
        "balance_record_count": len(balances) if isinstance(balances, dict) else 0,
        "position_count": len(positions.get("positions", [])) if isinstance(positions, dict) else 0,
        "observation_timestamp": datetime.now(timezone.utc).isoformat(),
        "freshness": "CURRENT",
        "rate_limit_remaining": client.last_rate_limit.remaining,
        "rate_limit_reset": client.last_rate_limit.reset,
    }


def main() -> int:
    client_id = os.environ.get("QUESTRADE_CLIENT_ID")
    client_secret = os.environ.get("QUESTRADE_CLIENT_SECRET")
    if not client_id or not client_secret:
        print("CONFIGURATION_REQUIRED")
        return 2
    try:
        print(json.dumps(validate(client_id=client_id, client_secret=client_secret, account_id=os.environ.get("QUESTRADE_ACCOUNT_ID")), sort_keys=True))
    except Exception as exc:
        print(type(exc).__name__)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
