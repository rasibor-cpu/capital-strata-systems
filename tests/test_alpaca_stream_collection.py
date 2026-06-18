from __future__ import annotations

import importlib.util
from pathlib import Path

from live_data.alpaca_adapter import AlpacaLiveDataAdapter


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_module_from_path(path: Path) -> None:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)


def test_alpaca_live_data_adapter_export_is_import_safe() -> None:
    assert AlpacaLiveDataAdapter.__name__ == "AlpacaLiveDataAdapter"


def test_stream_scripts_are_import_safe_for_pytest_collection() -> None:
    for relative_path in (
        "tests/stream/stream_test.py",
        "tests/stream/stream_test_quotes.py",
        "tests/stream/stream_test_crypto.py",
    ):
        _load_module_from_path(PROJECT_ROOT / relative_path)
