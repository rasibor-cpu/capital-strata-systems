"""Canonical evidence hashing — excludes volatile retrieval/runtime metadata."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_json_hash(payload: Mapping[str, Any] | list[Any] | dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return sha256_text(body)


def normalize_title(title: str) -> str:
    text = re.sub(r"\s+", " ", str(title or "").strip().casefold())
    text = re.sub(r"[^a-z0-9 %$.,:;/\-]", "", text)
    return text.strip()


def semantic_fingerprint(
    *,
    title: str,
    category: str,
    instruments: tuple[str, ...] | list[str],
    published_at: str,
) -> str:
    material = {
        "title": normalize_title(title),
        "category": str(category or "").casefold(),
        "instruments": sorted({str(i).upper() for i in instruments if str(i).strip()}),
        "published_day": str(published_at or "")[:10],
    }
    return canonical_json_hash(material)


def normalized_evidence_material(
    *,
    title: str,
    summary: str,
    category: str,
    instruments: tuple[str, ...] | list[str],
    published_at: str,
    source_id: str,
    schema_version: str,
    parser_version: str,
) -> dict[str, Any]:
    """Evidence material for normalized hash.

    Includes evidentiary published_at; excludes volatile retrieved_at / runtime clocks.
    """
    return {
        "title": normalize_title(title),
        "summary": str(summary or "").strip(),
        "category": str(category or "").casefold(),
        "instruments": sorted({str(i).upper() for i in instruments if str(i).strip()}),
        "published_at": str(published_at or ""),
        "source_id": str(source_id or ""),
        "schema_version": str(schema_version or ""),
        "parser_version": str(parser_version or ""),
    }


def normalized_evidence_hash(**kwargs: Any) -> str:
    return canonical_json_hash(normalized_evidence_material(**kwargs))
