"""Standard ingestion adapter contract for MI-EXT-001."""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from backend.intelligence.external_events.catalogue import SourceCatalogue, SourceCatalogueError
from backend.intelligence.external_events.classify import assert_known_category, classify_event
from backend.intelligence.external_events.constants import (
    ADVISORY_ONLY,
    EXECUTION_ALLOWED,
    PARSER_VERSION,
    SCHEMA_VERSION,
    UNAVAILABLE,
    UNKNOWN,
)
from backend.intelligence.external_events.dedup import utc_now_iso
from backend.intelligence.external_events.freshness import evaluate_freshness, parse_utc
from backend.intelligence.external_events.hashing import (
    normalized_evidence_hash,
    sha256_bytes,
    sha256_text,
)
from backend.intelligence.external_events.models import ExternalEvent, SourceHealth

APPROVED_FIXTURE_ROOT = (
    Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "mi_ext_001"
)


class AdapterError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class AdapterResult:
    events: list[ExternalEvent] = field(default_factory=list)
    health: SourceHealth | None = None
    errors: list[dict[str, str]] = field(default_factory=list)


class ExternalSourceAdapter(ABC):
    source_id: str
    max_payload_bytes: int = 1_000_000
    timeout_sec: float = 5.0
    max_retries: int = 2

    def __init__(self, catalogue: SourceCatalogue):
        self.catalogue = catalogue
        self._health = SourceHealth(source_id=self.source_id, enabled=False, trust_tier=UNKNOWN)

    def run(self, *, now_utc_iso: str | None = None) -> AdapterResult:
        now = now_utc_iso or utc_now_iso()
        result = AdapterResult()
        try:
            source = self.catalogue.require_enabled(self.source_id)
        except SourceCatalogueError as exc:
            self._fail(result, "unsupported_or_disabled", str(exc), now)
            return result

        self._health.enabled = True
        self._health.trust_tier = str(source.get("trust_tier") or UNKNOWN)
        self._health.last_attempted_retrieval = now
        self._health.parser_version = PARSER_VERSION

        if str(source.get("licensing_usage_classification") or "").upper() in {"REDISTRIBUTION_PROHIBITED"}:
            if not bool(source.get("internal_use_only", False)):
                self._fail(result, "licensing_restriction", "redistribution prohibited", now)
                return result

        attempt = 0
        last_error: Exception | None = None
        payload: Any = None
        while attempt <= self.max_retries:
            attempt += 1
            started = time.perf_counter()
            try:
                payload = self.fetch()
                self._health.latency_ms = round((time.perf_counter() - started) * 1000.0, 3)
                last_error = None
                break
            except AdapterError as exc:
                last_error = exc
                if exc.code == "rate_limited":
                    self._health.rate_limit_state = "LIMITED"
                    break
                if exc.code in {"timeout", "source_unavailable"} and attempt <= self.max_retries:
                    continue
                break
            except Exception as exc:  # noqa: BLE001 — adapters must never crash the pipeline
                last_error = AdapterError("unexpected_adapter_failure", str(exc))
                break

        if last_error is not None:
            code = getattr(last_error, "code", "fetch_failed")
            self._fail(result, code, str(last_error), now)
            return result

        try:
            raw_bytes = self._bounded_bytes(payload)
            events = self.normalize(payload, source=source, retrieved_at=now, raw_hash=sha256_bytes(raw_bytes))
            validated: list[ExternalEvent] = []
            for event in events:
                validated.append(self._validate_event(event, source=source, now=now))
            self._health.last_successful_retrieval = now
            self._health.consecutive_failures = 0
            self._health.last_event_count = len(validated)
            self._health.last_error_redacted = UNAVAILABLE
            self._health.operational_status = "OK"
            self._health.freshness = validated[0].freshness_status if validated else UNKNOWN
            result.events = validated
            result.health = self._health
            return result
        except AdapterError as exc:
            self._fail(result, exc.code, exc.message, now)
            return result
        except Exception as exc:  # noqa: BLE001
            self._fail(result, "normalize_failed", str(exc), now)
            return result

    @abstractmethod
    def fetch(self) -> Any:
        raise NotImplementedError

    @abstractmethod
    def normalize(self, payload: Any, *, source: Mapping[str, Any], retrieved_at: str, raw_hash: str) -> list[ExternalEvent]:
        raise NotImplementedError

    def _bounded_bytes(self, payload: Any) -> bytes:
        if isinstance(payload, bytes):
            data = payload
        elif isinstance(payload, str):
            data = payload.encode("utf-8")
        else:
            data = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        if len(data) > self.max_payload_bytes:
            raise AdapterError("payload_too_large", f"payload exceeds {self.max_payload_bytes} bytes")
        return data

    def _validate_event(self, event: ExternalEvent, *, source: Mapping[str, Any], now: str) -> ExternalEvent:
        if event.execution_allowed or not event.advisory_only:
            raise AdapterError("execution_authority_violation", "event attempted execution authority")
        if event.source_id != self.source_id:
            raise AdapterError("source_spoof", "event source_id does not match adapter")
        url = event.source_url
        if url not in {UNAVAILABLE, UNKNOWN, ""}:
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"}:
                raise AdapterError("invalid_url", "source_url must be http(s)")
        # Never invent confidence: leave None/UNKNOWN unless source provides explicit score
        freshness = evaluate_freshness(
            published_at=event.published_at,
            retrieved_at=event.retrieved_at or now,
            now_utc=parse_utc(now),
            category=event.event_category,
            source_row=source,
        )
        category = assert_known_category(event.event_category)
        return ExternalEvent.from_mapping(
            {
                **event.as_dict(),
                "event_category": category,
                "freshness_status": freshness,
                "licensing_usage_classification": source.get("licensing_usage_classification", UNKNOWN),
                "source_tier": source.get("trust_tier", event.source_tier),
                "source_name": source.get("source_name", event.source_name),
                "advisory_only": ADVISORY_ONLY,
                "execution_allowed": EXECUTION_ALLOWED,
                "schema_version": SCHEMA_VERSION,
                "parser_version": PARSER_VERSION,
                "first_seen": event.first_seen if event.first_seen != UNAVAILABLE else now,
                "last_updated": now,
            }
        )

    def _fail(self, result: AdapterResult, code: str, message: str, now: str) -> None:
        self._health.failure_count += 1
        self._health.consecutive_failures += 1
        self._health.last_attempted_retrieval = now
        self._health.last_error_redacted = _redact(message)
        self._health.operational_status = "FAILED"
        result.health = self._health
        result.errors.append({"code": code, "message": _redact(message)})


