from __future__ import annotations


INFO = "INFO"
WARNING = "WARNING"
CRITICAL = "CRITICAL"


def classify_mismatch_severity(
    source_a_count: int,
    source_b_count: int,
) -> str:
    """
    Simple severity classifier.

    Difference = 0      -> INFO
    Difference = 1      -> WARNING
    Difference >= 2     -> CRITICAL
    """

    difference = abs(
        int(source_a_count) - int(source_b_count)
    )

    if difference == 0:
        return INFO

    if difference == 1:
        return WARNING

    return CRITICAL