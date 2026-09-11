from __future__ import annotations

import getpass
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from backend.brokers.questrade_client import QuestradeReadOnlyClient
from backend.brokers.questrade_oauth_manager import (
    FileQuestradeCredentialStore,
    QuestradeTokenSession,
    parse_token_response,
)

TOKEN_ENDPOINT = "https://login.questrade.com/oauth2/token"
DEFAULT_STORE = Path("state") / "questrade" / "credentials.json"


class _TokenTransport:
    def post_authorization_code(self, *, client_id: str, client_secret: str, code: str) -> dict[str, Any]:
        body = urllib.parse.urlencode({
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
        }).encode("ascii")
        request = urllib.request.Request(TOKEN_ENDPOINT, data=body, method="POST")
        request.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise RuntimeError("Questrade authorization redemption failed") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("Questrade token response was malformed")
        return payload


class _ValidationTransport:
    def get(self, url: str, *, headers: dict[str, str], timeout: float) -> Any:
        request = urllib.request.Request(url, headers=dict(headers), method="GET")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return _Response(payload, response.status, dict(response.headers))


class _Response:
    def __init__(self, payload: Any, status_code: int, headers: dict[str, str]) -> None:
        self.payload = payload
        self.status_code = status_code
        self.headers = headers

    def json(self) -> Any:
        return self.payload


def bootstrap(*, client_id: str, client_secret: str, store_path: Path = DEFAULT_STORE) -> QuestradeTokenSession:
    code = getpass.getpass("Paste the Questrade manual authorization token locally (input hidden): ")
    if not code:
        raise RuntimeError("authorization token is required")
    payload = _TokenTransport().post_authorization_code(client_id=client_id, client_secret=client_secret, code=code)
    session = parse_token_response(payload)
    client = QuestradeReadOnlyClient(session=session, transport=_ValidationTransport())
    client.get_time()
    FileQuestradeCredentialStore(str(store_path)).replace_refresh_token(session.refresh_token)
    print(f"Questrade read-only bootstrap validated; api_server={session.api_server}; credential_store={store_path}")
    return session


def main() -> int:
    client_id = os.environ.get("QUESTRADE_CLIENT_ID")
    client_secret = os.environ.get("QUESTRADE_CLIENT_SECRET")
    if not client_id or not client_secret:
        print("CONFIGURATION_REQUIRED: set Questrade client configuration locally")
        return 2
    try:
        bootstrap(client_id=client_id, client_secret=client_secret)
    except Exception as exc:
        print(f"BOOTSTRAP_FAILED: {type(exc).__name__}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
