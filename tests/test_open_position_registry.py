from __future__ import annotations

from pathlib import Path

from backend.portfolio.open_position_registry import OpenPositionRegistry


def test_open_position_registry_appends_and_summarizes_open_positions(tmp_path: Path) -> None:
    registry = OpenPositionRegistry(tmp_path)

    result = registry.sync_positions(
        [
            {
                "symbol": "SPY",
                "asset_class": "EQUITIES",
                "quantity": 10,
                "entry_price": 400,
                "current_price": 410,
                "entry_timestamp": "2026-06-29T12:00:00+00:00",
            }
        ],
        timestamp="2026-06-29T12:05:00+00:00",
    )

    assert result["status"] == "OK"
    assert result["open_count"] == 1
    assert result["total_exposure"] == 4100.0
    assert result["open_positions"][0]["age_seconds"] == 300.0
    assert (tmp_path / "portfolio" / "open_position_registry.json").exists()


def test_open_position_registry_closes_missing_positions(tmp_path: Path) -> None:
    registry = OpenPositionRegistry(tmp_path)
    registry.sync_positions(
        [{"symbol": "SPY", "asset_class": "EQUITIES", "quantity": 1, "entry_price": 100, "current_price": 110}],
        timestamp="2026-06-29T12:00:00+00:00",
    )

    result = registry.sync_positions([], timestamp="2026-06-29T12:10:00+00:00")

    assert result["open_count"] == 0
    closed = registry.list_closed()
    assert closed["closed_count"] == 1
    assert closed["closed_positions"][0]["status"] == "CLOSED"
    assert closed["closed_positions"][0]["realized_pnl"] == 10.0


def test_open_position_registry_handles_corrupt_file_safely(tmp_path: Path) -> None:
    path = tmp_path / "portfolio" / "open_position_registry.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not-json", encoding="utf-8")

    result = OpenPositionRegistry(tmp_path).summary()

    assert result["status"] == "OK"
    assert result["open_count"] == 0