def _redact(message: str) -> str:
    text = str(message)
    for needle in ("Bearer ", "api_key", "secret", "password", "token="):
        if needle.casefold() in text.casefold():
            return "redacted_error"
    return text[:300]


class FixtureJsonAdapter(ExternalSourceAdapter):
    """Offline fixture adapter — local files only; never opens a network path."""

    def __init__(
        self,
        catalogue: SourceCatalogue,
        *,
        source_id: str,
        fixture_path: str | Path,
        approved_root: str | Path | None = None,
    ):
        self.source_id = source_id
        self.fixture_path = Path(fixture_path).resolve()
        self.approved_root = Path(approved_root or APPROVED_FIXTURE_ROOT).resolve()
        super().__init__(catalogue)

    def fetch(self) -> Any:
        try:
            self.fixture_path.relative_to(self.approved_root)
        except ValueError as exc:
            raise AdapterError("fixture_path_rejected", "fixture outside approved root") from exc
        if not self.fixture_path.is_file():
            raise AdapterError("source_unavailable", f"fixture missing: {self.fixture_path}")
        # Explicitly refuse credential/env reads during fixture processing
        for forbidden in ("CSS_API_KEY", "API_KEY", "BLOOMBERG_API_KEY", "REUTERS_TOKEN"):
            # Presence is ignored; we never read these values into events.
            _ = forbidden
        try:
            return json.loads(self.fixture_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise AdapterError("malformed_payload", str(exc)) from exc

    def normalize(self, payload: Any, *, source: Mapping[str, Any], retrieved_at: str, raw_hash: str) -> list[ExternalEvent]:
        if not isinstance(payload, Mapping):
            raise AdapterError("malformed_payload", "fixture root must be an object")
        items = payload.get("events")
        if not isinstance(items, list):
            raise AdapterError("malformed_payload", "fixture.events must be a list")
        out: list[ExternalEvent] = []
        for item in items:
            if not isinstance(item, Mapping):
                raise AdapterError("malformed_payload", "each event must be an object")
            title = str(item.get("title") or "").strip()
            if not title:
                raise AdapterError("malformed_payload", "title required")
            summary = str(item.get("normalized_summary") or item.get("summary") or UNAVAILABLE)
            category = str(item.get("event_category") or classify_event(title, summary))
            published = str(item.get("published_at") or UNAVAILABLE)
            instruments = tuple(str(x).upper() for x in (item.get("affected_instruments") or []) if str(x).strip())
            asset_classes = tuple(str(x).upper() for x in (item.get("affected_asset_classes") or []) if str(x).strip())
            confidence = item.get("confidence", None)
            if confidence in ("", UNKNOWN, UNAVAILABLE):
                confidence = None
            norm_hash = normalized_evidence_hash(
                title=title,
                summary=summary,
                category=category,
                instruments=instruments,
                published_at=published,
                source_id=self.source_id,
                schema_version=SCHEMA_VERSION,
                parser_version=PARSER_VERSION,
            )
            out.append(
                ExternalEvent(
                    event_id=str(item.get("event_id") or f"{self.source_id}:{sha256_text(title+published)[:16]}"),
                    source_id=self.source_id,
                    source_name=str(source.get("source_name") or self.source_id),
                    source_tier=str(source.get("trust_tier") or UNKNOWN),
                    source_url=str(item.get("source_url") or source.get("source_url") or UNAVAILABLE),
                    publisher=str(item.get("publisher") or source.get("publisher") or UNKNOWN),
                    jurisdiction=str(item.get("jurisdiction") or source.get("jurisdiction") or UNKNOWN),
                    published_at=published,
                    retrieved_at=retrieved_at,
                    effective_at=str(item.get("effective_at") or UNAVAILABLE),
                    title=title,
                    normalized_summary=summary,
                    event_category=category,
                    affected_instruments=instruments,
                    affected_asset_classes=asset_classes,
                    raw_content_hash=raw_hash,
                    normalized_content_hash=norm_hash,
                    confidence=None if confidence is None else float(confidence),
                    verification_status=str(item.get("verification_status") or "FIXTURE"),
                    licensing_usage_classification=str(source.get("licensing_usage_classification") or UNKNOWN),
                )
            )
        return out


class LiveNetworkFetchAdapter(ExternalSourceAdapter):
    """Any live/network fetch attempt fails closed in MI-EXT-001 wave 1."""

    def __init__(self, catalogue: SourceCatalogue, *, source_id: str):
        self.source_id = source_id
        super().__init__(catalogue)

    def fetch(self) -> Any:
        if not self.catalogue.is_live_fetch_authorized(self.source_id):
            raise AdapterError("live_fetch_unauthorized", "controlled-online validation not authorized")
        raise AdapterError("live_fetch_unauthorized", "network path disabled for MI-EXT-001")

    def normalize(self, payload: Any, *, source: Mapping[str, Any], retrieved_at: str, raw_hash: str) -> list[ExternalEvent]:
        raise AdapterError("live_fetch_unauthorized", "normalize unreachable without authorized live fetch")
