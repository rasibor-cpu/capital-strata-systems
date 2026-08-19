"""Source catalogue loader, integrity validation, and trust helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from backend.intelligence.external_events.constants import TrustTier, UNKNOWN
from backend.intelligence.external_events.hashing import canonical_json_hash

DEFAULT_CATALOGUE_PATH = (
    Path(__file__).resolve().parents[3] / "docs" / "governance" / "MI_EXT_001_SOURCE_CATALOGUE.json"
)

REQUIRED_SOURCE_FIELDS = (
    "source_id",
    "source_name",
    "jurisdiction",
    "trust_tier",
    "access_method",
    "cost_status",
    "licensing_usage_classification",
    "freshness_threshold",
    "may_influence_advisory",
    "prohibited_from_direct_execution",
    "direct_execution_influence",
    "access_status",
    "operational_state",
    "online_validation_required",
    "enabled",
)

COMMERCIAL_COST_MARKERS = {"paid", "commercial", "licensed_paid"}
BLOCKED_ACCESS = {"BLOCKED", "PROHIBITED"}
FIXTURE_OR_CATALOGUE = {"FIXTURE_ONLY", "CATALOGUED_NOT_WIRED", "BLOCKED", "PROHIBITED"}


class SourceCatalogueError(ValueError):
    """Raised when the source catalogue is invalid or a source is unsupported."""


class SourceCatalogue:
    def __init__(self, payload: Mapping[str, Any]):
        if not isinstance(payload, Mapping):
            raise SourceCatalogueError("catalogue root must be an object")
        sources = payload.get("sources")
        if not isinstance(sources, list) or not sources:
            raise SourceCatalogueError("catalogue.sources must be a non-empty list")
        by_id: dict[str, dict[str, Any]] = {}
        for row in sources:
            if not isinstance(row, Mapping):
                raise SourceCatalogueError("each source must be an object")
            normalized = self._normalize_and_validate_row(dict(row))
            source_id = normalized["source_id"]
            if source_id in by_id:
                raise SourceCatalogueError(f"duplicate source_id: {source_id}")
            by_id[source_id] = normalized
        self._payload = dict(payload)
        if bool(self._payload.get("live_network_ingestion", False)):
            raise SourceCatalogueError("live_network_ingestion must be false for MI-EXT-001 recovery")
        if bool(self._payload.get("execution_allowed", False)):
            raise SourceCatalogueError("catalogue execution_allowed must be false")
        if self._payload.get("advisory_only") is False:
            raise SourceCatalogueError("catalogue advisory_only must be true")
        self._payload["live_network_ingestion"] = False
        self._payload["execution_allowed"] = False
        self._payload["advisory_only"] = True
        self._payload["sources"] = [by_id[k] for k in sorted(by_id)]
        self._by_id = by_id
        self.integrity_hash = self.compute_integrity_hash(self._payload)

    @staticmethod
    def _normalize_and_validate_row(row: dict[str, Any]) -> dict[str, Any]:
        source_id = str(row.get("source_id") or "").strip()
        if not source_id:
            raise SourceCatalogueError("source_id required")
        # Defaults that preserve explicit advisory/execution safety without inventing facts
        if "direct_execution_influence" not in row:
            row["direct_execution_influence"] = False
        if "operational_state" not in row:
            access = str(row.get("access_status") or UNKNOWN).upper()
            if access == "FIXTURE_ONLY":
                row["operational_state"] = "FIXTURE_ONLY"
            elif access in BLOCKED_ACCESS:
                row["operational_state"] = "BLOCKED"
            elif bool(row.get("enabled", False)):
                row["operational_state"] = "ENABLED_OFFLINE"
            else:
                row["operational_state"] = "CATALOGUED"
        if "online_validation_required" not in row:
            # Live/online use remains unauthorized until explicit LIVE_AUTHORIZED + approval
            access = str(row.get("access_status") or "").upper()
            row["online_validation_required"] = access != "LIVE_AUTHORIZED"

        missing = [f for f in REQUIRED_SOURCE_FIELDS if f not in row]
        if missing:
            raise SourceCatalogueError(f"{source_id}: missing required fields: {', '.join(missing)}")

        tier = str(row.get("trust_tier") or UNKNOWN)
        if tier not in TrustTier.ORDER:
            raise SourceCatalogueError(f"invalid trust_tier for {source_id}: {tier}")

        if bool(row.get("direct_execution_influence", False)):
            raise SourceCatalogueError(f"{source_id}: direct_execution_influence must be false")
        if not bool(row.get("prohibited_from_direct_execution", True)):
            raise SourceCatalogueError(f"{source_id}: prohibited_from_direct_execution must be true")

        access = str(row.get("access_status") or "").upper()
        enabled = bool(row.get("enabled", False))
        if enabled and access != "FIXTURE_ONLY":
            raise SourceCatalogueError(
                f"{source_id}: enabled sources must remain FIXTURE_ONLY during MI-EXT-001 recovery"
            )
        if access in BLOCKED_ACCESS and enabled:
            raise SourceCatalogueError(f"{source_id}: blocked/prohibited source cannot be enabled")
        if bool(row.get("requires_terms_review", False)) and not bool(row.get("terms_reviewed", False)) and enabled:
            raise SourceCatalogueError(f"{source_id}: unreviewed source cannot be enabled")

        cost = str(row.get("cost_status") or "").casefold()
        licensing = str(row.get("licensing_usage_classification") or "").upper()
        if any(marker in cost for marker in COMMERCIAL_COST_MARKERS):
            if licensing not in {"COMMERCIAL_LICENSE_APPROVED"} and enabled:
                raise SourceCatalogueError(
                    f"{source_id}: commercial source cannot be enabled without approved licensing record"
                )
            if licensing in {"COMMERCIAL_LICENSE_REQUIRED", "TERMS_PENDING_REVIEW"} and enabled:
                raise SourceCatalogueError(f"{source_id}: commercial licensing not approved")

        if tier == TrustTier.TIER_4_UNVERIFIED_SOCIAL and bool(row.get("may_influence_advisory", False)):
            raise SourceCatalogueError(f"{source_id}: Tier 4 cannot influence advisory without corroboration policy")

        for key in ("jurisdiction", "access_method", "cost_status", "licensing_usage_classification", "freshness_threshold"):
            if not str(row.get(key) or "").strip():
                raise SourceCatalogueError(f"{source_id}: {key} required")

        row["source_id"] = source_id
        row["direct_execution_influence"] = False
        row["prohibited_from_direct_execution"] = True
        return row

    @classmethod
    def load(cls, path: str | Path | None = None) -> "SourceCatalogue":
        catalogue_path = Path(path or DEFAULT_CATALOGUE_PATH)
        try:
            payload = json.loads(catalogue_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SourceCatalogueError(str(exc)) from exc
        return cls(payload)

    @staticmethod
    def compute_integrity_hash(payload: Mapping[str, Any]) -> str:
        sources = payload.get("sources") or []
        material = {
            "schema_version": payload.get("schema_version"),
            "program": payload.get("program"),
            "sources": sorted(
                (
                    {
                        "source_id": s.get("source_id"),
                        "trust_tier": s.get("trust_tier"),
                        "jurisdiction": s.get("jurisdiction"),
                        "access_method": s.get("access_method"),
                        "cost_status": s.get("cost_status"),
                        "licensing_usage_classification": s.get("licensing_usage_classification"),
                        "freshness_threshold": s.get("freshness_threshold"),
                        "may_influence_advisory": s.get("may_influence_advisory"),
                        "direct_execution_influence": False,
                        "prohibited_from_direct_execution": True,
                        "access_status": s.get("access_status"),
                        "operational_state": s.get("operational_state"),
                        "online_validation_required": s.get("online_validation_required"),
                        "enabled": s.get("enabled"),
                    }
                    for s in sources
                    if isinstance(s, Mapping)
                ),
                key=lambda r: str(r.get("source_id") or ""),
            ),
        }
        return canonical_json_hash(material)

    def get(self, source_id: str) -> dict[str, Any]:
        key = str(source_id or "").strip()
        if key not in self._by_id:
            raise SourceCatalogueError(f"unsupported or unregistered source_id: {key}")
        return dict(self._by_id[key])

    def require_enabled(self, source_id: str) -> dict[str, Any]:
        row = self.get(source_id)
        if not bool(row.get("enabled", False)):
            raise SourceCatalogueError(f"source disabled: {source_id}")
        if bool(row.get("requires_terms_review", False)) and not bool(row.get("terms_reviewed", False)):
            raise SourceCatalogueError(f"source terms not reviewed: {source_id}")
        if str(row.get("access_status") or "").upper() in BLOCKED_ACCESS:
            raise SourceCatalogueError(f"source access prohibited: {source_id}")
        if bool(row.get("direct_execution_influence", False)):
            raise SourceCatalogueError(f"source claims direct execution influence: {source_id}")
        return row

    def tier_of(self, source_id: str) -> str:
        return str(self.get(source_id).get("trust_tier") or UNKNOWN)

    def all_sources(self) -> list[dict[str, Any]]:
        return [dict(v) for v in self._by_id.values()]

    @staticmethod
    def higher_tier_wins(tier_a: str, tier_b: str) -> str:
        return tier_a if TrustTier.rank(tier_a) <= TrustTier.rank(tier_b) else tier_b

    def may_influence_advisory(self, source_id: str) -> bool:
        row = self.get(source_id)
        if str(row.get("trust_tier")) == TrustTier.TIER_4_UNVERIFIED_SOCIAL:
            return False
        return bool(row.get("may_influence_advisory", False))

    def prohibited_from_execution(self, source_id: str) -> bool:
        return bool(self.get(source_id).get("prohibited_from_direct_execution", True))

    def is_live_fetch_authorized(self, source_id: str) -> bool:
        del source_id
        # MI-EXT-001 recovery is fixture/offline only. Live network ingestion stays unauthorized.
        return False
