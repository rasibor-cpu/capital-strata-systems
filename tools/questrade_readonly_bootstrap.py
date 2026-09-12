from __future__ import annotations

import argparse
import getpass
import json
import os
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError
from pathlib import Path
from typing import Any

from backend.brokers.questrade_client import QuestradeReadOnlyClient
from backend.brokers.questrade_oauth_manager import (
    FileQuestradeCredentialStore,
    QuestradeOAuthManager,
    TokenEndpointError,
    safe_token_response_diagnostics,
)
from backend.brokers.questrade_readonly_service import provider_failure_status

TOKEN_ENDPOINT = "https://login.questrade.com/oauth2/token"
DEFAULT_STORE = Path("state") / "questrade" / "credentials.json"


class _TokenTransport:
    def __init__(self) -> None:
        self.last_diagnostics: dict[str, Any] = {}

    def post_token(self, **kwargs: str) -> dict[str, Any]:
        token = kwargs.pop("refresh_token", "")
        body = urllib.parse.urlencode({"grant_type": "refresh_token", "refresh_token": token}).encode("ascii")
        request = urllib.request.Request(TOKEN_ENDPOINT, data=body, method="POST")
        request.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                content_type = response.headers.get("Content-Type")
                raw = response.read()
                status = int(response.status)
        except HTTPError as error:
            content_type = error.headers.get("Content-Type") if error.headers else None
            raw = error.read()
            diagnostics = self._diagnostics_from_body(raw, status=error.code, content_type=content_type)
            category = "AUTH_REQUIRED" if error.code in {400, 401, 403} else "PROVIDER_RATE_LIMITED" if error.code == 429 else "PROVIDER_UNAVAILABLE" if error.code >= 500 else "PROVIDER_RESPONSE_ERROR"
            raise TokenEndpointError("Questrade token endpoint rejected the request", category=category, diagnostics=diagnostics) from None
        except (TimeoutError, URLError, OSError) as error:
            raise TokenEndpointError(f"Questrade token endpoint unavailable: {type(error).__name__}", category="PROVIDER_UNAVAILABLE") from None
        diagnostics = self._diagnostics_from_body(raw, status=status, content_type=content_type)
        self.last_diagnostics = diagnostics
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise TokenEndpointError("Questrade token response was not valid JSON", category="MALFORMED_RESPONSE", diagnostics=diagnostics) from None
        if not isinstance(payload, dict):
            raise TokenEndpointError("Questrade token response was malformed", category="MALFORMED_RESPONSE", diagnostics=diagnostics)
        required = ("access_token", "refresh_token", "expires_in", "api_server")
        if any(not payload.get(field) for field in required):
            raise TokenEndpointError("Questrade token response is missing required fields", category="MALFORMED_RESPONSE", diagnostics=diagnostics)
        return payload

    def _diagnostics_from_body(self, raw: bytes, *, status: int | None, content_type: str | None) -> dict[str, Any]:
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            payload = None
        return safe_token_response_diagnostics(payload, http_status=status, content_type=content_type)


class _Response:
    def __init__(self, payload: Any, status_code: int, headers: Any) -> None:
        self.payload = payload
        self.status_code = status_code
        self.headers = dict(headers)

    def json(self) -> Any:
        return self.payload


class _ValidationTransport:
    def get(self, url: str, *, headers: dict[str, str], timeout: float) -> _Response:
        request = urllib.request.Request(url, headers=dict(headers), method="GET")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return _Response(json.loads(response.read().decode("utf-8")), response.status, response.headers)


def verify_secure_credential_destination(path: str | os.PathLike[str]) -> Path:
    destination = Path(path).expanduser().resolve()
    if destination.name != "credentials.json" or any(part in {"backend", "tests", "tools", ".git"} for part in destination.parts):
        raise RuntimeError("credential destination must be a local runtime credentials.json path")
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if destination.exists() and destination.is_dir():
        raise RuntimeError("credential destination is a directory")
    return destination


def bootstrap(*, store_path: Path = DEFAULT_STORE, authorization_token: str | None = None) -> dict[str, Any]:
    destination = verify_secure_credential_destination(store_path)
    token = authorization_token or getpass.getpass("Paste the Questrade manual authorization token locally (input hidden): ")
    if not token:
        raise RuntimeError("authorization token is required")
    store = FileQuestradeCredentialStore(str(destination))
    transport = _TokenTransport()
    oauth = QuestradeOAuthManager(token_transport=transport, credential_store=store)
    session = oauth.redeem_authorization_token(token)
    QuestradeReadOnlyClient(session=session, transport=_ValidationTransport()).get_time()
    return {"provider_health": "AVAILABLE", "provider": "QUESTRADE", "credential_status": "STORED", "api_server": session.api_server, "token_type": session.token_type, "read_only": True, "execution_allowed": False, "live_trading_blocked": True, "broker_execution_armed": False, "advisory_only": True, **getattr(transport, "last_diagnostics", {})}


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap Questrade read-only credentials locally")
    parser.add_argument("--credentials", default=str(DEFAULT_STORE))
    args = parser.parse_args()
    try:
        result = bootstrap(store_path=Path(args.credentials))
    except Exception as error:
        diagnostics = error.diagnostics if isinstance(error, TokenEndpointError) else {}
        print(json.dumps({"provider_health": "UNAVAILABLE", "status": provider_failure_status(error), "read_only": True, **diagnostics}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
