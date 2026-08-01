"""Phase 188 — network validators (DNS/TLS) for controlled RO certification."""

from __future__ import annotations

import socket
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping
from urllib.parse import urlparse


@dataclass(frozen=True)
class DnsValidationResult:
    ok: bool
    host: str
    addresses: tuple[str, ...]
    latency_ms: float
    error: str = ""


@dataclass(frozen=True)
class TlsValidationResult:
    ok: bool
    host: str
    protocol: str
    cipher: str
    not_after: str
    latency_ms: float
    error: str = ""
    clock_skew_ok: bool = True


def parse_endpoint(endpoint: str) -> tuple[str, int]:
    parsed = urlparse(endpoint if "://" in endpoint else f"https://{endpoint}")
    host = parsed.hostname or ""
    port = int(parsed.port or (443 if parsed.scheme == "https" else 80))
    return host, port


def validate_dns(
    endpoint: str,
    *,
    resolver: Callable[[str], list[str]] | None = None,
    clock: Callable[[], float] | None = None,
) -> DnsValidationResult:
    import time

    host, _ = parse_endpoint(endpoint)
    if not host:
        return DnsValidationResult(False, "", (), 0.0, "missing_host")
    started = (clock or time.perf_counter)()
    try:
        if resolver is not None:
            addrs = list(resolver(host))
        else:
            infos = socket.getaddrinfo(host, None)
            addrs = sorted({item[4][0] for item in infos if item and item[4]})
        latency = ((clock or time.perf_counter)() - started) * 1000.0
        if not addrs:
            return DnsValidationResult(False, host, (), latency, "no_addresses")
        return DnsValidationResult(True, host, tuple(addrs), latency)
    except Exception as exc:  # noqa: BLE001
        latency = ((clock or time.perf_counter)() - started) * 1000.0
        return DnsValidationResult(False, host, (), latency, str(exc)[:160])


def validate_tls(
    endpoint: str,
    *,
    connector: Callable[[str, int], Mapping[str, Any]] | None = None,
    now: Callable[[], datetime] | None = None,
    clock: Callable[[], float] | None = None,
) -> TlsValidationResult:
    import time

    host, port = parse_endpoint(endpoint)
    if not host:
        return TlsValidationResult(False, "", "", "", "", 0.0, "missing_host")
    started = (clock or time.perf_counter)()
    try:
        if connector is not None:
            info = dict(connector(host, port))
        else:
            info = _default_tls_probe(host, port)
        latency = ((clock or time.perf_counter)() - started) * 1000.0
        not_after = str(info.get("not_after") or "")
        skew_ok = True
        if not_after:
            try:
                # OpenSSL date format: 'Jun  1 12:00:00 2027 GMT'
                expiry = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(
                    tzinfo=timezone.utc
                )
                current = (now or (lambda: datetime.now(timezone.utc)))()
                skew_ok = expiry > current
            except ValueError:
                skew_ok = True
        ok = bool(info.get("ok", True)) and skew_ok
        return TlsValidationResult(
            ok=ok,
            host=host,
            protocol=str(info.get("protocol") or ""),
            cipher=str(info.get("cipher") or ""),
            not_after=not_after,
            latency_ms=latency,
            error="" if ok else str(info.get("error") or "tls_or_clock_skew"),
            clock_skew_ok=skew_ok,
        )
    except Exception as exc:  # noqa: BLE001
        latency = ((clock or time.perf_counter)() - started) * 1000.0
        return TlsValidationResult(False, host, "", "", "", latency, str(exc)[:160], False)


def _default_tls_probe(host: str, port: int) -> dict[str, Any]:
    context = ssl.create_default_context()
    with socket.create_connection((host, port), timeout=10.0) as sock:
        with context.wrap_socket(sock, server_hostname=host) as ssock:
            cert = ssock.getpeercert() or {}
            cipher = ssock.cipher()
            return {
                "ok": True,
                "protocol": ssock.version() or "",
                "cipher": cipher[0] if cipher else "",
                "not_after": str(cert.get("notAfter") or ""),
            }
