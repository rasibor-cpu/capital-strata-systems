"""Dependency-free ASGI test client.

``fastapi.testclient`` requires an HTTP client package whose name and version
requirements change across Starlette releases (CI currently needs ``httpx2``,
which is not a project dependency). This client drives an ASGI app directly,
so API tests exercise the real routing, validation and dependency behaviour
identically on every Starlette version.
"""
import asyncio
import json as _json
from typing import Any, Dict, Optional
from urllib.parse import urlencode, urlsplit


class AsgiResponse:
    def __init__(self, status_code: int, headers: Dict[str, str], body: bytes):
        self.status_code = status_code
        self.headers = headers
        self.content = body

    def json(self) -> Any:
        return _json.loads(self.content.decode("utf-8"))


class AsgiTestClient:
    def __init__(self, app):
        self.app = app

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        json: Any = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> AsgiResponse:
        parts = urlsplit(url)
        if data is not None:
            body = urlencode(data).encode("utf-8")
        elif json is not None:
            body = _json.dumps(json).encode("utf-8")
        else:
            body = b""
        raw_headers = [(k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in (headers or {}).items()]
        if data is not None:
            raw_headers.append((b"content-type", b"application/x-www-form-urlencoded"))
        elif json is not None:
            raw_headers.append((b"content-type", b"application/json"))
        raw_headers.append((b"content-length", str(len(body)).encode("latin-1")))
        scope = {
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method.upper(),
            "scheme": "http", "path": parts.path, "raw_path": parts.path.encode("latin-1"),
            "query_string": parts.query.encode("latin-1"), "root_path": "", "headers": raw_headers,
            "client": ("testclient", 50000), "server": ("testserver", 80),
        }
        messages = [{"type": "http.request", "body": body, "more_body": False}]
        status = {"code": 500, "headers": {}}
        chunks = []

        async def receive():
            return messages.pop(0) if messages else {"type": "http.disconnect"}

        async def send(message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                status["headers"] = {k.decode("latin-1"): v.decode("latin-1") for k, v in message.get("headers", [])}
            elif message["type"] == "http.response.body":
                chunks.append(message.get("body", b""))

        asyncio.run(self.app(scope, receive, send))
        return AsgiResponse(status["code"], status["headers"], b"".join(chunks))

    def get(self, url: str, **kwargs) -> AsgiResponse:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> AsgiResponse:
        return self.request("POST", url, **kwargs)
