from __future__ import annotations

SOURCE_RELIABILITY = {
    "federal reserve": 100,
    "sec": 100,
    "reuters": 95,
    "bloomberg": 95,
    "major exchange": 95,
    "verified institutional analyst": 85,
    "financial influencer": 40,
    "reddit rumor": 10,
    "unknown source": 5,
}


def get_source_reliability(source_name: str) -> int:
    if not source_name:
        return SOURCE_RELIABILITY["unknown source"]

    key = str(source_name).strip().casefold()
    return SOURCE_RELIABILITY.get(key, SOURCE_RELIABILITY["unknown source"])
