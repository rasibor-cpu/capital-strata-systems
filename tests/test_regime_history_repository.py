from __future__ import annotations

import pytest

from backend.analytics.regime_history_repository import (
    RegimeHistoryRepository,
    RegimeHistoryRepositoryError,
)


def _entry(symbol: str = "EUR/USD", regime: str = "TRENDING", confidence: float = 0.82) -> dict[str, object]:
    return {
        "timestamp": "2026-06-24T10:00:00+00:00",
        "regime": regime,
        "symbol": symbol,
        "confidence": confidence,
    }


def test_history_persistence_and_reload(tmp_path) -> None:
    repo = RegimeHistoryRepository(tmp_path / "regime_history.json")
    repo.create_storage()

    repo.append_regime(_entry("EUR/USD", "TRENDING", 0.9))
    repo.append_regime(_entry("BTC/USD", "HIGH_VOLATILITY", 0.7))

    reloaded = RegimeHistoryRepository(repo.storage_path).load_history()
    assert len(reloaded) == 2
    assert reloaded[0]["regime"] == "TRENDING"
    assert reloaded[1]["symbol"] == "BTC/USD"


def test_recent_counts_and_symbol_history(tmp_path) -> None:
    repo = RegimeHistoryRepository(tmp_path / "regime_history.json")
    repo.create_storage()

    repo.append_regime(_entry("EUR/USD", "TRENDING", 0.8))
    repo.append_regime(_entry("EUR/USD", "RANGING", 0.6))
    repo.append_regime(_entry("BTC/USD", "BREAKOUT", 0.9))

    recent = repo.list_recent_regimes(limit=2)
    counts = repo.regime_counts()
    symbol_rows = repo.symbol_regime_history("eur/usd", limit=5)

    assert len(recent) == 2
    assert counts["TRENDING"] == 1
    assert counts["RANGING"] == 1
    assert len(symbol_rows) == 2
    assert all(row["symbol"] == "EUR/USD" for row in symbol_rows)


def test_repository_fail_closed(tmp_path) -> None:
    path = tmp_path / "regime_history.json"
    path.write_text("not-json", encoding="utf-8")

    repo = RegimeHistoryRepository(path)
    with pytest.raises(RegimeHistoryRepositoryError):
        repo.load_history()
