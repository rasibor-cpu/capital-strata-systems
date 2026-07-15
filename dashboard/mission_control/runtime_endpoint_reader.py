from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from dashboard.mission_control.active_runtime_source import RuntimeSourceCandidate, SOURCE_RUNTIME_ENDPOINT
from dashboard.mission_control.serializers import state_hash


class RuntimeEndpointReader:
    """Read an existing local runtime/frontend endpoint without creating a server."""

    DEFAULT_PATH = "/api/v1/frontend-state"
    LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}

    def __init__(self, base_url: str | None = None, *, timeout_seconds: float = 0.35) -> None:
        self.base_url = str(base_url or os.getenv("CSS_MISSION_CONTROL_RUNTIME_ENDPOINT") or "").strip()
        self.timeout_seconds = float(timeout_seconds)

    def read_candidate(self) -> RuntimeSourceCandidate:
        if not self.base_url:
            return RuntimeSourceCandidate(
                name="localhost_runtime_endpoint",
                source_type=SOURCE_RUNTIME_ENDPOINT,
                available=False,
                freshness_status="UNAVAILABLE",
                path_category="RUNTIME_ENDPOINT",
                process_relationship="EXISTING_LOCALHOST_HTTP",
                failure="runtime_endpoint_not_configured",
            )
        url, failure = self._endpoint_url()
        if failure:
            return RuntimeSourceCandidate(
                name="localhost_runtime_endpoint",
                source_type=SOURCE_RUNTIME_ENDPOINT,
                available=False,
                freshness_status="UNAVAILABLE",
                path_category="RUNTIME_ENDPOINT",
                process_relationship="EXISTING_LOCALHOST_HTTP",
                failure=failure,
            )
        try:
            request = Request(url, method="GET", headers={"Accept": "application/json"})
            with urlopen(request, timeout=self.timeout_seconds) as response:
                status = int(getattr(response, "status", 0) or 0)
                body = response.read(2_000_000)
            payload = json.loads(body.decode("utf-8"))
            if not isinstance(payload, Mapping):
                raise ValueError("endpoint_payload_not_mapping")
        except Exception as exc:
            return RuntimeSourceCandidate(
                name="localhost_runtime_endpoint",
                source_type=SOURCE_RUNTIME_ENDPOINT,
                available=False,
                freshness_status="UNAVAILABLE",
                path_category="RUNTIME_ENDPOINT",
                process_relationship="EXISTING_LOCALHOST_HTTP",
                failure=f"endpoint_read_failed:{exc.__class__.__name__}",
                metadata={"url": self._safe_url(url)},
            )
        wrapped = {
            "source": SOURCE_RUNTIME_ENDPOINT,
            "source_type": SOURCE_RUNTIME_ENDPOINT,
            "source_name": "runtime_endpoint_reader",
            "frontend_payload": dict(payload),
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
            "advisory_only": True,
        }
        return RuntimeSourceCandidate(
            name="localhost_runtime_endpoint",
            source_type=SOURCE_RUNTIME_ENDPOINT,
            available=200 <= status < 300,
            freshness_status="FRESH" if 200 <= status < 300 else "UNAVAILABLE",
            path_category="RUNTIME_ENDPOINT",
            process_relationship="EXISTING_LOCALHOST_HTTP",
            generated_at=str(payload.get("generated_at") or payload.get("timestamp") or "UNAVAILABLE"),
            observed_at=str(payload.get("generated_at") or payload.get("timestamp") or "UNAVAILABLE"),
            failure="" if 200 <= status < 300 else f"endpoint_http_status:{status}",
            state_hash=state_hash(wrapped),
            metadata={"url": self._safe_url(url), "http_status": status},
            payload=wrapped,
        )

    def _endpoint_url(self) -> tuple[str, str]:
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"}:
            return "", "runtime_endpoint_scheme_not_http"
        if (parsed.hostname or "").lower() not in self.LOCAL_HOSTS:
            return "", "runtime_endpoint_not_localhost"
        path = parsed.path or self.DEFAULT_PATH
        url = self.base_url.rstrip("/")
        if path == "/" or not parsed.path:
            url = self.base_url.rstrip("/") + self.DEFAULT_PATH
        return url, ""

    @staticmethod
    def _safe_url(url: str) -> str:
        parsed = urlparse(url)
        host = parsed.hostname or "localhost"
        port = f":{parsed.port}" if parsed.port else ""
        return f"{parsed.scheme}://{host}{port}{parsed.path or RuntimeEndpointReader.DEFAULT_PATH}"


__all__ = ["RuntimeEndpointReader"]
