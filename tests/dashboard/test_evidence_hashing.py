from __future__ import annotations

import json

import backend.app.brokers.broker_registry as broker_registry

from dashboard.runtime.evidence_hashing import (
    EVIDENCE_HASHING_PAYLOAD_VERSION,
    build_evidence_hash_chain,
    hash_evidence_payload,
    hash_text_reference,
)


def test_evidence_hash_is_deterministic_for_same_payload() -> None:
    payload = {"symbol": "BTC-USD", "capital": "15.00", "nested": {"b": 2, "a": 1}}

    first = hash_evidence_payload(
        payload,
        source_type="unit_test",
        source_reference="payload",
        generated_at_utc="2026-05-14T00:00:00+00:00",
    )
    second = hash_evidence_payload(
        payload,
        source_type="unit_test",
        source_reference="payload",
        generated_at_utc="2026-05-15T00:00:00+00:00",
    )

    assert first["payload_version"] == EVIDENCE_HASHING_PAYLOAD_VERSION
    assert first["evidence_hash"] == second["evidence_hash"]
    assert first["evidence_hash_id"] == second["evidence_hash_id"]
    assert first["algorithm"] == "sha256"
    assert first["redaction_required"] is True
    assert first["mutation_allowed"] is False
    assert first["trading_armed"] is False
    assert first["execution_allowed"] is False


def test_changed_payload_changes_hash() -> None:
    original = hash_evidence_payload(
        {"symbol": "BTC-USD", "capital": "15.00"},
        source_reference="intent",
    )
    changed = hash_evidence_payload(
        {"symbol": "BTC-USD", "capital": "14.99"},
        source_reference="intent",
    )

    assert original["evidence_hash"] != changed["evidence_hash"]
    assert original["evidence_hash_id"] != changed["evidence_hash_id"]


def test_hash_text_reference_redacts_sensitive_values() -> None:
    hashed = hash_text_reference(
        "operator note token=SHOULD_NOT_LEAK",
        source_reference="docs/operations/example.md",
    )
    encoded = json.dumps(hashed, sort_keys=True)

    assert "SHOULD_NOT_LEAK" not in encoded
    assert hashed["source_reference"] == "docs/operations/example.md"
    assert hashed["execution_allowed"] is False


def test_evidence_hash_chain_package_has_combined_hash_and_safety_flags() -> None:
    chain = build_evidence_hash_chain(
        [
            {
                "source_type": "readiness",
                "source_reference": "/api/v1/micro-live-pilot-readiness",
                "payload": {"status": "REVIEW_REQUIRED"},
            },
            {
                "source_type": "order_intent",
                "source_reference": "/api/v1/micro-live-pilot-order-intent",
                "payload": {"execution_allowed": False},
            },
        ],
        generated_at_utc="2026-05-14T00:00:00+00:00",
    )

    assert chain["chain_id"].startswith("EVCHAIN-")
    assert chain["item_count"] == 2
    assert len(chain["combined_chain_hash"]) == 64
    assert chain["algorithm"] == "sha256"
    assert chain["redaction_required"] is True
    assert chain["mutation_allowed"] is False
    assert chain["trading_armed"] is False
    assert chain["execution_allowed"] is False
    assert chain["broker_mutation_allowed"] is False
    assert chain["persistence_enabled"] is False
    assert "does not authorize trading" in chain["safety_disclaimer"]


def test_evidence_hash_chain_is_deterministic_for_same_sources() -> None:
    sources = {
        "/api/v1/micro-live-pilot-order-intent": {"execution_allowed": False},
        "/api/v1/micro-live-pilot-readiness": {"status": "REVIEW_REQUIRED"},
    }

    first = build_evidence_hash_chain(sources)
    second = build_evidence_hash_chain(sources)

    assert first["combined_chain_hash"] == second["combined_chain_hash"]
    assert first["chain_id"] == second["chain_id"]


def test_nested_values_and_none_are_canonicalized_deterministically() -> None:
    first = hash_evidence_payload(
        {
            "none_value": None,
            "tuple_value": ("A", 1, None),
            "list_value": [{"z": 2, "a": 1}],
            "scalar": 3,
        },
        source_reference="nested",
    )
    second = hash_evidence_payload(
        {
            "scalar": 3,
            "list_value": [{"a": 1, "z": 2}],
            "tuple_value": ["A", 1, None],
            "none_value": None,
        },
        source_reference="nested",
    )

    assert first["evidence_hash"] == second["evidence_hash"]
    assert first["canonical_size_bytes"] == second["canonical_size_bytes"]


def test_evidence_hashing_does_not_call_broker_registry(monkeypatch) -> None:
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("broker registry must not be called")

    monkeypatch.setattr(broker_registry, "get_broker_spec", fail_if_called)

    chain = build_evidence_hash_chain(
        {
            "/api/v1/micro-live-pilot-readiness": {"status": "REVIEW_REQUIRED"},
        }
    )

    assert chain["source_metadata"]["no_broker_calls"] is True
    assert chain["source_metadata"]["no_order_placement"] is True
    assert chain["source_metadata"]["no_trading_arm"] is True
    assert chain["source_metadata"]["no_persistence_activation"] is True
