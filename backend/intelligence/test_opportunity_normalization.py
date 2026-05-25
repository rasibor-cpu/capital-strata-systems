from __future__ import annotations

from backend.intelligence.opportunity_normalizer import OpportunityNormalizer
from backend.intelligence.opportunity_viability_engine import OpportunityViabilityEngine


def run_tests() -> None:
    normalizer = OpportunityNormalizer()
    viability_engine = OpportunityViabilityEngine()

    classes = ["crypto", "fx", "futures", "options", "equity", "etf", "indices", "commodities"]
    for asset_class in classes:
        normalized = normalizer.normalize_candidate(asset_class, {"symbol": f"{asset_class.upper()}_X", "score": 0.9})
        assert normalized.symbol.endswith("_X")

    missing_fields = normalizer.normalize_candidate("crypto", {"symbol": "BTC_USD"})
    assert missing_fields.signal_strength == 0.0

    malformed_payload = normalizer.normalize_candidate("fx", "bad_payload")
    assert malformed_payload.symbol == "UNKNOWN"

    result = viability_engine.evaluate(missing_fields)
    assert isinstance(result.viable, bool)
    assert isinstance(result.reasons, list)


if __name__ == "__main__":
    run_tests()
    print("test_opportunity_normalization: PASS")
