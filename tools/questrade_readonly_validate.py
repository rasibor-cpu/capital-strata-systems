from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from backend.brokers.questrade_client import QuestradeReadOnlyClient
from backend.brokers.questrade_oauth_manager import FileQuestradeCredentialStore, QuestradeOAuthManager
from backend.brokers.questrade_provider_config import QuestradeProviderConfig
from backend.brokers.questrade_readonly_service import provider_failure_status, validate_readonly_provider

TOKEN_ENDPOINT = "https://login.questrade.com/oauth2/token"


class _TokenTransport:
    def post_token(self, **kwargs: str) -> dict[str, Any]:
        body = urllib.parse.urlencode({"grant_type": "refresh_token", **kwargs}).encode("ascii")
        request = urllib.request.Request(TOKEN_ENDPOINT, data=body, method="POST")
        request.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeError("Questrade token response was malformed")
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


def validate(*, client_id: str, client_secret: str, account_id: str | None = None, store_path: Path = Path("state") / "questrade" / "credentials.json") -> dict[str, Any]:
    config = QuestradeProviderConfig(enabled=True, credential_source=str(store_path), account_id=account_id)
    store = FileQuestradeCredentialStore(config.credential_path())
    oauth = QuestradeOAuthManager(client_id=client_id, client_secret=client_secret, token_transport=_TokenTransport(), credential_store=store)
    session = oauth.refresh()
    client = QuestradeReadOnlyClient(session=session, transport=_Transport(), oauth=oauth)
    return validate_readonly_provider(client, config)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Questrade read-only connectivity")
    parser.add_argument("--credentials", default="state/questrade/credentials.json")
    args = parser.parse_args()
    try:
        result = validate(client_id=os.environ.get("QUESTRADE_CLIENT_ID", ""), client_secret=os.environ.get("QUESTRADE_CLIENT_SECRET", ""), account_id=os.environ.get("QUESTRADE_ACCOUNT_ID"), store_path=Path(args.credentials))
    except Exception as error:
        print(json.dumps({"provider_health": "UNAVAILABLE", "status": provider_failure_status(error), "read_only": True}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
