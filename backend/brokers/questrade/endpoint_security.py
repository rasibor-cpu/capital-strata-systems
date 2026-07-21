"""Questrade API-server discovery validation and SSRF controls."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import re
from urllib.parse import urlsplit, urlunsplit


_API_HOST = re.compile(r"^api[0-9]+\.iq\.questrade\.com$", re.IGNORECASE)


@dataclass(frozen=True)
class ValidatedApiServer:
    base_url: str
    host: str
    api_version: str = "v1"

    def sanitized_metadata(self) -> dict[str, str | bool]:
        return {
            "scheme": "https",
            "host": self.host,
            "api_version": self.api_version,
            "base_url": self.base_url,
            "provider_domain_validated": True,
        }


def validate_api_server(value: str) -> ValidatedApiServer:
    raw = str(value or "").strip()
    try:
        parsed = urlsplit(raw)
        host = (parsed.hostname or "").lower()
        if parsed.scheme.lower() != "https":
            raise ValueError("API_SERVER_HTTPS_REQUIRED")
        if parsed.username or parsed.password:
            raise ValueError("API_SERVER_USERINFO_REJECTED")
        if parsed.port not in (None, 443):
            raise ValueError("API_SERVER_PORT_REJECTED")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError("API_SERVER_IP_LITERAL_REJECTED")
        if not _API_HOST.fullmatch(host):
            raise ValueError("API_SERVER_DOMAIN_REJECTED")
        path = "/" + parsed.path.strip("/")
        if path in {"/", "/v1"}:
            path = "/v1/"
        elif path == "/v1/":
            pass
        else:
            raise ValueError("API_SERVER_PATH_REJECTED")
        normalized = urlunsplit(("https", host, path, "", ""))
        return ValidatedApiServer(base_url=normalized, host=host)
    except (TypeError, ValueError) as exc:
        code = str(exc)
        if code.startswith("API_SERVER_"):
            raise
        raise ValueError("API_SERVER_MALFORMED") from None


def safe_join_api_path(server: ValidatedApiServer, path: str) -> str:
    suffix = "/" + str(path or "").lstrip("/")
    if ".." in suffix or "://" in suffix or "\\" in suffix:
        raise ValueError("API_PATH_REJECTED")
    return server.base_url.rstrip("/") + suffix


__all__ = ["ValidatedApiServer", "safe_join_api_path", "validate_api_server"]
