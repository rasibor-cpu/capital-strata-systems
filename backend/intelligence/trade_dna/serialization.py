"""DIP-002 Trade DNA JSON serialization helpers."""

from __future__ import annotations

import json
from typing import Any, Mapping

from backend.intelligence.trade_dna.derived import assert_not_embedded_in_facts
from backend.intelligence.trade_dna.schema import TradeDNARecord, trade_dna_from_dict
from backend.intelligence.trade_dna.validation import validate_trade_dna


def serialize_trade_dna(record: TradeDNARecord, *, validate: bool = True) -> str:
    """Serialize a Trade DNA fact record to canonical JSON text."""
    if validate:
        validate_trade_dna(record, require_hash=True)
    payload = record.to_dict()
    assert_not_embedded_in_facts(payload)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def deserialize_trade_dna(
    text: str | Mapping[str, Any],
    *,
    validate: bool = True,
    allow_compatible_schema: bool = False,
) -> TradeDNARecord:
    """Deserialize JSON text or mapping into a Trade DNA fact record."""
    if isinstance(text, Mapping):
        payload = dict(text)
    else:
        payload = json.loads(text)
    assert_not_embedded_in_facts(payload)
    record = trade_dna_from_dict(payload)
    if validate:
        return validate_trade_dna(
            record,
            require_hash=True,
            allow_compatible_schema=allow_compatible_schema,
        )
    return record
