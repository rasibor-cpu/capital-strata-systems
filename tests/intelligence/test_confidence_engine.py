from backend.intelligence.global_intelligence.confidence_engine import calculate_event_confidence


def test_calculate_event_confidence_clamps_and_penalties():
    confidence = calculate_event_confidence(
        source_reliability=95,
        confirming_sources=3,
        market_confirmation=True,
        contradiction=False,
        rumor=False,
    )
    assert confidence == 100.0

    confidence_with_contradiction = calculate_event_confidence(
        source_reliability=80,
        confirming_sources=1,
        market_confirmation=False,
        contradiction=True,
        rumor=False,
    )
    assert confidence_with_contradiction == 60.0

    confidence_rumor = calculate_event_confidence(
        source_reliability=40,
        confirming_sources=1,
        market_confirmation=False,
        contradiction=False,
        rumor=True,
    )
    assert confidence_rumor == 15.0
